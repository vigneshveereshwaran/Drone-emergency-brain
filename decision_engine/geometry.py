"""
Pure Geometry and Spatial Utilities for Emergency Decision Engine.
Decoupled from simulator: operates on mathematical coordinates, bounding boxes, and circles.
"""

import math
from typing import List, Tuple, Dict, Any, Optional
import config


def euclidean_distance(p1: List[float], p2: List[float]) -> float:
    """Calculates 2D Euclidean distance between two points [x, y]."""
    return math.hypot(p1[0] - p2[0], p1[1] - p2[1])


def point_in_rect(point: List[float], rect: Dict[str, Any]) -> bool:
    """
    Checks if a point [x, y] is inside a rectangle defined by:
    x_min, x_max, y_min, y_max (inclusive).
    """
    px, py = point[0], point[1]
    return (rect["x_min"] <= px <= rect["x_max"] and
            rect["y_min"] <= py <= rect["y_max"])


def point_in_circle(point: List[float], center: List[float], radius: float) -> bool:
    """Checks if point [x, y] lies inside or on the circle with center and radius."""
    return euclidean_distance(point, center) <= radius


def circle_rect_overlap(center: List[float], radius: float, rect: Dict[str, Any]) -> bool:
    """Checks whether a circle overlaps with a 2D axis-aligned bounding box."""
    cx, cy = center[0], center[1]
    closest_x = max(rect["x_min"], min(cx, rect["x_max"]))
    closest_y = max(rect["y_min"], min(cy, rect["y_max"]))
    dx = cx - closest_x
    dy = cy - closest_y
    return (dx * dx + dy * dy) <= (radius * radius)


def circle_circle_overlap(c1: List[float], r1: float, c2: List[float], r2: float) -> bool:
    """Checks whether two circles overlap."""
    dist = euclidean_distance(c1, c2)
    return dist <= (r1 + r2)


def segment_intersects_rect(p1: List[float], p2: List[float], rect: Dict[str, Any]) -> bool:
    """
    Checks if line segment p1 -> p2 intersects an axis-aligned rectangle [x_min, x_max, y_min, y_max].
    Uses Liang-Barsky parametric line-clipping algorithm.
    """
    # If either endpoint is inside the rectangle, it intersects
    if point_in_rect(p1, rect) or point_in_rect(p2, rect):
        return True

    x1, y1 = p1[0], p1[1]
    x2, y2 = p2[0], p2[1]
    dx = x2 - x1
    dy = y2 - y1

    p = [-dx, dx, -dy, dy]
    q = [
        x1 - rect["x_min"],
        rect["x_max"] - x1,
        y1 - rect["y_min"],
        rect["y_max"] - y1
    ]

    u1 = 0.0
    u2 = 1.0

    for i in range(4):
        if p[i] == 0:
            if q[i] < 0:
                return False
        else:
            t = q[i] / p[i]
            if p[i] < 0:
                if t > u2:
                    return False
                if t > u1:
                    u1 = t
            elif p[i] > 0:
                if t < u1:
                    return False
                if t < u2:
                    u2 = t

    return u1 <= u2


def get_point_zone_type(point: List[float]) -> str:
    """
    Returns the zone classification for a point:
    - 'RESTRICTED' if inside restricted airspace
    - 'PRIVATE' if inside private property
    - 'HOVER_ZONE' if inside any defined legal hover zone
    - 'ALLOWED' otherwise
    """
    if point_in_rect(point, config.RESTRICTED_AIRSPACE):
        return "RESTRICTED"

    if point_in_rect(point, config.PRIVATE_PROPERTY):
        return "PRIVATE"

    for hz in config.LEGAL_HOVER_ZONES:
        if point_in_circle(point, hz["center"], hz["radius"]):
            return "HOVER_ZONE"

    return "ALLOWED"


def is_position_safe_and_legal(point: List[float]) -> bool:
    """A position is safe and legal if it is NOT in restricted or private property."""
    return not (point_in_rect(point, config.RESTRICTED_AIRSPACE) or
                point_in_rect(point, config.PRIVATE_PROPERTY))


def find_nearest_legal_hover_zone(
    current_pos: List[float],
    current_battery: float = 100.0,
    consumption_rate: float = config.BATTERY_CONSUMPTION,
    reserve: float = config.SAFETY_RESERVE,
    excluded_zone_ids: Optional[List[str]] = None
) -> Tuple[Optional[Dict[str, Any]], List[Dict[str, str]]]:
    """
    Finds the nearest reachable and legal hover zone to current_pos.
    Returns:
        (best_zone_dict, rejected_options_list)
    """
    excluded = set(excluded_zone_ids or [])
    candidates = []
    rejected: List[Dict[str, str]] = []

    # Candidate evaluation: prioritize transit distance, with return-to-base alignment
    # (Favoring recovery zones closer to home base when transit distances are comparable)
    for hz in config.LEGAL_HOVER_ZONES:
        hz_id = hz["id"]
        center = hz["center"]

        if hz_id in excluded:
            rejected.append({"zone_id": hz_id, "reason": "Explicitly excluded"})
            continue

        dist = euclidean_distance(current_pos, center)
        energy_required = dist * consumption_rate

        # Energy feasibility check
        if (current_battery - energy_required) < reserve:
            rejected.append({
                "zone_id": hz_id,
                "reason": f"Insufficient battery (Requires {energy_required:.1f}%, remaining would be {current_battery - energy_required:.1f}% < reserve {reserve}%)"
            })
            continue

        # Proximity to home base enhances recovery safety
        dist_to_home = euclidean_distance(center, config.START)
        suitability_score = dist + (0.1 * dist_to_home)

        candidates.append((suitability_score, dist, hz))

    if not candidates:
        return None, rejected

    # Sort candidates by suitability (ascending)
    candidates.sort(key=lambda item: item[0])
    best_score, best_dist, best_zone = candidates[0]

    # For reporting, add unselected candidates to rejected options with distance comparison
    for score, dist, other_zone in candidates[1:]:
        rejected.append({
            "zone_id": other_zone["id"],
            "reason": f"Less optimal recovery zone (Distance: {dist:.1f} units vs {best_dist:.1f} units for {best_zone['id']})"
        })

    return best_zone, rejected


def interpolate_point(p1: List[float], p2: List[float], fraction: float) -> List[float]:
    """Linearly interpolates between p1 and p2 at parameter fraction [0.0, 1.0]."""
    clamped = max(0.0, min(1.0, fraction))
    return [
        p1[0] + (p2[0] - p1[0]) * clamped,
        p1[1] + (p2[1] - p1[1]) * clamped
    ]
