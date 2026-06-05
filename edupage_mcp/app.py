from __future__ import annotations

import json
from datetime import date

from edupage_api.exceptions import BadCredentialsException, CaptchaException
from edupage_api.substitution import TimetableChange
from mcp.server.fastmcp import Context, FastMCP

from .runtime import EduPageContext, app_lifespan, call_edupage, logger
from .serializers import (
    serialize_account,
    serialize_class,
    serialize_grade,
    serialize_lesson,
    serialize_meals,
    serialize_subject,
    serialize_substitution,
    serialize_timetable_change,
    serialize_timeline_event,
)
from .substitutions import (
    get_missing_teacher_message,
    get_substitutions as fetch_substitutions,
)

mcp = FastMCP("edupage", lifespan=app_lifespan)


def _parse_target_date(date_str: str | None) -> date:
    return date.fromisoformat(date_str) if date_str else date.today()


@mcp.tool()
async def get_timetable(ctx: Context, date_str: str | None = None) -> str:
    """Get the student's timetable for a specific date.

    Args:
        date_str: Date in ISO format (YYYY-MM-DD). If None, returns today's timetable.

    Returns:
        JSON string with list of lessons or error message.
    """
    try:
        edupage_ctx: EduPageContext = ctx.request_context.lifespan_context
        target_date = _parse_target_date(date_str)

        timetable = await call_edupage(
            edupage_ctx, edupage_ctx.edupage.get_my_timetable, target_date
        )

        if timetable is None:
            return json.dumps(
                {"message": "No timetable data available for this date"}, indent=2
            )

        serialized = [serialize_lesson(lesson) for lesson in timetable.lessons]
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
        edupage_ctx: EduPageContext = ctx.request_context.lifespan_context

        if (year is None) != (term is None):
            return json.dumps(
                {"error": "Both year and term must be provided together, or neither"},
                indent=2,
            )

        if term is not None and term not in ["P1", "P2"]:
            return json.dumps({"error": "term must be 'P1' or 'P2'"}, indent=2)

        if year is not None and term is not None:
            from edupage_api.grades import Term

            grades = await call_edupage(
                edupage_ctx,
                edupage_ctx.edupage.get_grades_for_term,
                year,
                Term(term),
            )
        else:
            grades = await call_edupage(edupage_ctx, edupage_ctx.edupage.get_grades)

        if not grades:
            return json.dumps({"message": "No grades available"}, indent=2)

        serialized = [serialize_grade(grade) for grade in grades]
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
        edupage_ctx: EduPageContext = ctx.request_context.lifespan_context

        if date_from:
            notifications = await call_edupage(
                edupage_ctx,
                edupage_ctx.edupage.get_notification_history,
                date.fromisoformat(date_from),
            )
        else:
            notifications = await call_edupage(
                edupage_ctx, edupage_ctx.edupage.get_notifications
            )

        if not notifications:
            return json.dumps({"message": "No notifications available"}, indent=2)

        serialized = [serialize_timeline_event(event) for event in notifications]
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
        edupage_ctx: EduPageContext = ctx.request_context.lifespan_context
        result = await call_edupage(edupage_ctx, edupage_ctx.edupage.get_teachers)

        if result is None:
            return json.dumps({"message": "No teachers data available"}, indent=2)

        serialized = [serialize_account(teacher) for teacher in result]
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
        edupage_ctx: EduPageContext = ctx.request_context.lifespan_context
        result = await call_edupage(edupage_ctx, edupage_ctx.edupage.get_students)

        if result is None:
            return json.dumps({"message": "No students data available"}, indent=2)

        serialized = [serialize_account(student) for student in result]
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
        edupage_ctx: EduPageContext = ctx.request_context.lifespan_context
        result = await call_edupage(edupage_ctx, edupage_ctx.edupage.get_classes)

        if result is None:
            return json.dumps({"message": "No classes data available"}, indent=2)

        serialized = [serialize_class(cls) for cls in result]
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
        edupage_ctx: EduPageContext = ctx.request_context.lifespan_context
        result = await call_edupage(edupage_ctx, edupage_ctx.edupage.get_subjects)

        if result is None:
            return json.dumps({"message": "No subjects data available"}, indent=2)

        serialized = [serialize_subject(subj) for subj in result]
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
        edupage_ctx: EduPageContext = ctx.request_context.lifespan_context
        target_date = _parse_target_date(date_str)

        result = await call_edupage(
            edupage_ctx, edupage_ctx.edupage.get_meals, target_date
        )

        if result is None:
            return json.dumps({"message": "No meals data available"}, indent=2)

        serialized = serialize_meals(result)
        return json.dumps(serialized, ensure_ascii=False, indent=2)

    except ValueError as e:
        return json.dumps({"error": f"Invalid date format: {e}"}, indent=2)
    except (BadCredentialsException, CaptchaException) as e:
        return json.dumps({"error": f"Authentication error: {str(e)}"}, indent=2)
    except Exception as e:
        logger.exception(f"Error in get_meals: {e}")
        return json.dumps({"error": str(e)}, indent=2)


