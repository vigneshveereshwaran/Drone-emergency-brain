"""
Tests for decision_engine/classifier.py
Validates severity, mission impact, dimensions, priority, and multi-failure escalation.
Includes mandatory Phase 2 Exit Gate verification.
"""

import pytest
from decision_engine.detector import FailureDetector
from decision_engine.classifier import FailureClassifier
from decision_engine.interfaces import SeverityLevel, ImpactLevel


@pytest.fixture
def detector():
    return FailureDetector()


@pytest.fixture
def classifier():
    return FailureClassifier()


def test_single_low_battery_classification(detector, classifier):
    """Low battery alone is classified as LOW severity and LOW impact."""
    telem = {
        "battery": 28.0,
        "gps_status": "CONNECTED",
        "communication": "CONNECTED",
        "position": [20.0, 70.0],
        "distance_to_home": 10.0,
        "battery_consumption_rate": 0.4
    }
    detections = detector.detect_failures(telem)
    classified, overall_sev, overall_imp, notes = classifier.evaluate(detections)

    assert len(classified) == 1
    assert classified[0].failure_type == "LOW_BATTERY"
    assert classified[0].severity == SeverityLevel.LOW.value
    assert classified[0].mission_impact == ImpactLevel.LOW.value
    assert overall_sev == SeverityLevel.LOW.value
    assert overall_imp == ImpactLevel.LOW.value


def test_multi_failure_escalates_by_one_level(detector, classifier):
    """
    Part K Rule: If two or more simultaneous failures exist:
    increase overall severity by one level.
    """
    # LOW_BATTERY (LOW) + GPS_DEGRADED (LOW) -> 2 failures -> Elevates to MEDIUM
    telem = {
        "battery": 28.0,
        "gps_status": "DEGRADED",
        "gps_accuracy": 22.0,
        "satellites": 4,
        "communication": "CONNECTED",
        "position": [20.0, 70.0],
        "distance_to_home": 10.0,
        "battery_consumption_rate": 0.4
    }
    detections = detector.detect_failures(telem)
    assert len(detections) == 2
    classified, overall_sev, overall_imp, notes = classifier.evaluate(detections)

    assert overall_sev == SeverityLevel.MEDIUM.value
    assert any("Multi-failure escalation" in n for n in notes)


def test_gps_loss_and_low_battery_compound_rule(detector, classifier):
    """
    Part K Rule: GPS LOSS + LOW BATTERY != GPS LOSS alone.
    Severity and impact are compounded.
    """
    telem = {
        "battery": 28.0,
        "gps_status": "LOST",
        "gps_accuracy": 99.0,
        "satellites": 0,
        "communication": "CONNECTED",
        "position": [20.0, 70.0],
        "distance_to_home": 10.0,
        "battery_consumption_rate": 0.4
    }
    detections = detector.detect_failures(telem)
    classified, overall_sev, overall_imp, notes = classifier.evaluate(detections)

    assert overall_sev in (SeverityLevel.HIGH.value, SeverityLevel.CRITICAL.value)
    assert any("GPS loss with reduced battery reserve" in n for n in notes)


def test_flagship_exit_gate_multi_failure(detector, classifier):
    """
    Mandatory Phase 2 Exit Gate Verification:
    GPS LOSS + COMM LOSS + BATTERY 18%
    MUST produce:
    - 3 failures
    - CRITICAL overall severity
    - CRITICAL mission impact
    """
    telem = {
        "battery": 18.0,                    # CRITICAL_BATTERY
        "gps_status": "LOST",               # GPS_FAILURE
        "gps_accuracy": 99.0,
        "satellites": 0,
        "communication": "LOST",            # COMMUNICATION_FAILURE
        "comm_loss_duration": 12.0,
        "position": [40.0, 60.0],
        "last_known_position": [40.0, 60.0],
        "distance_to_home": 30.0,
        "battery_consumption_rate": 0.4
    }

    detections = detector.detect_failures(telem)
    assert len(detections) == 3, f"Expected 3 detections, got {len(detections)}: {[d.type for d in detections]}"

    det_types = {d.type for d in detections}
    assert "GPS_FAILURE" in det_types
    assert "COMMUNICATION_FAILURE" in det_types
    assert "CRITICAL_BATTERY" in det_types

    classified, overall_sev, overall_imp, notes = classifier.evaluate(detections)

    assert overall_sev == SeverityLevel.CRITICAL.value, f"Expected CRITICAL severity, got {overall_sev}"
    assert overall_imp == ImpactLevel.CRITICAL.value, f"Expected CRITICAL impact, got {overall_imp}"
    assert any("Triple emergency failure" in n for n in notes)
