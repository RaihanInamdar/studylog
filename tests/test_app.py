"""Automated test suite for StudyLog Flask web application and APIs."""

from datetime import date, timedelta
from typing import Generator
import pytest
from app import create_app
import store


@pytest.fixture
def client() -> Generator:
    """Fixture to create a test client with an isolated, empty in-memory store."""
    flask_app = create_app(seed_demo=False)
    flask_app.config["TESTING"] = True
    store.reset_store()
    with flask_app.test_client() as test_client:
        yield test_client
    store.reset_store()


def test_health_check(client) -> None:
    """Test 1: GET /health returns HTTP 200 and {'status': 'ok'}."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}


def test_add_session_valid(client) -> None:
    """Test 2: POST /sessions with valid data adds a session and redirects."""
    today_str = date.today().isoformat()
    payload = {
        "subject": "Cloud Computing",
        "hours": "3.5",
        "date": today_str,
    }
    response = client.post("/sessions", data=payload, follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["Location"] in ["/", "http://localhost/"]

    api_resp = client.get("/api/sessions")
    assert api_resp.status_code == 200
    sessions = api_resp.get_json()
    assert len(sessions) == 1
    assert sessions[0]["subject"] == "Cloud Computing"
    assert sessions[0]["hours"] == 3.5
    assert sessions[0]["date"] == today_str


def test_add_session_empty_subject(client) -> None:
    """Test 3: POST /sessions with empty or missing subject returns HTTP 400."""
    payload = {
        "subject": "   ",
        "hours": "2.0",
        "date": date.today().isoformat(),
    }
    response = client.post("/sessions", data=payload)
    assert response.status_code == 400


def test_add_session_invalid_hours(client) -> None:
    """Test 4: POST /sessions with negative or zero hours returns HTTP 400."""
    today_str = date.today().isoformat()

    # Test with zero hours
    resp_zero = client.post("/sessions", data={
        "subject": "Physics",
        "hours": "0",
        "date": today_str,
    })
    assert resp_zero.status_code == 400

    # Test with negative hours
    resp_neg = client.post("/sessions", data={
        "subject": "Physics",
        "hours": "-2.5",
        "date": today_str,
    })
    assert resp_neg.status_code == 400


def test_api_summary_totals(client) -> None:
    """Test 5: GET /api/summary returns correct aggregated totals per subject."""
    today_str = date.today().isoformat()
    client.post("/sessions", data={"subject": "Math", "hours": "2.0", "date": today_str})
    client.post("/sessions", data={"subject": "Math", "hours": "3.5", "date": today_str})
    client.post("/sessions", data={"subject": "Physics", "hours": "1.5", "date": today_str})

    summary_resp = client.get("/api/summary")
    assert summary_resp.status_code == 200
    summary = summary_resp.get_json()
    assert summary.get("Math") == 5.5
    assert summary.get("Physics") == 1.5


def test_seed_sample_data(client) -> None:
    """Test 6: POST /seed loads 5 sample sessions and repeated calls do not duplicate."""
    # First seed
    seed_resp1 = client.post("/seed", follow_redirects=True)
    assert seed_resp1.status_code == 200

    sessions_resp1 = client.get("/api/sessions")
    assert sessions_resp1.status_code == 200
    sessions1 = sessions_resp1.get_json()
    assert len(sessions1) == 5

    # Second seed: must reset and not create duplicates
    seed_resp2 = client.post("/seed", follow_redirects=True)
    assert seed_resp2.status_code == 200

    sessions_resp2 = client.get("/api/sessions")
    assert sessions_resp2.status_code == 200
    sessions2 = sessions_resp2.get_json()
    assert len(sessions2) == 5


def test_add_session_future_date_rejected(client) -> None:
    """Additional Test: POST /sessions with a future date returns HTTP 400."""
    future_date = (date.today() + timedelta(days=2)).isoformat()
    payload = {
        "subject": "DevOps",
        "hours": "2.0",
        "date": future_date,
    }
    response = client.post("/sessions", data=payload)
    assert response.status_code == 400


def test_set_weekly_goal_valid(client) -> None:
    """Additional Test: POST /goals with valid data stores the weekly goal."""
    response = client.post("/goals", data={
        "subject": "Cloud Computing",
        "goal_hours": "12.0",
    }, follow_redirects=False)
    assert response.status_code == 302
    assert store.get_goals().get("Cloud Computing") == 12.0