@mcp.tool()
async def get_substitutions(ctx: Context, date_str: str | None = None) -> str:
    """Get raw substitutions for a specific date.

    Args:
        date_str: Date in ISO format (YYYY-MM-DD). If None, returns today's substitutions.

    Returns:
        JSON string with list of substitutions or error message.
    """
    try:
        edupage_ctx: EduPageContext = ctx.request_context.lifespan_context
        target_date = _parse_target_date(date_str)

        result = await call_edupage(
            edupage_ctx, fetch_substitutions, edupage_ctx.edupage, target_date
        )

        if not result:
            return json.dumps({"message": "No substitutions available"}, indent=2)

        serialized = [serialize_substitution(item) for item in result]
        return json.dumps(serialized, ensure_ascii=False, indent=2)

    except ValueError as e:
        return json.dumps({"error": f"Invalid date format: {e}"}, indent=2)
    except (BadCredentialsException, CaptchaException) as e:
        return json.dumps({"error": f"Authentication error: {str(e)}"}, indent=2)
    except Exception as e:
        logger.exception(f"Error in get_substitutions: {e}")
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
        edupage_ctx: EduPageContext = ctx.request_context.lifespan_context
        target_date = _parse_target_date(date_str)

        substitutions = await call_edupage(
            edupage_ctx, fetch_substitutions, edupage_ctx.edupage, target_date
        )

        if not substitutions:
            return json.dumps({"message": "No timetable changes available"}, indent=2)

        result = [
            TimetableChange(
                change.change_class,
                change.lesson_n,
                f"{change.subject}: {change.details}" if change.subject else change.details,
                change.action,
            )
            for change in substitutions
        ]

        serialized = [serialize_timetable_change(item) for item in result]
        return json.dumps(serialized, ensure_ascii=False, indent=2)

    except ValueError as e:
        return json.dumps({"error": f"Invalid date format: {e}"}, indent=2)
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
        edupage_ctx: EduPageContext = ctx.request_context.lifespan_context
        target_date = _parse_target_date(date_str)

        blocked_message = await call_edupage(
            edupage_ctx,
            get_missing_teacher_message,
            edupage_ctx.edupage,
            target_date,
        )

        if blocked_message is not None:
            return json.dumps({"message": blocked_message}, ensure_ascii=False, indent=2)

        try:
            result = await call_edupage(
                edupage_ctx, edupage_ctx.edupage.get_missing_teachers, target_date
            )
        except ValueError:
            return json.dumps(
                {
                    "message": "Missing teacher data is not available for this school's substitution layout"
                },
                indent=2,
            )

        if result is None:
            return json.dumps(
                {"message": "No missing teachers data available"}, indent=2
            )

        serialized = [serialize_account(teacher) for teacher in result]
        return json.dumps(serialized, ensure_ascii=False, indent=2)

    except ValueError as e:
        return json.dumps({"error": f"Invalid date format: {e}"}, indent=2)
    except (BadCredentialsException, CaptchaException) as e:
        return json.dumps({"error": f"Authentication error: {str(e)}"}, indent=2)
    except Exception as e:
        logger.exception(f"Error in get_missing_teachers: {e}")
        return json.dumps({"error": str(e)}, indent=2)


def main() -> None:
    mcp.run(transport="stdio")
