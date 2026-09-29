"""
Tests for decision_engine/detector.py
Validates detection of all 9 failure modes with proper structured evidence.
"""

import pytest
import config
from decision_engine.detector import FailureDetector


@pytest.fixture
def detector():
    return FailureDetector()


def test_clean_telemetry_no_detections(detector):
    """Healthy telemetry produces zero failures."""
    telem = {
        "battery": 95.0,
        "gps_status": "CONNECTED",
        "gps_accuracy": 3.0,
        "satellites": 12,
        "communication": "CONNECTED",
        "comm_loss_duration": 0.0,
        "obstacle_detected": False,
        "unauthorized_movement": False,
        "theft_detected": False,
        "position": [15.0, 75.0],
        "last_known_position": [15.0, 75.0],
        "distance_to_home": 5.0,
        "battery_consumption_rate": 0.4
    }
    detections = detector.detect_failures(telem)
    assert len(detections) == 0


def test_detect_gps_loss(detector):
    """Detects GPS failure when status is LOST."""
    telem = {
        "battery": 80.0,
        "gps_status": "LOST",
        "gps_accuracy": 99.0,
        "satellites": 0,
        "communication": "CONNECTED",
        "position": [20.0, 70.0],
        "last_known_position": [20.0, 70.0]
    }
    detections = detector.detect_failures(telem)
    types = [d.type for d in detections]
    assert "GPS_FAILURE" in types
    gps_det = next(d for d in detections if d.type == "GPS_FAILURE")
    assert any("LOST" in ev for ev in gps_det.evidence)


def test_detect_gps_degraded(detector):
    """Detects GPS degraded if accuracy > threshold or satellites < 6."""
    telem = {
        "battery": 80.0,
        "gps_status": "DEGRADED",
        "gps_accuracy": 20.0,  # exceeds 15m threshold
        "satellites": 4,        # below 6 min satellites
        "communication": "CONNECTED",
        "position": [20.0, 70.0],
        "last_known_position": [20.0, 70.0]
    }
    detections = detector.detect_failures(telem)
    types = [d.type for d in detections]
    assert "GPS_DEGRADED" in types


def test_detect_battery_levels(detector):
    """Detects low battery (<= 30%) and critical battery (<= 20%)."""
    # 1. Low battery
    telem_low = {
        "battery": 28.0,
        "gps_status": "CONNECTED",
        "communication": "CONNECTED",
        "position": [20.0, 70.0],
        "last_known_position": [20.0, 70.0],
        "distance_to_home": 10.0,
        "battery_consumption_rate": 0.4
    }
    det_low = detector.detect_failures(telem_low)
    assert "LOW_BATTERY" in [d.type for d in det_low]
    assert "CRITICAL_BATTERY" not in [d.type for d in det_low]

    # 2. Critical battery
    telem_crit = dict(telem_low, battery=18.0)
    det_crit = detector.detect_failures(telem_crit)
    assert "CRITICAL_BATTERY" in [d.type for d in det_crit]
    assert "LOW_BATTERY" not in [d.type for d in det_crit]


def test_detect_battery_insufficient_for_rth(detector):
    """
    Even if battery is 35% (> critical threshold 20%), if distance to home requires
    more energy than available + reserve, it must trigger CRITICAL_BATTERY.
    Distance 80 units * 0.4% = 32% + 10% reserve = 42% > 35%.
    """
    telem = {
        "battery": 35.0,
        "gps_status": "CONNECTED",
        "communication": "CONNECTED",
        "position": [70.0, 30.0],
        "last_known_position": [70.0, 30.0],
        "distance_to_home": 80.0,
        "battery_consumption_rate": 0.4
    }
    detections = detector.detect_failures(telem)
    assert "CRITICAL_BATTERY" in [d.type for d in detections]


def test_detect_communication_failure(detector):
    """Detects communication failure and records duration."""
    telem = {
        "battery": 80.0,
        "gps_status": "CONNECTED",
        "communication": "LOST",
        "comm_loss_duration": 8.5,
        "position": [20.0, 70.0],
        "last_known_position": [20.0, 70.0]
    }
    detections = detector.detect_failures(telem)
    types = [d.type for d in detections]
    assert "COMMUNICATION_FAILURE" in types
    comm_det = next(d for d in detections if d.type == "COMMUNICATION_FAILURE")
    assert any("8.5" in ev for ev in comm_det.evidence)


def test_detect_obstacle(detector):
    """Detects obstacle on active corridor."""
    telem = {
        "battery": 80.0,
        "gps_status": "CONNECTED",
        "communication": "CONNECTED",
        "obstacle_detected": True,
        "position": [40.0, 50.0],
        "last_known_position": [40.0, 50.0]
    }
    detections = detector.detect_failures(telem)
    assert "OBSTACLE_DETECTED" in [d.type for d in detections]


def test_detect_restricted_airspace(detector):
    """Detects restricted airspace when position is [50, 50]."""
    telem = {
        "battery": 80.0,
        "gps_status": "CONNECTED",
        "communication": "CONNECTED",
        "position": [50.0, 50.0],
        "last_known_position": [50.0, 50.0]
    }
    detections = detector.detect_failures(telem)
    assert "RESTRICTED_ZONE" in [d.type for d in detections]


def test_detect_unauthorized_movement(detector):
    """Detects unauthorized movement and theft."""
    telem = {
        "battery": 80.0,
        "gps_status": "CONNECTED",
        "communication": "CONNECTED",
        "unauthorized_movement": True,
        "theft_detected": True,
        "position": [25.0, 60.0],
        "last_known_position": [25.0, 60.0]
    }
    detections = detector.detect_failures(telem)
    types = [d.type for d in detections]
    assert "UNAUTHORIZED_MOVEMENT" in types
    assert "THEFT_DETECTED" in types
