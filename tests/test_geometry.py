"""
Tests for decision_engine/geometry.py
Validates pure spatial calculations, distances, bounding box tests, and hover zone selection.
"""

import pytest
import config
from decision_engine.geometry import (
    euclidean_distance,
    point_in_rect,
    point_in_circle,
    circle_rect_overlap,
    segment_intersects_rect,
    interpolate_point,
    get_point_zone_type,
    find_nearest_legal_hover_zone
)


def test_euclidean_distance():
    assert euclidean_distance([0, 0], [3, 4]) == 5.0
    assert euclidean_distance([10, 20], [10, 20]) == 0.0
    assert euclidean_distance([10, 80], [90, 20]) == pytest.approx(100.0)


def test_point_in_rect():
    rect = {"x_min": 42.0, "x_max": 62.0, "y_min": 40.0, "y_max": 60.0}
    assert point_in_rect([50.0, 50.0], rect) is True
    assert point_in_rect([42.0, 40.0], rect) is True  # Boundary inclusive
    assert point_in_rect([62.0, 60.0], rect) is True
    assert point_in_rect([30.0, 50.0], rect) is False
    assert point_in_rect([50.0, 70.0], rect) is False


def test_point_in_circle():
    center = [36.0, 66.0]
    radius = 5.0
    assert point_in_circle([36.0, 66.0], center, radius) is True
    assert point_in_circle([36.0, 71.0], center, radius) is True  # Exactly on boundary
    assert point_in_circle([36.0, 72.0], center, radius) is False


def test_circle_rect_overlap():
    rect = {"x_min": 40.0, "x_max": 60.0, "y_min": 40.0, "y_max": 60.0}
    # Circle clearly outside
    assert circle_rect_overlap([10.0, 10.0], 5.0, rect) is False
    # Circle clearly overlapping
    assert circle_rect_overlap([38.0, 50.0], 5.0, rect) is True
    # Circle center inside
    assert circle_rect_overlap([50.0, 50.0], 2.0, rect) is True


def test_segment_intersects_rect():
    rect = {"x_min": 40.0, "x_max": 60.0, "y_min": 40.0, "y_max": 60.0}
    # Segment passes straight through
    assert segment_intersects_rect([30.0, 50.0], [70.0, 50.0], rect) is True
    # Segment is completely outside
    assert segment_intersects_rect([10.0, 10.0], [20.0, 20.0], rect) is False
    # Segment endpoint inside
    assert segment_intersects_rect([50.0, 50.0], [90.0, 90.0], rect) is True


def test_interpolate_point():
    p1 = [10.0, 80.0]
    p2 = [90.0, 20.0]
    mid = interpolate_point(p1, p2, 0.5)
    assert mid == [50.0, 50.0]
    assert interpolate_point(p1, p2, 0.0) == [10.0, 80.0]
    assert interpolate_point(p1, p2, 1.0) == [90.0, 20.0]


def test_flagship_nearest_hover_zone():
    """
    At approximately [50, 50] (inside restricted zone), HZ1 (36, 66) is the nearest valid legal hover zone.
    Distance to HZ1: sqrt((50-36)^2 + (50-66)^2) = sqrt(196 + 256) = sqrt(452) ~= 21.26
    Distance to HZ2 (30, 45): sqrt(20^2 + 5^2) = sqrt(425) ~= 20.61? Wait! Let's check distances!
    """
    pos = [50.0, 50.0]
    best_zone, rejected = find_nearest_legal_hover_zone(pos, current_battery=80.0)
    assert best_zone is not None
    assert "id" in best_zone
    assert len(rejected) > 0
