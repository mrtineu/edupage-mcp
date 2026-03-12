# pyright: reportMissingTypeStubs=false

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import date, datetime, time
from typing import TypeVar

from dotenv import load_dotenv
from edupage_api import EduAccount, EduGrade, EduStudent, EduTeacher, Edupage
from edupage_api.classes import Class
from edupage_api.classrooms import Classroom
from edupage_api.exceptions import (
    BadCredentialsException,
    CaptchaException,
    ExpiredSessionException,
    MissingDataException,
    NotLoggedInException,
    RequestError,
)
from edupage_api.lunches import Meal, Meals, Menu, Rating
from edupage_api.people import Gender
from edupage_api.subjects import Subject
from edupage_api.substitution import Action, TimetableChange
from edupage_api.timeline import EventType, TimelineEvent
from edupage_api.timetables import Lesson, Timetable
from mcp.server.fastmcp import Context, FastMCP

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


def _serialize_datetime(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()


def _serialize_time(value: time | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()


def _serialize_gender(gender: Gender | None) -> str | None:
    if gender is None:
        return None
    return gender.value


def _serialize_event_type(event_type: EventType | None) -> str | None:
    if event_type is None:
        return None
    return event_type.value


def _serialize_action(
    action: Action | tuple[int, int] | None,
) -> str | list[int] | None:
    if action is None:
        return None
    if isinstance(action, Action):
        return action.value
    return [action[0], action[1]]


def _serialize_subject(subj: Subject) -> dict[str, object]:
    return {
        "subject_id": subj.subject_id,
        "name": subj.name,
        "short": subj.short,
    }


def _serialize_classroom(room: Classroom) -> dict[str, object]:
    return {
        "classroom_id": room.classroom_id,
        "name": room.name,
        "short": room.short,
    }


def _serialize_account(
    acc: EduStudent | EduTeacher | EduAccount | str,
) -> dict[str, object] | str:
    if isinstance(acc, str):
        return acc

    base: dict[str, object] = {
        "person_id": acc.person_id,
        "name": acc.name,
        "gender": _serialize_gender(acc.gender),
        "in_school_since": _serialize_datetime(acc.in_school_since),
        "account_type": acc.account_type.value,
    }

    if isinstance(acc, EduStudent):
        base["class_id"] = acc.class_id
        base["number_in_class"] = acc.number_in_class
        return base

    if isinstance(acc, EduTeacher):
        base["classroom_name"] = acc.classroom_name
        base["teacher_to"] = _serialize_datetime(acc.teacher_to)
        return base

    return base


def _serialize_class(cls: Class) -> dict[str, object]:
    return {
        "class_id": cls.class_id,
        "name": cls.name,
        "short": cls.short,
        "homeroom_teachers": (
            [_serialize_account(t) for t in cls.homeroom_teachers]
            if cls.homeroom_teachers is not None
            else None
        ),
        "homeroom": (
            _serialize_classroom(cls.homeroom) if cls.homeroom is not None else None
        ),
        "grade": cls.grade,
    }


def _serialize_lesson(lesson: Lesson) -> dict[str, object]:
    return {
        "period": lesson.period,
        "start_time": _serialize_time(lesson.start_time),
        "end_time": _serialize_time(lesson.end_time),
        "duration": lesson.duration,
        "subject": _serialize_subject(lesson.subject)
        if lesson.subject is not None
        else None,
        "classes": (
            [_serialize_class(c) for c in lesson.classes]
            if lesson.classes is not None
            else None
        ),
        "groups": list(lesson.groups) if lesson.groups is not None else None,
        "teachers": (
            [_serialize_account(t) for t in lesson.teachers]
            if lesson.teachers is not None
            else None
        ),
        "classrooms": (
            [_serialize_classroom(r) for r in lesson.classrooms]
            if lesson.classrooms is not None
            else None
        ),
        "curriculum": lesson.curriculum,
        "online_lesson_link": lesson.online_lesson_link,
        "is_cancelled": lesson.is_cancelled,
        "is_event": lesson.is_event,
    }


def _serialize_timetable(timetable: Timetable) -> dict[str, object]:
    return {
        "lessons": [_serialize_lesson(lesson) for lesson in timetable.lessons],
    }


def _serialize_grade(grade: EduGrade) -> dict[str, object]:
    return {
        "event_id": grade.event_id,
        "title": grade.title,
        "grade_n": grade.grade_n,
        "comment": grade.comment,
        "date": _serialize_datetime(grade.date),
        "subject_id": grade.subject_id,
        "subject_name": grade.subject_name,
        "teacher": _serialize_account(grade.teacher)
        if grade.teacher is not None
        else None,
        "max_points": grade.max_points,
        "more_details": list(grade.more_details)
        if grade.more_details is not None
        else None,
        "importance": grade.importance,
        "verbal": grade.verbal,
        "percent": grade.percent,
        "class_grade_avg": grade.class_grade_avg,
    }


def _serialize_timeline_event(event: TimelineEvent) -> dict[str, object]:
    return {
        "event_id": event.event_id,
        "timestamp": _serialize_datetime(event.timestamp),
        "text": event.text,
        "author": _serialize_account(event.author),
        "recipient": _serialize_account(event.recipient),
        "event_type": _serialize_event_type(event.event_type),
        "additional_data": event.additional_data,  # pyright: ignore[reportUnknownMemberType]
    }


def _serialize_rating(rating: Rating) -> dict[str, object]:
    return {
        "quality_average": rating.quality_average,
        "quality_ratings": rating.quality_ratings,
        "quantity_average": rating.quantity_average,
        "quantity_ratings": rating.quantity_ratings,
    }


def _serialize_menu(menu: Menu) -> dict[str, object]:
    return {
        "name": menu.name,
        "allergens": menu.allergens,
        "weight": menu.weight,
        "number": menu.number,
        "rating": _serialize_rating(menu.rating) if menu.rating is not None else None,
    }


def _serialize_meal(meal: Meal) -> dict[str, object]:
    return {
        "served_from": _serialize_datetime(meal.served_from),
        "served_to": _serialize_datetime(meal.served_to),
        "amount_of_foods": meal.amount_of_foods,
        "chooseable_menus": list(meal.chooseable_menus),
        "can_be_changed_until": _serialize_datetime(meal.can_be_changed_until),
        "title": meal.title,
        "menus": [_serialize_menu(menu) for menu in meal.menus],
        "date": _serialize_datetime(meal.date),
        "ordered_meal": meal.ordered_meal,
        "meal_type": meal.meal_type.value,
    }


def _serialize_meals(meals: Meals) -> dict[str, object]:
    return {
        "snack": _serialize_meal(meals.snack) if meals.snack is not None else None,
        "lunch": _serialize_meal(meals.lunch) if meals.lunch is not None else None,
        "afternoon_snack": (
            _serialize_meal(meals.afternoon_snack)
            if meals.afternoon_snack is not None
            else None
        ),
    }


def _serialize_timetable_change(change: TimetableChange) -> dict[str, object]:
    lesson_n: int | list[int]
    if isinstance(change.lesson_n, tuple):
        lesson_n = [change.lesson_n[0], change.lesson_n[1]]
    else:
        lesson_n = change.lesson_n

    return {
        "change_class": change.change_class,
        "lesson_n": lesson_n,
        "title": change.title,
        "action": _serialize_action(change.action),
    }


T = TypeVar("T")


async def _login_edupage(
    edupage: Edupage, username: str, password: str, subdomain: str
) -> None:
    login_result = await asyncio.to_thread(edupage.login, username, password, subdomain)
    if login_result is not None:
        raise RuntimeError(
            "Two-factor authentication is required by EduPage account and is not supported by this MCP server yet."
        )


async def _call_edupage(
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
            await _login_edupage(ctx.edupage, ctx.username, ctx.password, ctx.subdomain)
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
        await _login_edupage(edupage, username, password, subdomain)
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


mcp = FastMCP("edupage", lifespan=app_lifespan)

_SERIALIZER_REGISTRY = (
    _serialize_datetime,
    _serialize_time,
    _serialize_gender,
    _serialize_event_type,
    _serialize_action,
    _serialize_subject,
    _serialize_classroom,
    _serialize_account,
    _serialize_class,
    _serialize_lesson,
    _serialize_timetable,
    _serialize_grade,
    _serialize_timeline_event,
    _serialize_rating,
    _serialize_menu,
    _serialize_meal,
    _serialize_meals,
    _serialize_timetable_change,
)

_INTERNAL_CALLS = (_call_edupage,)


@mcp.tool()
async def get_timetable(ctx: Context, date_str: str | None = None) -> str:
    """Get the student's timetable for a specific date.

    Args:
        date_str: Date in ISO format (YYYY-MM-DD). If None, returns today's timetable.

    Returns:
        JSON string with list of lessons or error message.
    """
    try:
        edupage_ctx: EduPageContext = ctx.lifespan_context

        target_date = date.fromisoformat(date_str) if date_str else date.today()

        timetable = await _call_edupage(
            edupage_ctx, edupage_ctx.edupage.get_my_timetable, target_date
        )

        if timetable is None:
            return json.dumps(
                {"message": "No timetable data available for this date"}, indent=2
            )

        serialized = [_serialize_lesson(lesson) for lesson in timetable.lessons]
        return json.dumps(serialized, ensure_ascii=False, indent=2)

    except ValueError as e:
        return json.dumps({"error": f"Invalid date format: {str(e)}"}, indent=2)
    except (BadCredentialsException, CaptchaException) as e:
        return json.dumps({"error": f"Authentication error: {str(e)}"}, indent=2)
    except Exception as e:
        logger.exception(f"Error in get_timetable: {e}")
        return json.dumps({"error": str(e)}, indent=2)


@mcp.tool()
async def get_grades(
    ctx: Context, year: int | None = None, term: str | None = None
) -> str:
    """Get the student's grades, optionally filtered by year and term.

    Args:
        year: School year (e.g., 2024). Must be provided if term is specified.
        term: Term/semester ("P1" or "P2"). Must be provided if year is specified.

    Returns:
        JSON string with list of grades or error message.
    """
    try:
        edupage_ctx: EduPageContext = ctx.lifespan_context

        if (year is None) != (term is None):
            return json.dumps(
                {"error": "Both year and term must be provided together, or neither"},
                indent=2,
            )

        if term is not None and term not in ["P1", "P2"]:
            return json.dumps({"error": "term must be 'P1' or 'P2'"}, indent=2)

        if year is not None and term is not None:
            from edupage_api.grades import Term

            term_enum = Term(term)
            grades = await _call_edupage(
                edupage_ctx, edupage_ctx.edupage.get_grades_for_term, year, term_enum
            )
        else:
            grades = await _call_edupage(edupage_ctx, edupage_ctx.edupage.get_grades)

        if not grades:
            return json.dumps({"message": "No grades available"}, indent=2)

        serialized = [_serialize_grade(grade) for grade in grades]
        return json.dumps(serialized, ensure_ascii=False, indent=2)

    except (BadCredentialsException, CaptchaException) as e:
        return json.dumps({"error": f"Authentication error: {str(e)}"}, indent=2)
    except Exception as e:
        logger.exception(f"Error in get_grades: {e}")
        return json.dumps({"error": str(e)}, indent=2)


@mcp.tool()
async def get_notifications(ctx: Context, date_from: str | None = None) -> str:
    """Get timeline notifications, optionally filtered from a start date.

    Args:
        date_from: Start date in ISO format (YYYY-MM-DD). If None, returns recent notifications.

    Returns:
        JSON string with list of timeline events or error message.
    """
    try:
        edupage_ctx: EduPageContext = ctx.lifespan_context

        if date_from:
            start_date = date.fromisoformat(date_from)
            notifications = await _call_edupage(
                edupage_ctx,
                edupage_ctx.edupage.get_notification_history,
                start_date,
            )
        else:
            notifications = await _call_edupage(
                edupage_ctx, edupage_ctx.edupage.get_notifications
            )

        if not notifications:
            return json.dumps({"message": "No notifications available"}, indent=2)

        serialized = [_serialize_timeline_event(event) for event in notifications]
        return json.dumps(serialized, ensure_ascii=False, indent=2)

    except ValueError as e:
        return json.dumps({"error": f"Invalid date format: {str(e)}"}, indent=2)
    except (BadCredentialsException, CaptchaException) as e:
        return json.dumps({"error": f"Authentication error: {str(e)}"}, indent=2)
    except Exception as e:
        logger.exception(f"Error in get_notifications: {e}")
        return json.dumps({"error": str(e)}, indent=2)


@mcp.tool()
async def get_teachers(ctx: Context) -> str:
    """Get all teachers at the school.

    Returns:
        JSON string with list of teachers or error message.
    """
    try:
        edupage_ctx: EduPageContext = ctx.lifespan_context

        result = await _call_edupage(edupage_ctx, edupage_ctx.edupage.get_teachers)

        if result is None:
            return json.dumps({"message": "No teachers data available"}, indent=2)

        serialized = [_serialize_account(teacher) for teacher in result]
        return json.dumps(serialized, ensure_ascii=False, indent=2)

    except (BadCredentialsException, CaptchaException) as e:
        return json.dumps({"error": f"Authentication error: {str(e)}"}, indent=2)
    except Exception as e:
        logger.exception(f"Error in get_teachers: {e}")
        return json.dumps({"error": str(e)}, indent=2)


@mcp.tool()
async def get_students(ctx: Context) -> str:
    """Get students in your class.

    Returns:
        JSON string with list of students or error message.
    """
    try:
        edupage_ctx: EduPageContext = ctx.lifespan_context

        result = await _call_edupage(edupage_ctx, edupage_ctx.edupage.get_students)

        if result is None:
            return json.dumps({"message": "No students data available"}, indent=2)

        serialized = [_serialize_account(student) for student in result]
        return json.dumps(serialized, ensure_ascii=False, indent=2)

    except (BadCredentialsException, CaptchaException) as e:
        return json.dumps({"error": f"Authentication error: {str(e)}"}, indent=2)
    except Exception as e:
        logger.exception(f"Error in get_students: {e}")
        return json.dumps({"error": str(e)}, indent=2)


@mcp.tool()
async def get_classes(ctx: Context) -> str:
    """Get all classes at the school.

    Returns:
        JSON string with list of classes or error message.
    """
    try:
        edupage_ctx: EduPageContext = ctx.lifespan_context

        result = await _call_edupage(edupage_ctx, edupage_ctx.edupage.get_classes)

        if result is None:
            return json.dumps({"message": "No classes data available"}, indent=2)

        serialized = [_serialize_class(cls) for cls in result]
        return json.dumps(serialized, ensure_ascii=False, indent=2)

    except (BadCredentialsException, CaptchaException) as e:
        return json.dumps({"error": f"Authentication error: {str(e)}"}, indent=2)
    except Exception as e:
        logger.exception(f"Error in get_classes: {e}")
        return json.dumps({"error": str(e)}, indent=2)


@mcp.tool()
async def get_subjects(ctx: Context) -> str:
    """Get all subjects taught at the school.

    Returns:
        JSON string with list of subjects or error message.
    """
    try:
        edupage_ctx: EduPageContext = ctx.lifespan_context

        result = await _call_edupage(edupage_ctx, edupage_ctx.edupage.get_subjects)

        if result is None:
            return json.dumps({"message": "No subjects data available"}, indent=2)

        serialized = [_serialize_subject(subj) for subj in result]
        return json.dumps(serialized, ensure_ascii=False, indent=2)

    except (BadCredentialsException, CaptchaException) as e:
        return json.dumps({"error": f"Authentication error: {str(e)}"}, indent=2)
    except Exception as e:
        logger.exception(f"Error in get_subjects: {e}")
        return json.dumps({"error": str(e)}, indent=2)


@mcp.tool()
async def get_meals(ctx: Context, date_str: str | None = None) -> str:
    """Get the school meal menu for a specific date.

    Args:
        date_str: Date in ISO format (YYYY-MM-DD). If None, returns today's meal menu.

    Returns:
        JSON string with meal data (snack, lunch, afternoon_snack) or error message.
    """
    try:
        edupage_ctx: EduPageContext = ctx.lifespan_context

        if date_str:
            try:
                target_date = date.fromisoformat(date_str)
            except ValueError as e:
                return json.dumps({"error": f"Invalid date format: {e}"}, indent=2)
        else:
            target_date = date.today()

        result = await _call_edupage(
            edupage_ctx, edupage_ctx.edupage.get_meals, target_date
        )

        if result is None:
            return json.dumps({"message": "No meals data available"}, indent=2)

        serialized = _serialize_meals(result)
        return json.dumps(serialized, ensure_ascii=False, indent=2)

    except (BadCredentialsException, CaptchaException) as e:
        return json.dumps({"error": f"Authentication error: {str(e)}"}, indent=2)
    except Exception as e:
        logger.exception(f"Error in get_meals: {e}")
        return json.dumps({"error": str(e)}, indent=2)


@mcp.tool()
async def get_timetable_changes(ctx: Context, date_str: str | None = None) -> str:
    """Get timetable substitutions/changes for a specific date.

    Args:
        date_str: Date in ISO format (YYYY-MM-DD). If None, returns today's timetable changes.

    Returns:
        JSON string with list of timetable changes or error message.
    """
    try:
        edupage_ctx: EduPageContext = ctx.lifespan_context

        if date_str:
            try:
                target_date = date.fromisoformat(date_str)
            except ValueError as e:
                return json.dumps({"error": f"Invalid date format: {e}"}, indent=2)
        else:
            target_date = date.today()

        result = await _call_edupage(
            edupage_ctx, edupage_ctx.edupage.get_timetable_changes, target_date
        )

        if result is None:
            return json.dumps({"message": "No timetable changes available"}, indent=2)

        serialized = [_serialize_timetable_change(item) for item in result]
        return json.dumps(serialized, ensure_ascii=False, indent=2)

    except (BadCredentialsException, CaptchaException) as e:
        return json.dumps({"error": f"Authentication error: {str(e)}"}, indent=2)
    except Exception as e:
        logger.exception(f"Error in get_timetable_changes: {e}")
        return json.dumps({"error": str(e)}, indent=2)


@mcp.tool()
async def get_missing_teachers(ctx: Context, date_str: str | None = None) -> str:
    """Get list of absent teachers for a specific date.

    Args:
        date_str: Date in ISO format (YYYY-MM-DD). If None, returns today's missing teachers.

    Returns:
        JSON string with list of missing teachers or error message.
    """
    try:
        edupage_ctx: EduPageContext = ctx.lifespan_context

        if date_str:
            try:
                target_date = date.fromisoformat(date_str)
            except ValueError as e:
                return json.dumps({"error": f"Invalid date format: {e}"}, indent=2)
        else:
            target_date = date.today()

        result = await _call_edupage(
            edupage_ctx, edupage_ctx.edupage.get_missing_teachers, target_date
        )

        if result is None:
            return json.dumps(
                {"message": "No missing teachers data available"}, indent=2
            )

        serialized = [_serialize_account(teacher) for teacher in result]
        return json.dumps(serialized, ensure_ascii=False, indent=2)

    except (BadCredentialsException, CaptchaException) as e:
        return json.dumps({"error": f"Authentication error: {str(e)}"}, indent=2)
    except Exception as e:
        logger.exception(f"Error in get_missing_teachers: {e}")
        return json.dumps({"error": str(e)}, indent=2)


if __name__ == "__main__":
    mcp.run(transport="stdio")
