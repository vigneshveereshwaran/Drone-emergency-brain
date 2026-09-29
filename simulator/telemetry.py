"""
Telemetry Generator and Serializer for Drone Simulator.
Conforms strictly to Part F Telemetry specification.
"""

from typing import Dict, Any, List, Optional
import math
import config


def build_telemetry(
    position: List[float],
    last_known_position: List[float],
    battery: float,
    gps_status: str,
    gps_accuracy: float,
    satellites: int,
    communication: str,
    comm_loss_duration: float,
    obstacle_detected: bool,
    flight_mode: str,
    mission_status: str,
    speed: float,
    altitude: float,
    zone_type: str,
    hover_position: Optional[List[float]],
    hover_duration: float,
    unauthorized_movement: bool,
    theft_detected: bool,
    active_command_id: Optional[str],
    timestamp: float,
    home: Optional[List[float]] = None,
    destination: Optional[List[float]] = None,
    consumption_rate: float = config.BATTERY_CONSUMPTION
) -> Dict[str, Any]:
    """Constructs a standardized telemetry dictionary matching Part F."""
    h = home or config.START
    dest = destination or config.DESTINATION

    dist_to_home = math.hypot(position[0] - h[0], position[1] - h[1])
    dist_to_dest = math.hypot(position[0] - dest[0], position[1] - dest[1])

    # Calculate GPS confidence based on status, satellites, and accuracy
    if gps_status == "LOST":
        gps_confidence = 0.0
    elif gps_status == "DEGRADED":
        # Decreased confidence if satellites < MIN_SATELLITES or accuracy > threshold
        sat_ratio = min(1.0, max(0.0, satellites / config.MIN_SATELLITES))
        acc_penalty = min(1.0, config.GPS_ACCURACY_THRESHOLD / max(1.0, gps_accuracy))
        gps_confidence = round(0.5 * (sat_ratio + acc_penalty), 2)
    else:
        gps_confidence = 1.0

    heartbeat = (communication == "CONNECTED")

    return {
        "battery": round(battery, 2),
        "battery_consumption_rate": consumption_rate,
        "gps_status": gps_status,
        "gps_accuracy": round(gps_accuracy, 1),
        "satellites": satellites,
        "gps_confidence": gps_confidence,
        "communication": communication,
        "heartbeat": heartbeat,
        "comm_loss_duration": round(comm_loss_duration, 2),
        "position": [round(position[0], 3), round(position[1], 3)],
        "last_known_position": [round(last_known_position[0], 3), round(last_known_position[1], 3)],
        "home": [round(h[0], 2), round(h[1], 2)],
        "destination": [round(dest[0], 2), round(dest[1], 2)],
        "distance_to_home": round(dist_to_home, 2),
        "distance_to_destination": round(dist_to_dest, 2),
        "obstacle_detected": obstacle_detected,
        "mission_status": mission_status,
        "flight_mode": flight_mode,
        "altitude": round(altitude, 2),
        "speed": round(speed, 2),
        "zone_type": zone_type,
        "hover_position": [round(hover_position[0], 2), round(hover_position[1], 2)] if hover_position else None,
        "hover_duration": round(hover_duration, 2),
        "unauthorized_movement": unauthorized_movement,
        "theft_detected": theft_detected,
        "active_command_id": active_command_id,
        "timestamp": round(timestamp, 3)
    }
