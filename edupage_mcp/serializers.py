from __future__ import annotations

from datetime import datetime, time

from edupage_api import EduAccount, EduGrade, EduStudent, EduTeacher
from edupage_api.classes import Class
from edupage_api.classrooms import Classroom
from edupage_api.lunches import Meal, Meals, Menu, Rating
from edupage_api.people import Gender
from edupage_api.subjects import Subject
from edupage_api.substitution import Action, TimetableChange
from edupage_api.timeline import EventType, TimelineEvent
from edupage_api.timetables import Lesson, Timetable

from .substitutions import ParsedSubstitution


def serialize_datetime(value: datetime | str | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return value.isoformat()


def serialize_time(value: time | str | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return value.isoformat()


def serialize_gender(gender: Gender | None) -> str | None:
    if gender is None:
        return None
    return gender.value


EVENT_TYPE_LABELS: dict[str, str] = {
    # Messages
    EventType.MESSAGE.value: "Message",
    EventType.POLL.value: "Poll",
    EventType.NEWS.value: "News post",
    # Exams / homework
    EventType.BIG_EXAM.value: "Big exam (test/klasifikovana praca)",
    EventType.HOMEWORK.value: "Homework assignment",
    EventType.ORAL_EXAM.value: "Oral exam",
    EventType.PAPER.value: "Written exam/paper",
    EventType.PROJECT_EXAM.value: "Project exam",
    EventType.SHORT_EXAM.value: "Short exam/quiz",
    EventType.TESTING.value: "Testing",
    EventType.EXAM_ASSIGNMENT.value: "Exam assigned",
    EventType.EXAM_EVALUATION.value: "Exam result/grade published",
    EventType.HOMEWORK_STUDENT_STATE.value: "Homework completion status update",
    EventType.HOMEWORK_TEST.value: "Homework test assignment",
    # Grades
    EventType.GRADE.value: "Grade added",
    EventType.GRADES_DOC.value: "Grade document published",
    # Timetable / substitutions
    EventType.SUBSTITUTION.value: "Timetable substitution",
    EventType.TIMETABLE.value: "Timetable change",
    EventType.TT_CANCEL.value: "Lesson cancelled",
    EventType.CHANGE_ROOM.value: "Classroom changed",
    EventType.BOOKED_ROOM.value: "Room booked",
    EventType.LESSON.value: "Lesson",
    EventType.CLASS_TEACHER_LESSON.value: "Class teacher lesson",
    EventType.PROJECT_LESSON.value: "Project lesson",
    EventType.TUTORING.value: "Tutoring lesson",
    EventType.DISTANT_LEARNING.value: "Distance learning notice",
    # Attendance
    EventType.ARRIVAL_TO_SCHOOL.value: "Attendance check-in/out",
    EventType.EXCUSED_LESSON.value: "Absence excuse",
    EventType.STUDENT_ABSENT.value: "Student marked absent",
    # School events / calendar
    EventType.EVENT.value: "School calendar event",
    EventType.SCHOOL_EVENT.value: "School event",
    EventType.SCHOOL_TRIP.value: "School trip",
    EventType.EXCURSION.value: "Excursion",
    EventType.CULTURE.value: "Cultural event",
    EventType.CONTEST.value: "Contest",
    EventType.ALBUM.value: "Photo album",
    EventType.FREE_DAY.value: "Free day",
    EventType.HOLIDAY.value: "Holiday",
    EventType.SHORT_HOLIDAY.value: "Short holiday",
    EventType.PARENTS_EVENING.value: "Parent-teacher evening",
    EventType.CLASSIFICATION_MEETING.value: "Classification meeting",
    EventType.TEACHER_MEETING.value: "Teacher meeting",
    EventType.CLASS_TEACHER_EVENT.value: "Class teacher event",
    EventType.CLASS_BOOK.value: "Class book entry",
    EventType.SAFETY_INSTRUCTIONING.value: "Safety instruction briefing",
    EventType.PROJECT.value: "Project",
    EventType.PROCESS.value: "Administrative process",
    EventType.REPRESENTATION.value: "Representation (competition/event)",
    EventType.CONFIRMATION.value: "Confirmation request",
    # Canteen
    EventType.FOOD_CREDIT.value: "Canteen account credit",
    EventType.FOOD_SERVED.value: "Meal served",
    EventType.NEW_MENU.value: "New canteen menu",
}
# EventType has ~70 members in total; anything starting with H_ (e.g.
# h_clearcache, h_settings, h_userphoto) is an internal EduPage system/cache
# event and is intentionally left unlabeled here - it won't normally appear
# in a user-facing notification feed. Unlabeled codes fall back to the raw
# code in describe_event_type below.


def serialize_event_type(event_type: EventType | None) -> str | None:
    if event_type is None:
        return None
    return event_type.value


def describe_event_type(event_type: EventType | None) -> str | None:
    if event_type is None:
        return None
    return EVENT_TYPE_LABELS.get(event_type.value, event_type.value)


def serialize_action(action: Action | tuple[int, int] | None) -> str | list[int] | None:
    if action is None:
        return None
    if isinstance(action, Action):
        return action.value
    return [action[0], action[1]]


def serialize_subject(subj: Subject) -> dict[str, object]:
    return {
        "subject_id": subj.subject_id,
        "name": subj.name,
        "short": subj.short,
    }


def serialize_classroom(room: Classroom) -> dict[str, object]:
    return {
        "classroom_id": room.classroom_id,
        "name": room.name,
        "short": room.short,
    }


def serialize_account(
    acc: EduStudent | EduTeacher | EduAccount | str,
) -> dict[str, object] | str:
    if isinstance(acc, str):
        return acc

    base: dict[str, object] = {
        "person_id": acc.person_id,
        "name": acc.name,
        "gender": serialize_gender(acc.gender),
        "in_school_since": serialize_datetime(acc.in_school_since),
        "account_type": acc.account_type.value,
    }

    if isinstance(acc, EduStudent):
        base["class_id"] = acc.class_id
        base["number_in_class"] = acc.number_in_class
        return base

    if isinstance(acc, EduTeacher):
        base["classroom_name"] = acc.classroom_name
        base["teacher_to"] = serialize_datetime(acc.teacher_to)
        return base

    return base


def serialize_class(cls: Class) -> dict[str, object]:
    return {
        "class_id": cls.class_id,
        "name": cls.name,
        "short": cls.short,
        "homeroom_teachers": (
            [serialize_account(t) for t in cls.homeroom_teachers]
            if cls.homeroom_teachers is not None
            else None
        ),
        "homeroom": serialize_classroom(cls.homeroom) if cls.homeroom is not None else None,
        "grade": cls.grade,
    }


def serialize_lesson(lesson: Lesson) -> dict[str, object]:
    return {
        "period": lesson.period,
        "start_time": serialize_time(lesson.start_time),
        "end_time": serialize_time(lesson.end_time),
        "duration": lesson.duration,
        "subject": serialize_subject(lesson.subject) if lesson.subject is not None else None,
        "classes": [serialize_class(c) for c in lesson.classes] if lesson.classes is not None else None,
        "groups": list(lesson.groups) if lesson.groups is not None else None,
        "teachers": [serialize_account(t) for t in lesson.teachers] if lesson.teachers is not None else None,
        "classrooms": [serialize_classroom(r) for r in lesson.classrooms] if lesson.classrooms is not None else None,
        "curriculum": lesson.curriculum,
        "online_lesson_link": lesson.online_lesson_link,
        "is_cancelled": lesson.is_cancelled,
        "is_event": lesson.is_event,
    }


def serialize_timetable(timetable: Timetable) -> dict[str, object]:
    return {"lessons": [serialize_lesson(lesson) for lesson in timetable.lessons]}


def serialize_grade(grade: EduGrade) -> dict[str, object]:
    return {
        "event_id": grade.event_id,
        "title": grade.title,
        "grade_n": grade.grade_n,
        "comment": grade.comment,
        "date": serialize_datetime(grade.date),
        "subject_id": grade.subject_id,
        "subject_name": grade.subject_name,
        "teacher": serialize_account(grade.teacher) if grade.teacher is not None else None,
        "max_points": grade.max_points,
        "more_details": list(grade.more_details) if grade.more_details is not None else None,
        "importance": grade.importance,
        "verbal": grade.verbal,
        "percent": grade.percent,
        "class_grade_avg": grade.class_grade_avg,
    }


def serialize_timeline_event(event: TimelineEvent) -> dict[str, object]:
    return {
        "event_id": event.event_id,
        "timestamp": serialize_datetime(event.timestamp),
        "text": event.text,
        "author": serialize_account(event.author),
        "recipient": serialize_account(event.recipient),
        "event_type": serialize_event_type(event.event_type),
        "event_type_label": describe_event_type(event.event_type),
        "additional_data": event.additional_data,  # pyright: ignore[reportUnknownMemberType]
    }


def serialize_rating(rating: Rating) -> dict[str, object]:
    return {
        "quality_average": rating.quality_average,
        "quality_ratings": rating.quality_ratings,
        "quantity_average": rating.quantity_average,
        "quantity_ratings": rating.quantity_ratings,
    }


def serialize_menu(menu: Menu) -> dict[str, object]:
    return {
        "name": menu.name,
        "allergens": menu.allergens,
        "weight": menu.weight,
        "number": menu.number,
        "rating": serialize_rating(menu.rating) if menu.rating is not None else None,
    }


def serialize_meal(meal: Meal) -> dict[str, object]:
    return {
        "served_from": serialize_datetime(meal.served_from),
        "served_to": serialize_datetime(meal.served_to),
        "amount_of_foods": meal.amount_of_foods,
        "chooseable_menus": list(meal.chooseable_menus),
        "can_be_changed_until": serialize_datetime(meal.can_be_changed_until),
        "title": meal.title,
        "menus": [serialize_menu(menu) for menu in meal.menus],
        "date": serialize_datetime(meal.date),
        "ordered_meal": meal.ordered_meal,
        "meal_type": meal.meal_type.value,
    }


def serialize_meals(meals: Meals) -> dict[str, object]:
    return {
        "snack": serialize_meal(meals.snack) if meals.snack is not None else None,
        "lunch": serialize_meal(meals.lunch) if meals.lunch is not None else None,
        "afternoon_snack": (
            serialize_meal(meals.afternoon_snack)
            if meals.afternoon_snack is not None
            else None
        ),
    }


def serialize_timetable_change(change: TimetableChange) -> dict[str, object]:
    lesson_n: int | list[int]
    if isinstance(change.lesson_n, tuple):
        lesson_n = [change.lesson_n[0], change.lesson_n[1]]
    else:
        lesson_n = change.lesson_n

    return {
        "change_class": change.change_class,
        "lesson_n": lesson_n,
        "title": change.title,
        "action": serialize_action(change.action),
    }


def serialize_substitution(change: ParsedSubstitution) -> dict[str, object]:
    lesson_n: int | list[int]
    if isinstance(change.lesson_n, tuple):
        lesson_n = [change.lesson_n[0], change.lesson_n[1]]
    else:
        lesson_n = change.lesson_n

    return {
        "change_class": change.change_class,
        "lesson_n": lesson_n,
        "period_label": change.period_label,
        "subject": change.subject,
        "details": change.details,
        "action": serialize_action(change.action),
    }
