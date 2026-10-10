"""Tests for multi-user event assignment and role-based visibility.

Validates:
- An event can be assigned to multiple users (assigned_user_ids).
- Administrators see every upcoming scheduled event regardless of assignment.
- A non-admin member sees public events (no assignees) and events assigned to
  them, but NOT events assigned only to other users.
- The create/update endpoints accept and return assigned_user_ids and reject
  non-existent user ids.
"""
import pytest
from datetime import datetime, timedelta, timezone

from app.models import User, UserRole, Event, EventStatus, EventAssignment
from app.auth.password import hash_password
from app.auth.token import create_access_token


def _make_user(db_session, email, role=UserRole.MEMBER):
    user = User(
        email=email,
        password_hash=hash_password("SecurePass123"),
        first_name=email.split("@")[0],
        last_name="User",
        role=role,
        is_email_verified=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _headers(user):
    return {"Authorization": f"Bearer {create_access_token({'sub': str(user.id)})}"}


@pytest.fixture
def admin(db_session):
    return _make_user(db_session, "admin@example.com", UserRole.ADMINISTRATOR)


@pytest.fixture
def alice(db_session):
    return _make_user(db_session, "alice@example.com")


@pytest.fixture
def bob(db_session):
    return _make_user(db_session, "bob@example.com")


def _future(days):
    return datetime.now(timezone.utc) + timedelta(days=days)


def _make_event(db_session, creator, title, assignees=()):
    event = Event(
        title=title,
        description="desc",
        start_date=_future(2),
        end_date=_future(3),
        location="Somewhere",
        created_by=creator.id,
        status=EventStatus.SCHEDULED,
    )
    db_session.add(event)
    db_session.flush()
    for u in assignees:
        db_session.add(EventAssignment(event_id=event.id, user_id=u.id))
    if assignees:
        event.assigned_user_id = assignees[0].id
    db_session.commit()
    db_session.refresh(event)
    return event


def test_create_event_with_multiple_assignees(client, db_session, admin, alice, bob):
    """Admin can create an event assigned to multiple users."""
    payload = {
        "title": "Multi assignment",
        "description": "d",
        "start_date": _future(5).isoformat(),
        "end_date": _future(6).isoformat(),
        "location": "HQ",
        "assigned_user_ids": [str(alice.id), str(bob.id)],
    }
    resp = client.post("/api/events", json=payload, headers=_headers(admin))
    assert resp.status_code == 201, resp.text
    event = resp.json()["event"]
    returned = set(event["assigned_user_ids"])
    assert returned == {str(alice.id), str(bob.id)}

    # Persisted join rows match.
    rows = db_session.query(EventAssignment).filter(
        EventAssignment.event_id == event["id"]
    ).all()
    assert {str(r.user_id) for r in rows} == {str(alice.id), str(bob.id)}


def test_create_event_rejects_unknown_assignee(client, admin, alice):
    """A non-existent assignee id yields 400 and creates no event."""
    import uuid
    payload = {
        "title": "Bad assignee",
        "start_date": _future(5).isoformat(),
        "end_date": _future(6).isoformat(),
        "assigned_user_ids": [str(alice.id), str(uuid.uuid4())],
    }
    resp = client.post("/api/events", json=payload, headers=_headers(admin))
    assert resp.status_code == 400
    assert resp.json()["detail"]["error"]["code"] == "INVALID_ASSIGNED_USER"


def test_admin_sees_all_events(client, db_session, admin, alice, bob):
    """Admin sees public and privately-assigned events regardless of assignee."""
    _make_event(db_session, admin, "Public event")
    _make_event(db_session, admin, "Alice event", assignees=[alice])
    _make_event(db_session, admin, "Bob event", assignees=[bob])

    resp = client.get("/api/events", headers=_headers(admin))
    assert resp.status_code == 200
    titles = {e["title"] for e in resp.json()["events"]}
    assert {"Public event", "Alice event", "Bob event"} <= titles


def test_member_sees_public_and_own_assignments_only(client, db_session, admin, alice, bob):
    """Alice sees public events and events assigned to her, not Bob-only ones."""
    _make_event(db_session, admin, "Public event")
    _make_event(db_session, admin, "Alice event", assignees=[alice])
    _make_event(db_session, admin, "Shared event", assignees=[alice, bob])
    _make_event(db_session, admin, "Bob event", assignees=[bob])

    resp = client.get("/api/events", headers=_headers(alice))
    assert resp.status_code == 200
    titles = {e["title"] for e in resp.json()["events"]}
    assert "Public event" in titles
    assert "Alice event" in titles
    assert "Shared event" in titles
    assert "Bob event" not in titles


def test_update_event_replaces_assignees(client, db_session, admin, alice, bob):
    """Updating assigned_user_ids replaces the assignment set."""
    event = _make_event(db_session, admin, "To update", assignees=[alice])
    resp = client.put(
        f"/api/events/{event.id}",
        json={"assigned_user_ids": [str(bob.id)]},
        headers=_headers(admin),
    )
    assert resp.status_code == 200, resp.text
    assert set(resp.json()["assigned_user_ids"]) == {str(bob.id)}

    rows = db_session.query(EventAssignment).filter(
        EventAssignment.event_id == event.id
    ).all()
    assert {str(r.user_id) for r in rows} == {str(bob.id)}


def test_update_event_clears_assignees_makes_public(client, db_session, admin, alice, bob):
    """Sending an empty assigned_user_ids clears assignment -> public event."""
    event = _make_event(db_session, admin, "Clear me", assignees=[alice])
    resp = client.put(
        f"/api/events/{event.id}",
        json={"assigned_user_ids": []},
        headers=_headers(admin),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["assigned_user_ids"] == []

    # Now visible to an unrelated member because it is public.
    resp2 = client.get("/api/events", headers=_headers(bob))
    titles = {e["title"] for e in resp2.json()["events"]}
    assert "Clear me" in titles
