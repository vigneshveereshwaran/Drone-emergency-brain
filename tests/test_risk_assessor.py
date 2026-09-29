"""
Tests for decision_engine/risk_assessor.py
Validates Part L transparent risk scoring, point breakdowns, and risk band mapping.
"""

import pytest
from decision_engine.detector import FailureDetector
from decision_engine.risk_assessor import RiskAssessor


@pytest.fixture
def detector():
    return FailureDetector()


@pytest.fixture
def risk_assessor():
    return RiskAssessor()


def test_zero_risk_on_clean_telemetry(detector, risk_assessor):
    """Healthy telemetry produces 0 risk points and LOW risk."""
    telem = {
        "battery": 90.0,
        "gps_status": "CONNECTED",
        "gps_accuracy": 3.0,
        "satellites": 10,
        "communication": "CONNECTED",
        "position": [15.0, 75.0]
    }
    detections = detector.detect_failures(telem)
    result = risk_assessor.assess_risk(telem, detections)

    assert result.total_score == 0
    assert result.overall_risk == "LOW"
    assert len(result.factors) == 0


def test_high_risk_flagship_scenario(detector, risk_assessor):
    """
    Part L Example:
    GPS LOST (+3) + Restricted Zone (+3) = Total Risk 6 -> HIGH.
    """
    telem = {
        "battery": 80.0,
        "gps_status": "LOST",
        "gps_accuracy": 99.0,
        "satellites": 0,
        "communication": "CONNECTED",
        "position": [50.0, 50.0],           # Inside restricted zone
        "last_known_position": [50.0, 50.0]
    }
    detections = detector.detect_failures(telem)
    result = risk_assessor.assess_risk(telem, detections)

    assert result.total_score == 6
    assert result.overall_risk == "HIGH"
    factors = {f.factor: f.points for f in result.factors}
    assert factors.get("Navigation Risk (GPS Lost)") == 3
    assert factors.get("Legal Risk (Restricted Airspace)") == 3


def test_critical_risk_multi_failure(detector, risk_assessor):
    """
    Multi-failure:
    CRITICAL_BATTERY (3) + GPS_LOST (3) + COMM_LOST (2) + LONG_COMM (1) = 9 points -> CRITICAL.
    """
    telem = {
        "battery": 18.0,
        "gps_status": "LOST",
        "gps_accuracy": 99.0,
        "satellites": 0,
        "communication": "LOST",
        "comm_loss_duration": 8.0,          # > 5s -> triggers additional point
        "position": [30.0, 70.0],
        "last_known_position": [30.0, 70.0],
        "distance_to_home": 20.0
    }
    detections = detector.detect_failures(telem)
    result = risk_assessor.assess_risk(telem, detections)

    assert result.total_score == 9
    assert result.overall_risk == "CRITICAL"
    factor_names = [f.factor for f in result.factors]
    assert "Battery Risk (Critical)" in factor_names
    assert "Navigation Risk (GPS Lost)" in factor_names
    assert "Communication Risk" in factor_names
    assert "Communication Risk (Prolonged)" in factor_names
