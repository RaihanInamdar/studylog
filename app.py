"""Flask application module for StudyLog.

Provides server-rendered UI and JSON API endpoints for tracking study sessions,
monitoring weekly subject goals, and checking service health.
"""

from datetime import date
import os
from typing import Any, Dict
from flask import Flask, jsonify, redirect, render_template, request, url_for

import store
import os, sys


def get_git_version() -> str:
    """Return 7-character Git commit hash from Render env var, or fallback to 'local'."""
    commit_sha = os.environ.get("RENDER_GIT_COMMIT", "").strip()
    if commit_sha:
        return commit_sha[:7]
    return "local"


def create_app(seed_demo: bool = False) -> Flask:
    """Application factory for StudyLog Flask app.

    Args:
        seed_demo: If True, loads initial sample sessions and goals into memory.
                   Defaults to False so app starts fresh with no predefined data.
    """
    flask_app = Flask(__name__)

    if seed_demo:
        store.load_sample_data()

    def _render_home(error: str = "") -> Any:
        """Helper to render home page template with all current store data."""
        sessions = store.get_all_sessions()
        summary = store.get_subject_summary()
        total_hours = round(sum(s["hours"] for s in sessions), 1)
        weekly_progress = store.get_weekly_progress()
        monday, sunday = store.get_current_week_range()

        return render_template(
            "index.html",
            sessions=sessions,
            summary=summary,
            total_hours=total_hours,
            weekly_progress=weekly_progress,
            week_range=f"{monday.strftime('%b %d')} - {sunday.strftime('%b %d')}",
            most_studied=store.get_most_studied_subject(),
            version=get_git_version(),
            today=date.today().isoformat(),
            error=error,
        )

    @flask_app.route("/", methods=["GET"])
    def home() -> Any:
        """Render home dashboard."""
        return _render_home()

    @flask_app.route("/sessions", methods=["POST"])
    def add_session() -> Any:
        """Validate and add a new study session."""
        data: Dict[str, Any] = request.get_json(silent=True) if request.is_json else request.form

        # 1. Subject validation (2-50 chars, trimmed)
        raw_subject = data.get("subject", "")
        subject = raw_subject.strip() if isinstance(raw_subject, str) else ""
        if not subject or len(subject) < 2 or len(subject) > 50:
            msg = "Subject is required and must be between 2 and 50 characters."
            if request.is_json:
                return jsonify({"error": msg}), 400
            return _render_home(error=msg), 400

        # 2. Hours validation (number > 0 and <= 24)
        raw_hours = data.get("hours")
        try:
            hours = float(raw_hours)  # type: ignore[arg-type]
        except (ValueError, TypeError):
            msg = "Hours is required and must be a valid number."
            if request.is_json:
                return jsonify({"error": msg}), 400
            return _render_home(error=msg), 400

        if hours <= 0 or hours > 24:
            msg = "Hours must be greater than 0 and at most 24."
            if request.is_json:
                return jsonify({"error": msg}), 400
            return _render_home(error=msg), 400

        # 3. Date validation (YYYY-MM-DD, not in future)
        raw_date = data.get("date", "")
        date_str = raw_date.strip() if isinstance(raw_date, str) else ""
        try:
            parsed_date = date.fromisoformat(date_str)
        except (ValueError, TypeError):
            msg = "Date is required and must be in valid YYYY-MM-DD format."
            if request.is_json:
                return jsonify({"error": msg}), 400
            return _render_home(error=msg), 400

        if parsed_date > date.today():
            msg = "Session date cannot be in the future."
            if request.is_json:
                return jsonify({"error": msg}), 400
            return _render_home(error=msg), 400

        store.add_session(subject=subject, hours=hours, session_date=date_str)
        return redirect(url_for("home"))

    @flask_app.route("/goals", methods=["POST"])
    def set_goal() -> Any:
        """Validate and set or update weekly goal for a subject."""
        data: Dict[str, Any] = request.get_json(silent=True) if request.is_json else request.form

        raw_subject = data.get("subject", "")
        subject = raw_subject.strip() if isinstance(raw_subject, str) else ""
        if not subject or len(subject) < 2 or len(subject) > 50:
            msg = "Subject is required and must be between 2 and 50 characters."
            if request.is_json:
                return jsonify({"error": msg}), 400
            return _render_home(error=msg), 400

        raw_goal = data.get("goal_hours")
        try:
            goal_hours = float(raw_goal)  # type: ignore[arg-type]
        except (ValueError, TypeError):
            msg = "Goal hours must be a valid number."
            if request.is_json:
                return jsonify({"error": msg}), 400
            return _render_home(error=msg), 400

        if goal_hours <= 0:
            msg = "Weekly goal hours must be greater than 0."
            if request.is_json:
                return jsonify({"error": msg}), 400
            return _render_home(error=msg), 400

        store.set_goal(subject=subject, goal_hours=goal_hours)
        return redirect(url_for("home"))

    @flask_app.route("/seed", methods=["POST"])
    def seed() -> Any:
        """Reset and load sample sessions and goals into memory."""
        store.load_sample_data()
        return redirect(url_for("home"))

    @flask_app.route("/api/sessions", methods=["GET"])
    def api_sessions() -> Any:
        """Return JSON list of all study sessions (newest first)."""
        return jsonify(store.get_all_sessions()), 200

    @flask_app.route("/api/summary", methods=["GET"])
    def api_summary() -> Any:
        """Return JSON object of total study hours per subject."""
        return jsonify(store.get_subject_summary()), 200

    @flask_app.route("/health", methods=["GET"])
    def health() -> Any:
        """Health check endpoint for Docker and Render monitoring."""
        return jsonify({"status": "ok"}), 200

    return flask_app


# Module-level instance for gunicorn (gunicorn app:app) starts clean with no demo data
app = create_app(seed_demo=False)

if __name__ == "__main__":
    # Local development runner: bind to 0.0.0.0 and PORT env variable
    listen_port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=listen_port, debug=False)
