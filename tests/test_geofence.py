"""
Tests for simulator/geofence.py and airspace zone legality.
Validates Part E requirements:
- [50, 50] is inside restricted airspace
- HZ1, HZ2, HZ3, HZ4 are legal
- No legal hover zone overlaps restricted airspace or private property
"""

import pytest
import config
from simulator.geofence import GeofenceManager


@pytest.fixture
def geofence():
    return GeofenceManager()


def test_restricted_zone_at_50_50(geofence):
    """Exit Gate requirement: [50, 50] MUST be restricted airspace."""
    pos = [50.0, 50.0]
    assert geofence.is_in_restricted_zone(pos) is True
    assert geofence.get_zone_type(pos) == "RESTRICTED"


def test_private_property(geofence):
    """Checks private property detection (x: 68-82, y: 30-45)."""
    inside_pos = [75.0, 38.0]
    assert geofence.is_in_private_property(inside_pos) is True
    assert geofence.get_zone_type(inside_pos) == "PRIVATE"

    outside_pos = [65.0, 25.0]
    assert geofence.is_in_private_property(outside_pos) is False


def test_hz1_to_hz4_are_legal_and_non_overlapping(geofence):
    """Exit Gate requirement: HZ1-HZ4 are legal and do not overlap restricted or private zones."""
    for hz in config.LEGAL_HOVER_ZONES:
        center = hz["center"]
        radius = hz["radius"]

        # Center must be recognized as HOVER_ZONE
        zone_info = geofence.is_in_legal_hover_zone(center)
        assert zone_info is not None, f"Center of {hz['id']} not recognized as hover zone"
        assert zone_info["id"] == hz["id"]

        # Center must not be restricted or private
        assert not geofence.is_in_restricted_zone(center), f"{hz['id']} center is inside restricted zone"
        assert not geofence.is_in_private_property(center), f"{hz['id']} center is inside private property"

        # Check circle boundary samples to ensure whole radius is clear of restricted/private
        for zone in [config.RESTRICTED_AIRSPACE, config.PRIVATE_PROPERTY]:
            cx, cy = center
            closest_x = max(zone["x_min"], min(cx, zone["x_max"]))
            closest_y = max(zone["y_min"], min(cy, zone["y_max"]))
            dx = cx - closest_x
            dy = cy - closest_y
            dist_sq = dx * dx + dy * dy
            assert dist_sq >= (radius * radius), f"{hz['id']} radius overlaps with {zone['name']}"


def test_allowed_zone(geofence):
    """Start position [10, 80] and destination [90, 20] must be ALLOWED zones."""
    assert geofence.get_zone_type(config.START) == "ALLOWED"
    assert geofence.get_zone_type(config.DESTINATION) == "ALLOWED"
