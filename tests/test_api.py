"""
Full REST API Test Suite for Autonomous Drone Emergency Brain.
Phase 5 Exit Gate validations:
- start, pause, reset endpoints
- telemetry, state, events, decision, map endpoints
- scenario fault injection endpoints
- demo runners
- invalid configuration / bad requests
- API failure handling
- CRITICAL TEST: Scenario endpoint cannot directly invoke recovery!
"""

import pytest
from app import create_app
import config


@pytest.fixture
def client(tmp_path):
    test_db = str(tmp_path / "test_api_mission.db")
    app = create_app({"TESTING": True, "DB_PATH": test_db})
    with app.test_client() as client:
        yield client


def test_index_route(client):
    """GET / serves command center HTML."""
    res = client.get("/")
    assert res.status_code == 200
    assert "AUTONOMOUS DRONE EMERGENCY BRAIN" in res.get_data(as_text=True)


def test_get_state_and_telemetry(client):
    """GET /api/state and GET /api/telemetry return valid schema."""
    state_res = client.get("/api/state")
    assert state_res.status_code == 200
    state_json = state_res.get_json()
    assert state_json["ok"] is True
    assert state_json["data"]["state"] == "READY"
    assert "mission_id" in state_json["data"]

    telem_res = client.get("/api/telemetry")
    assert telem_res.status_code == 200
    telem_json = telem_res.get_json()
    assert telem_json["ok"] is True
    assert telem_json["data"]["battery"] == 100.0
    assert telem_json["data"]["gps_status"] == "CONNECTED"
    assert telem_json["data"]["position"] == config.START


def test_get_map_metadata(client):
    """GET /api/map returns coordinates and zone definitions."""
    res = client.get("/api/map")
    assert res.status_code == 200
    data = res.get_json()["data"]
    assert data["map_size"] == 100
    assert data["start"] == config.START
    assert data["destination"] == config.DESTINATION
    assert "restricted_airspace" in data
    assert "legal_hover_zones" in data
    assert len(data["legal_hover_zones"]) == 4


def test_get_events_and_decision(client):
    """GET /api/events and GET /api/decision return structured data."""
    events_res = client.get("/api/events")
    assert events_res.status_code == 200
    assert events_res.get_json()["ok"] is True
    assert isinstance(events_res.get_json()["data"], list)

    dec_res = client.get("/api/decision")
    assert dec_res.status_code == 200
    dec_json = dec_res.get_json()["data"]
    assert "decision" in dec_json
    assert "risk" in dec_json
    assert "detections" in dec_json


def test_mission_lifecycle_endpoints(client):
    """POST /api/mission/start, pause, reset."""
    # Start
    start_res = client.post("/api/mission/start")
    assert start_res.status_code == 200
    assert start_res.get_json()["ok"] is True

    # Check state is MISSION_ACTIVE
    state = client.get("/api/state").get_json()["data"]
    assert state["state"] == "MISSION_ACTIVE"
    assert state["is_running"] is True

    # Pause
    pause_res = client.post("/api/mission/pause")
    assert pause_res.status_code == 200
    state = client.get("/api/state").get_json()["data"]
    assert state["is_running"] is False

    # Reset
    reset_res = client.post("/api/mission/reset")
    assert reset_res.status_code == 200
    state = client.get("/api/state").get_json()["data"]
    assert state["state"] == "READY"


def test_all_scenario_fault_injection_endpoints(client):
    """Tests all scenario fault injection and restoration endpoints."""
    endpoints = [
        ("/api/scenario/gps-loss", "gps_status", "LOST"),
        ("/api/scenario/gps-restore", "gps_status", "CONNECTED"),
        ("/api/scenario/gps-degrade", "gps_status", "DEGRADED"),
        ("/api/scenario/low-battery", "battery", 28.0),
        ("/api/scenario/critical-battery", "battery", 18.0),
        ("/api/scenario/communication-loss", "communication", "LOST"),
        ("/api/scenario/communication-restore", "communication", "CONNECTED"),
        ("/api/scenario/obstacle", "obstacle_detected", True),
        ("/api/scenario/obstacle-clear", "obstacle_detected", False),
        ("/api/scenario/unauthorized-movement", "unauthorized_movement", True),
        ("/api/scenario/multi-failure", "battery", 18.0),
        ("/api/scenario/reset", "battery", 100.0),
    ]

    for endpoint, key, expected in endpoints:
        res = client.post(endpoint)
        assert res.status_code == 200, f"Endpoint {endpoint} failed"
        assert res.get_json()["ok"] is True
        telem = client.get("/api/telemetry").get_json()["data"]
        assert telem[key] == expected, f"{endpoint} did not set {key} to {expected}, got {telem[key]}"


def test_critical_architecture_scenario_cannot_directly_invoke_recovery(client):
    """
    CRITICAL ARCHITECTURE TEST:
    Verify that scenario endpoints modify ONLY simulated conditions
    and NEVER directly invoke recovery!
    """
    # Put drone in MISSION mode
    client.post("/api/mission/start")
    telem_before = client.get("/api/telemetry").get_json()["data"]
    assert telem_before["flight_mode"] == "MISSION"

    # Inject GPS loss via scenario endpoint
    res = client.post("/api/scenario/gps-loss")
    assert res.status_code == 200
    assert res.get_json()["ok"] is True

    # Telemetry condition changed to LOST
    telem_after = client.get("/api/telemetry").get_json()["data"]
    assert telem_after["gps_status"] == "LOST"

    # Crucial check: The endpoint itself did NOT immediately flip flight mode to RELOCATING or RETURNING!
    # Recovery must only be commanded by the Emergency Brain pipeline, not by the button endpoint!
    assert telem_after["flight_mode"] == "MISSION"


def test_simulation_speed_endpoint(client):
    """POST /api/simulation/speed validation."""
    # Valid speeds
    for s in (1.0, 2.0, 4.0):
        res = client.post("/api/simulation/speed", json={"speed": s})
        assert res.status_code == 200
        assert res.get_json()["ok"] is True
        assert res.get_json()["data"]["speed"] == s

    # Invalid speed
    bad_res = client.post("/api/simulation/speed", json={"speed": 10.0})
    assert bad_res.status_code == 400
    assert bad_res.get_json()["ok"] is False


def test_demo_scenario_runners(client):
    """POST /api/demo/<scenario> runs end-to-end demonstrations."""
    demos = ["flagship", "critical-battery", "obstacle", "multi-failure", "unauthorized-movement", "failing-verification"]
    for d in demos:
        res = client.post(f"/api/demo/{d}")
        assert res.status_code == 200, f"Demo {d} failed: {res.get_data(as_text=True)}"
        assert res.get_json()["ok"] is True

    # Unknown demo
    bad_res = client.post("/api/demo/unknown_scenario")
    assert bad_res.status_code == 400
    assert bad_res.get_json()["ok"] is False
    assert "Unknown demo scenario" in bad_res.get_json()["error"]


def test_error_handlers(client):
    """Standardized 404, 405 error responses."""
    # 404
    r404 = client.get("/api/nonexistent")
    assert r404.status_code == 404
    assert r404.get_json()["ok"] is False

    # 405 Method Not Allowed (e.g. GET on a POST-only endpoint)
    r405 = client.get("/api/mission/start")
    assert r405.status_code == 405
    assert r405.get_json()["ok"] is False
