from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from html import unescape

from edupage_api import Edupage
from edupage_api.exceptions import ExpiredSessionException
from edupage_api.substitution import Action


@dataclass(slots=True)
class ParsedSubstitution:
    change_class: str
    lesson_n: int | tuple[int, int]
    period_label: str
    subject: str | None
    details: str
    action: Action


_SECTION_RE = re.compile(
    r'<tbody[^>]*class=["\'][^"\']*print-nobreak[^"\']*["\'][^>]*>(.*?)</tbody>',
    re.IGNORECASE | re.DOTALL,
)
_ROW_RE = re.compile(r"<tr[^>]*>(.*?)</tr>", re.IGNORECASE | re.DOTALL)
_CELL_RE = re.compile(r"<td(?P<attrs>[^>]*)>(?P<html>.*?)</td>", re.IGNORECASE | re.DOTALL)
_CLASS_RE = re.compile(r'class=["\']([^"\']+)["\']', re.IGNORECASE)
_HTML_TAG_RE = re.compile(r"<[^>]+>", re.DOTALL)
_HTML_SPACE_RE = re.compile(r"\s+")


def _html_to_text(html_fragment: str) -> str:
    text = re.sub(r"<br\s*/?>", "\n", html_fragment, flags=re.IGNORECASE)
    text = _HTML_TAG_RE.sub("", text)
    text = unescape(text)
    return _HTML_SPACE_RE.sub(" ", text).strip()


def _parse_lesson_n(period_label: str) -> int | tuple[int, int] | None:
    cleaned = period_label.strip()
    if cleaned.startswith("(") and cleaned.endswith(")"):
        cleaned = cleaned[1:-1].strip()

    numbers = [int(value) for value in re.findall(r"\d+", cleaned)]
    if not numbers:
        return None
    if len(numbers) >= 2:
        return (numbers[0], numbers[1])
    return numbers[0]


def _infer_action(subject: str | None, details: str) -> Action:
    normalized = f"{subject or ''} {details}".casefold()
    if "pridan" in normalized:
        return Action.ADDITION
    if "odpadlo" in normalized:
        return Action.DELETION
    return Action.CHANGE


def fetch_substitution_html(
    edupage: Edupage, target_date: date, mode: str = "classes"
) -> str | None:
    url = (
        f"https://{edupage.subdomain}.edupage.org/substitution/server/viewer.js"
        "?__func=getSubstViewerDayDataHtml"
    )
    data = {
        "__args": [None, {"date": target_date.strftime("%Y-%m-%d"), "mode": mode}],
        "__gsh": edupage.gsec_hash,
    }

    payload = edupage.session.post(url, json=data).json()
    if payload.get("reload"):
        raise ExpiredSessionException(
            "Invalid gsec hash! (Expired session, try logging in again!)"
        )

    html = payload.get("r")
    return html if isinstance(html, str) else None


def parse_substitutions(html: str | None) -> list[ParsedSubstitution]:
    if not html:
        return []

    substitutions: list[ParsedSubstitution] = []
    for section_html in _SECTION_RE.findall(html):
        current_class = ""

        for row_html in _ROW_RE.findall(section_html):
            cells: list[tuple[list[str], str]] = []
            for cell_match in _CELL_RE.finditer(row_html):
                attrs = cell_match.group("attrs")
                cell_class_match = _CLASS_RE.search(attrs)
                classes = (
                    cell_class_match.group(1).split() if cell_class_match is not None else []
                )
                cells.append((classes, _html_to_text(cell_match.group("html"))))

            if not cells:
                continue

            if any(
                text == "Na tento deň nie sú zadané žiadne suplovania."
                for _, text in cells
            ):
                continue

            header = next(
                (text for classes, text in cells if "header" in classes and text),
                None,
            )
            if header is not None:
                current_class = header

            period_label = next(
                (text for classes, text in cells if "period" in classes), ""
            )
            subject = next((text for classes, text in cells if "what" in classes), "")
            details = next((text for classes, text in cells if "info" in classes), "")

            lesson_n = _parse_lesson_n(period_label)
            if lesson_n is None or not details:
                continue

            substitutions.append(
                ParsedSubstitution(
                    change_class=current_class,
                    lesson_n=lesson_n,
                    period_label=period_label,
                    subject=subject or None,
                    details=details,
                    action=_infer_action(subject or None, details),
                )
            )

    return substitutions


def get_substitutions(edupage: Edupage, target_date: date) -> list[ParsedSubstitution]:
    return parse_substitutions(fetch_substitution_html(edupage, target_date))


def get_missing_teacher_message(edupage: Edupage, target_date: date) -> str | None:
    html = fetch_substitution_html(edupage, target_date, mode="teachers")
    if not html:
        return None

    text = _html_to_text(html)
    if "nepovolila zverejnenie informácií o suplovaní" in text.casefold():
        return text
    return None
