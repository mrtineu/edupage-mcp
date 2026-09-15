from __future__ import annotations

import html as html_lib
import json
import re
from pathlib import Path
from typing import Any

from edupage_api import Edupage

_TITLE_MARKER = ".etestPlayer("
_BLOCK_TAGS = re.compile(r"</(?:div|p|h[1-6]|li|tr)>|<br\s*/?>", re.IGNORECASE)
_TAG = re.compile(r"<[^>]+>")
_CONTENT_DISPOSITION_FILENAME = re.compile(r'filename\*?=(?:UTF-8\'\')?"?([^";]+)"?')


def html_to_text(fragment: str | None) -> str:
    """Convert a fragment of EduPage's rich-text HTML into readable plain text."""
    if not fragment:
        return ""

    text = _BLOCK_TAGS.sub("\n", fragment)
    text = _TAG.sub("", text)
    text = html_lib.unescape(text)

    lines = [line.strip() for line in text.splitlines()]
    lines = [line for line in lines if line]
    return "\n".join(lines)


def _walk_widget(widget: Any, blocks: list[str], attachments: list[dict[str, str]]) -> None:
    if not isinstance(widget, dict):
        return

    widget_class = widget.get("widgetClass")
    props = widget.get("props") or {}

    if widget_class == "TitleETestWidget":
        text = html_to_text(props.get("text"))
        if text:
            blocks.append(text)
    elif widget_class == "TextETestWidget":
        text = html_to_text(props.get("_parsedHtmlText") or props.get("htmlText"))
        if text:
            blocks.append(text)
    elif widget_class == "FileETestWidget":
        for file_entry in props.get("files") or []:
            src = file_entry.get("src")
            if not src:
                continue
            attachments.append(
                {"name": file_entry.get("name") or "", "src": src}
            )
    elif widget_class == "ElaborationETestWidget":
        if props.get("enableUpload") == "enabled":
            blocks.append("[Student answer / file upload area]")

    for child in widget.get("widgets") or []:
        _walk_widget(child, blocks, attachments)


def _parse_material_player(page_html: str) -> dict[str, Any]:
    idx = page_html.find(_TITLE_MARKER)
    if idx == -1:
        raise ValueError(
            "Could not find homework material data on the page "
            "(the material id may be invalid, or you may not have access to it)"
        )

    start = idx + len(_TITLE_MARKER)
    try:
        obj, _ = json.JSONDecoder().raw_decode(page_html[start:])
    except json.JSONDecodeError as exc:
        raise ValueError(f"Failed to parse homework material data: {exc}") from exc

    return obj


def get_homework_material(edupage: Edupage, base_url: str, superid: str) -> dict[str, Any]:
    """Fetch and parse the full content of a homework/material item.

    Args:
        edupage: An authenticated `Edupage` instance.
        base_url: The school's EduPage base URL, e.g. `https://example.edupage.org`.
        superid: The material id (`superid`) referenced from a homework notification's
            `additional_data`.

    Returns:
        A dict with title, dates, plain-text content, and a list of attachments
        (each with a `name` and an absolute `url`).
    """
    url = f"{base_url}/elearning/?cmd=MaterialPlayer&superid={superid}"
    response = edupage.custom_request(url, "GET")
    response.raise_for_status()

    player_data = _parse_material_player(response.text)

    material = player_data.get("materialData") or {}
    super_row = player_data.get("superRow") or {}
    hw_row = super_row.get("hwRow") or {}

    blocks: list[str] = []
    raw_attachments: list[dict[str, str]] = []

    cards_data = material.get("cardsData") or {}
    for card in cards_data.values():
        content_raw = card.get("content")
        if not content_raw:
            continue
        try:
            content = json.loads(content_raw)
        except json.JSONDecodeError:
            continue
        _walk_widget(content, blocks, raw_attachments)

    attachments: list[dict[str, str]] = []
    for attachment in raw_attachments:
        src = attachment["src"]
        url_ = src if src.startswith("http") else f"{base_url}{src}"
        attachments.append(
            {"name": attachment.get("name") or url_.rsplit("/", 1)[-1], "url": url_}
        )

    return {
        "superid": str(superid),
        "title": hw_row.get("name") or material.get("name"),
        "details": html_to_text(hw_row.get("details")) or None,
        "date_from": hw_row.get("datefrom"),
        "date_to": hw_row.get("dateto"),
        "content": "\n\n".join(blocks),
        "attachments": attachments,
    }


def _filename_from_response(response, fallback_url: str) -> str:
    disposition = response.headers.get("content-disposition") or ""
    match = _CONTENT_DISPOSITION_FILENAME.search(disposition)
    if match:
        return match.group(1)
    return fallback_url.rsplit("/", 1)[-1].split("?")[0] or "download"


def _sanitize_filename(name: str) -> str:
    name = Path(name).name  # strip any directory components
    name = re.sub(r'[\\/:*?"<>|\x00-\x1f]', "_", name).strip(" .")
    return name or "download"


def _dedupe_path(path: Path) -> Path:
    if not path.exists():
        return path

    stem, suffix = path.stem, path.suffix
    counter = 1
    candidate = path
    while candidate.exists():
        candidate = path.with_name(f"{stem} ({counter}){suffix}")
        counter += 1
    return candidate


def download_attachment(
    edupage: Edupage,
    url: str,
    dest_dir: Path,
    filename: str | None = None,
) -> Path:
    """Download a homework attachment and save it to `dest_dir`.

    Args:
        edupage: An authenticated `Edupage` instance.
        url: Absolute attachment URL, as returned by `get_homework_material`.
        dest_dir: Directory to save the file into (created if missing).
        filename: Optional filename override; otherwise inferred from the
            response or the URL.

    Returns:
        The path the file was saved to.
    """
    response = edupage.custom_request(url, "GET")
    response.raise_for_status()

    name = _sanitize_filename(filename or _filename_from_response(response, url))

    dest_dir.mkdir(parents=True, exist_ok=True)
    path = _dedupe_path(dest_dir / name)
    path.write_bytes(response.content)
    return path
