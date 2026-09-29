"""
Autonomous Drone Emergency Brain - Configuration
Centralized configuration values for simulation, zones, risk thresholds, and parameters.
"""

from typing import Dict, Any, List

# Map Dimensions (100 x 100 grid, origin at top-left: +x right, +y downward)
MAP_SIZE = 100
COORDINATE_MIN = 0
COORDINATE_MAX = 100

# Flight Waypoints
START = [10.0, 80.0]
DESTINATION = [90.0, 20.0]
MISSION_TYPE = "DELIVERY"

# Battery and Energy Parameters
INITIAL_BATTERY = 100.0          # percent
BATTERY_CONSUMPTION = 0.4        # % drain per distance unit traveled
SAFETY_RESERVE = 10.0            # % mandatory safety reserve
LOW_BATTERY_THRESHOLD = 30.0     # % warning threshold
CRITICAL_BATTERY_THRESHOLD = 20.0 # % critical return / land threshold
HOVER_DRAIN = 0.05               # % drain per second while hovering

# Navigation and GPS Parameters
GPS_ACCURACY_THRESHOLD = 15.0    # meters (values above this indicate degraded accuracy)
MIN_SATELLITES = 6               # minimum satellites required for healthy GPS lock

# Communication Thresholds (seconds)
COMM_WARNING_THRESHOLD = 5.0     # 0–5s: WARNING
COMM_HIGH_THRESHOLD = 15.0       # 5–15s: HIGH (>15s: CRITICAL)

# Flight Dynamics
DRONE_SPEED = 5.0                # units / second
HOVER_RADIUS = 2.0               # units (tolerance boundary for hovering)
MAX_HOVER_DURATION = 30.0        # seconds

# Fixed Simulated Airspace Zones
# Restricted Airspace: x = 42–62, y = 40–60
RESTRICTED_AIRSPACE = {
    "name": "Restricted Airspace (No-Fly Zone)",
    "type": "RESTRICTED",
    "x_min": 42.0,
    "x_max": 62.0,
    "y_min": 40.0,
    "y_max": 60.0
}

# Private Property: x = 68–82, y = 30–45
PRIVATE_PROPERTY = {
    "name": "Private Property",
    "type": "PRIVATE",
    "x_min": 68.0,
    "x_max": 82.0,
    "y_min": 30.0,
    "y_max": 45.0
}

# Legal Hover Zones (safe emergency recovery locations)
LEGAL_HOVER_ZONES = [
    {"id": "HZ1", "name": "Hover Zone 1 (Primary South-West)", "center": [36.0, 66.0], "radius": 5.0},
    {"id": "HZ2", "name": "Hover Zone 2 (West Outpost)", "center": [30.0, 45.0], "radius": 5.0},
    {"id": "HZ3", "name": "Hover Zone 3 (South-East Pad)", "center": [72.0, 60.0], "radius": 5.0},
    {"id": "HZ4", "name": "Hover Zone 4 (North-East Perimeter)", "center": [85.0, 12.0], "radius": 5.0},
]

# Risk Scoring Points
RISK_POINTS = {
    "LOW_BATTERY": 1,
    "CRITICAL_BATTERY": 3,
    "GPS_DEGRADED": 1,
    "GPS_LOST": 3,
    "COMMUNICATION_LOST": 2,
    "LONG_COMM_LOSS": 1,         # additional point if comm loss > 5s
    "OBSTACLE": 2,
    "RESTRICTED_ZONE": 3,
    "UNAUTHORIZED_MOVEMENT": 3,
}

# Risk Bands (Total Score to Risk Level)
RISK_BANDS = [
    (0, 2, "LOW"),
    (3, 5, "MEDIUM"),
    (6, 8, "HIGH"),
    (9, 999, "CRITICAL"),
]

# Database Path
DB_PATH = "database/mission.db"


def validate_config() -> bool:
    """
    Validates the configuration parameters at startup:
    1. Grid limits and waypoint coordinates within bounds.
    2. Battery and threshold invariants.
    3. Verifies that NO legal hover zone overlaps restricted airspace or private property.
    """
    # 1. Bounds checks
    for coord in (START, DESTINATION):
        if not (COORDINATE_MIN <= coord[0] <= COORDINATE_MAX and COORDINATE_MIN <= coord[1] <= COORDINATE_MAX):
            raise ValueError(f"Waypoint {coord} out of map bounds [0, {MAP_SIZE}]")

    # 2. Battery thresholds check
    if not (0 < CRITICAL_BATTERY_THRESHOLD < LOW_BATTERY_THRESHOLD < INITIAL_BATTERY):
        raise ValueError("Invalid battery threshold hierarchy")

    if not (0 < SAFETY_RESERVE < CRITICAL_BATTERY_THRESHOLD):
        raise ValueError("Safety reserve must be positive and below critical battery threshold")

    # 3. Hover zone non-overlap validation
    # A circle (cx, cy, r) overlaps a rectangle [x_min, x_max, y_min, y_max]
    # if the closest point in the rectangle to (cx, cy) is within distance r.
    obstacles = [RESTRICTED_AIRSPACE, PRIVATE_PROPERTY]

    for hz in LEGAL_HOVER_ZONES:
        cx, cy = hz["center"]
        r = hz["radius"]

        for zone in obstacles:
            # Find closest point on rect to circle center
            closest_x = max(zone["x_min"], min(cx, zone["x_max"]))
            closest_y = max(zone["y_min"], min(cy, zone["y_max"]))

            dx = cx - closest_x
            dy = cy - closest_y
            dist_sq = dx * dx + dy * dy

            if dist_sq < (r * r):
                raise ValueError(
                    f"Configuration error: Legal hover zone {hz['id']} at {hz['center']} overlaps "
                    f"{zone['name']} [{zone['x_min']}-{zone['x_max']}, {zone['y_min']}-{zone['y_max']}]"
                )

    return True


# Run startup validation on import
validate_config()
