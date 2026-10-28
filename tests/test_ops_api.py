"""Smoke tests for the operations router and its session lifecycle."""

from thermalloop.app import app
from thermalloop.ops.api import (
    CreateSession,
    TickRequest,
    create_session,
    delete_session,
    events,
    meta,
    session_state,
    tick,
)


def test_operations_metadata_advertises_simulation_only():
    registered_paths = {route.path for route in app.routes}
    assert "/api/ops/meta" in registered_paths
    assert "/api/ops/session" in registered_paths
    assert "/api/ops/session/{session_id}/tick" in registered_paths
    data = meta()
    assert set(data["modes"]) == {"A", "B", "C"}
    assert len(data["agents"]) == 8
    assert data["real_device_enabled"] is False


def test_operations_session_lifecycle():
    session_id = create_session(CreateSession(mode="C", seed=7))["session_id"]

    reports = tick(session_id, TickRequest(steps=2))["reports"]
    assert len(reports) == 2
    assert reports[-1]["decisions"]

    assert session_state(session_id)["total_steps"] == 2

    assert events(session_id)["events"]

    assert delete_session(session_id)["deleted"] is True
