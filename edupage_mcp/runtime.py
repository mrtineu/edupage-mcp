from __future__ import annotations

import asyncio
import logging
import os
import sys
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import TypeVar

from dotenv import load_dotenv
from edupage_api import Edupage
from edupage_api.exceptions import (
    BadCredentialsException,
    CaptchaException,
    ExpiredSessionException,
    MissingDataException,
    NotLoggedInException,
    RequestError,
)
from mcp.server.fastmcp import FastMCP

_ = load_dotenv()

logger = logging.getLogger("edupage-mcp")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    stream=sys.stderr,
)


@dataclass(slots=True)
class EduPageContext:
    edupage: Edupage
    username: str
    password: str
    subdomain: str


T = TypeVar("T")


async def login_edupage(
    edupage: Edupage, username: str, password: str, subdomain: str
) -> None:
    login_result = await asyncio.to_thread(edupage.login, username, password, subdomain)
    if login_result is not None:
        raise RuntimeError(
            "Two-factor authentication is required by EduPage account and is not supported by this MCP server yet."
        )


async def call_edupage(
    ctx: EduPageContext,
    func: Callable[..., T],
    *args: object,
    **kwargs: object,
) -> T:
    try:
        return await asyncio.to_thread(func, *args, **kwargs)
    except (ExpiredSessionException, NotLoggedInException) as exc:
        logger.warning(
            "EduPage session expired or not logged in. Re-authenticating once. reason=%s",
            type(exc).__name__,
        )

        try:
            await login_edupage(ctx.edupage, ctx.username, ctx.password, ctx.subdomain)
        except CaptchaException as captcha_exc:
            logger.error(
                "Re-authentication blocked by captcha challenge. reason=%s",
                str(captcha_exc),
            )
            raise RuntimeError(
                "EduPage login blocked by captcha challenge after session expiration."
            ) from captcha_exc
        except BadCredentialsException as bad_creds_exc:
            logger.error(
                "Re-authentication failed due to invalid credentials. reason=%s",
                str(bad_creds_exc),
            )
            raise RuntimeError(
                "EduPage credentials became invalid during runtime."
            ) from bad_creds_exc

        return await asyncio.to_thread(func, *args, **kwargs)


@asynccontextmanager
async def app_lifespan(server: FastMCP) -> AsyncIterator[EduPageContext]:
    del server

    username = os.getenv("EDUPAGE_USERNAME", "").strip()
    password = os.getenv("EDUPAGE_PASSWORD", "").strip()
    subdomain = os.getenv("EDUPAGE_SUBDOMAIN", "").strip()

    missing = [
        name
        for name, value in (
            ("EDUPAGE_USERNAME", username),
            ("EDUPAGE_PASSWORD", password),
            ("EDUPAGE_SUBDOMAIN", subdomain),
        )
        if not value
    ]

    if missing:
        logger.error(
            "Missing required environment variables: %s",
            ", ".join(missing),
        )
        raise SystemExit(1)

    edupage = Edupage()

    try:
        logger.info("Logging into EduPage subdomain=%s", subdomain)
        await login_edupage(edupage, username, password, subdomain)
        logger.info("EduPage login successful")
    except CaptchaException as exc:
        logger.error("EduPage login blocked by captcha challenge. reason=%s", str(exc))
        raise SystemExit(1) from exc
    except BadCredentialsException as exc:
        logger.error(
            "EduPage login failed due to invalid credentials. reason=%s", str(exc)
        )
        raise SystemExit(1) from exc
    except (MissingDataException, RequestError) as exc:
        logger.error(
            "EduPage login failed due to API/server error. details=%s", str(exc)
        )
        raise SystemExit(1) from exc
    except RuntimeError as exc:
        logger.error("EduPage login failed. details=%s", str(exc))
        raise SystemExit(1) from exc

    ctx = EduPageContext(
        edupage=edupage,
        username=username,
        password=password,
        subdomain=subdomain,
    )

    try:
        yield ctx
    finally:
        logger.info("Shutting down EduPage MCP lifespan context")
        if getattr(edupage, "session", None) is not None:
            await asyncio.to_thread(edupage.session.close)
