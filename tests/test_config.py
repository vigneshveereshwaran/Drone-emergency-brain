"""
Tests for config.py validation and parameter invariants.
"""

import pytest
import config


def test_default_config_valid():
    """Default configuration must pass startup validation."""
    assert config.validate_config() is True


def test_battery_invariants():
    """Battery hierarchy must satisfy 0 < safety_reserve < critical < low < initial."""
    assert 0 < config.SAFETY_RESERVE < config.CRITICAL_BATTERY_THRESHOLD
    assert config.CRITICAL_BATTERY_THRESHOLD < config.LOW_BATTERY_THRESHOLD
    assert config.LOW_BATTERY_THRESHOLD < config.INITIAL_BATTERY


def test_risk_points_coverage():
    """Verify all mandated risk scoring factors are configured."""
    required_factors = [
        "LOW_BATTERY",
        "CRITICAL_BATTERY",
        "GPS_DEGRADED",
        "GPS_LOST",
        "COMMUNICATION_LOST",
        "LONG_COMM_LOSS",
        "OBSTACLE",
        "RESTRICTED_ZONE",
        "UNAUTHORIZED_MOVEMENT",
    ]
    for factor in required_factors:
        assert factor in config.RISK_POINTS
        assert config.RISK_POINTS[factor] > 0


def test_invalid_hover_zone_detected(monkeypatch):
    """If a legal hover zone is improperly placed inside restricted airspace, validation must fail."""
    bad_zones = [
        {"id": "HZ_BAD", "name": "Bad Zone inside Restricted", "center": [50.0, 50.0], "radius": 5.0}
    ]
    monkeypatch.setattr(config, "LEGAL_HOVER_ZONES", bad_zones)
    with pytest.raises(ValueError, match="overlaps"):
        config.validate_config()
