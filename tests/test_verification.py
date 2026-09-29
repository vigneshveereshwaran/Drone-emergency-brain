"""
Tests for decision_engine/verifier.py
Part 6 (Third Absolute Rule): Verification must never assume success.
Part R: Validates HOVER, RELOCATE, RETURN_TO_HOME, GPS_RESTORE, COMM_RESTORE, and intentional failure.
"""

import pytest
import config
from decision_engine.verifier import RecoveryVerifier
from decision_engine.interfaces import VerificationStatus


@pytest.fixture
def verifier():
    return RecoveryVerifier()


def test_verify_hover_success(verifier):
    """Hover succeeds when stationary, at target, in legal airspace."""
    telem = {
        "position": [36.0, 66.0],
        "speed": 0.0,
        "unauthorized_movement": False,
        "timestamp": 25.0
    }
    res = verifier.verify_hover(telem, target_pos=[36.0, 66.0])
    assert res.status == VerificationStatus.SUCCESS.value
    assert res.checks["target_reached"] == "PASS"
    assert res.checks["speed_zero"] == "PASS"
    assert res.checks["position_legal"] == "PASS"


def test_verify_hover_failure_target_not_reached(verifier):
    """Hover FAILS if drone is not at commanded target station."""
    telem = {
        "position": [45.0, 60.0],  # 11 units away from [36, 66]
        "speed": 0.0,
        "unauthorized_movement": False
    }
    res = verifier.verify_hover(telem, target_pos=[36.0, 66.0])
    assert res.status == VerificationStatus.FAILED.value
    assert res.checks["target_reached"] == "FAIL"


def test_verify_hover_failure_in_restricted_airspace(verifier):
    """Hover FAILS if drone attempts to hover inside restricted airspace."""
    telem = {
        "position": [50.0, 50.0],  # Restricted airspace
        "speed": 0.0,
        "unauthorized_movement": False
    }
    res = verifier.verify_hover(telem, target_pos=[50.0, 50.0])
    assert res.status == VerificationStatus.FAILED.value
    assert res.checks["position_legal"] == "FAIL"


def test_verify_relocation_success(verifier):
    """Relocation succeeds when target reached with battery above safety reserve."""
    target = [36.0, 66.0]
    telem = {
        "position": [36.0, 66.0],
        "battery": 75.0,
        "obstacle_detected": False
    }
    res = verifier.verify_relocation(telem, target)
    assert res.status == VerificationStatus.SUCCESS.value
    assert res.checks["battery_sufficient"] == "PASS"
    assert res.checks["destination_legal"] == "PASS"


def test_verify_relocation_failure_low_battery(verifier):
    """Relocation FAILS if battery dips below safety reserve."""
    target = [36.0, 66.0]
    telem = {
        "position": [36.0, 66.0],
        "battery": 6.0,  # Below 10% safety reserve
        "obstacle_detected": False
    }
    res = verifier.verify_relocation(telem, target)
    assert res.status == VerificationStatus.FAILED.value
    assert res.checks["battery_sufficient"] == "FAIL"


def test_verify_return_to_home_success(verifier):
    """RTH succeeds when home reached, altitude 0, landed."""
    telem = {
        "position": config.START,
        "home": config.START,
        "battery": 25.0,
        "altitude": 0.0,
        "flight_mode": "LANDED"
    }
    res = verifier.verify_return_home(telem)
    assert res.status == VerificationStatus.SUCCESS.value
    assert res.checks["home_reached"] == "PASS"
    assert res.checks["safe_touchdown"] == "PASS"


def test_verify_gps_restoration(verifier):
    """GPS restoration verifies 3D lock, accuracy, and minimum satellites."""
    healthy = {
        "gps_status": "CONNECTED",
        "gps_accuracy": 3.5,
        "satellites": 10
    }
    assert verifier.verify_gps_restoration(healthy).status == VerificationStatus.SUCCESS.value

    unlocked = {
        "gps_status": "LOST",
        "gps_accuracy": 99.0,
        "satellites": 0
    }
    assert verifier.verify_gps_restoration(unlocked).status == VerificationStatus.FAILED.value


def test_verify_communication_restoration(verifier):
    """Communication restoration verifies connected link and heartbeat."""
    connected = {"communication": "CONNECTED", "heartbeat": True}
    assert verifier.verify_communication_restoration(connected).status == VerificationStatus.SUCCESS.value

    disconnected = {"communication": "LOST", "heartbeat": False}
    assert verifier.verify_communication_restoration(disconnected).status == VerificationStatus.FAILED.value


def test_intentional_failing_verification_demonstrated(verifier):
    """
    Mandatory Phase 4 Exit Gate requirement:
    Demonstrate that verification does not assume success and explicitly catches failures.
    """
    bad_telemetry = {
        "position": [85.0, 85.0],
        "speed": 4.5,
        "battery": 3.0,
        "unauthorized_movement": True
    }
    res = verifier.verify_hover(bad_telemetry, target_pos=[36.0, 66.0])
    assert res.status == VerificationStatus.FAILED.value
    assert res.checks["target_reached"] == "FAIL"
    assert res.checks["station_holding_secure"] == "FAIL"
