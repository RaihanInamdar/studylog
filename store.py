"""In-memory data store for study sessions and weekly goals.

Thread-safe implementation using a threading.Lock to protect shared state.
No external database or disk persistence is used.
"""

from datetime import date, timedelta
import threading
from typing import Any, Dict, List, Optional, Tuple

# Thread lock protecting concurrent access to in-memory collections
_lock = threading.Lock()

# Internal in-memory storage structures
_sessions: List[Dict[str, Any]] = []
_goals: Dict[str, float] = {}


def reset_store() -> None:
    """Clear all sessions and goals from memory."""
    with _lock:
        _sessions.clear()
        _goals.clear()


def load_sample_data() -> None:
    """Populate store with sample sessions and weekly goals.

    Clears existing store first to prevent duplicate records when re-seeded.
    Sample session dates are guaranteed to be within the current week (Monday to today)
    and never in the future.
    """
    with _lock:
        _sessions.clear()
        _goals.clear()

        today = date.today()
        days_since_monday = today.weekday()  # 0 = Monday, ..., 6 = Sunday
        monday = today - timedelta(days=days_since_monday)

        # Helper to pick a safe date between Monday and today
        def calc_date(offset_from_mon: int) -> str:
            safe_offset = min(offset_from_mon, days_since_monday)
            return (monday + timedelta(days=safe_offset)).isoformat()

        # 5 sample sessions across 3 subjects
        sample_sessions = [
            {"subject": "Cloud Computing", "hours": 3.5, "date": calc_date(0)},
            {"subject": "Mathematics", "hours": 2.0, "date": calc_date(1)},
            {"subject": "Cloud Computing", "hours": 2.5, "date": calc_date(2)},
            {"subject": "Physics", "hours": 3.0, "date": calc_date(3)},
            {"subject": "Mathematics", "hours": 1.5, "date": calc_date(4)},
        ]
        _sessions.extend(sample_sessions)

        # 1 weekly goal per subject
        _goals.update({
            "Cloud Computing": 10.0,
            "Mathematics": 8.0,
            "Physics": 6.0,
        })


def add_session(subject: str, hours: float, session_date: str) -> Dict[str, Any]:
    """Add a validated study session to in-memory store."""
    record = {
        "subject": subject.strip(),
        "hours": round(float(hours), 2),
        "date": session_date.strip(),
    }
    with _lock:
        _sessions.append(record)
    return dict(record)


def get_all_sessions() -> List[Dict[str, Any]]:
    """Return all study sessions ordered newest first (by date)."""
    with _lock:
        records = [dict(s) for s in _sessions]
    # Sort newest first by date string (YYYY-MM-DD)
    records.sort(key=lambda s: s["date"], reverse=True)
    return records


def set_goal(subject: str, goal_hours: float) -> None:
    """Set or update weekly goal for a given subject."""
    clean_subj = subject.strip()
    with _lock:
        _goals[clean_subj] = round(float(goal_hours), 2)


def get_goals() -> Dict[str, float]:
    """Return a copy of all weekly goals."""
    with _lock:
        return dict(_goals)


def get_subject_summary() -> Dict[str, float]:
    """Return total study hours aggregated across all sessions per subject."""
    summary: Dict[str, float] = {}
    with _lock:
        for s in _sessions:
            subj = s["subject"]
            summary[subj] = round(summary.get(subj, 0.0) + s["hours"], 2)
    return summary


def get_current_week_range() -> Tuple[date, date]:
    """Return Monday and Sunday dates for the current calendar week."""
    today = date.today()
    monday = today - timedelta(days=today.weekday())
    sunday = monday + timedelta(days=6)
    return monday, sunday


def get_weekly_summary() -> Dict[str, float]:
    """Return study hours logged in current calendar week (Monday to Sunday) per subject."""
    monday, sunday = get_current_week_range()
    weekly_hours: Dict[str, float] = {}
    with _lock:
        for s in _sessions:
            try:
                s_date = date.fromisoformat(s["date"])
            except ValueError:
                continue
            if monday <= s_date <= sunday:
                subj = s["subject"]
                weekly_hours[subj] = round(weekly_hours.get(subj, 0.0) + s["hours"], 2)
    return weekly_hours


def get_weekly_progress() -> List[Dict[str, Any]]:
    """Combine weekly goals with weekly logged hours to compute progress bars.

    Returns list of dicts with subject, goal, logged, percentage, and achieved flag.
    """
    weekly_logged = get_weekly_summary()
    goals = get_goals()

    # Collect union of subjects from goals and logged sessions
    subjects = sorted(set(list(goals.keys()) + list(weekly_logged.keys())))
    progress_list = []

    for subj in subjects:
        goal = goals.get(subj, 0.0)
        logged = weekly_logged.get(subj, 0.0)
        if goal > 0:
            pct = round((logged / goal) * 100.0, 1)
        else:
            pct = 0.0
        capped_pct = min(pct, 100.0)
        progress_list.append({
            "subject": subj,
            "goal": goal,
            "logged": logged,
            "percentage": pct,
            "capped_percentage": capped_pct,
            "achieved": goal > 0 and logged >= goal,
        })
    return progress_list


def get_most_studied_subject() -> Optional[Tuple[str, float]]:
    """Return the subject with maximum total hours logged, or None if empty."""
    summary = get_subject_summary()
    if not summary:
        return None
    sorted_subjects = sorted(summary.items(), key=lambda item: item[1], reverse=True)
    return sorted_subjects[0]
