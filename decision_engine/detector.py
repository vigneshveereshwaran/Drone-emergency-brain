"""
Failure Detection Module for Autonomous Drone Emergency Brain.
Part J: Detects anomalies, threshold breaches, geofence intrusions, and security events from telemetry.
Completely decoupled from simulator.
"""

from typing import List, Dict, Any, Optional
import time
import config
from decision_engine.geometry import point_in_rect
from decision_engine.interfaces import DetectionResult


class FailureDetector:
    """
    Monitors telemetry frames and produces structured detection results with evidence.
    """

    def __init__(self):
        pass

    def detect_failures(self, telemetry: Dict[str, Any]) -> List[DetectionResult]:
        """
        Evaluates a telemetry frame and returns a list of detected failures.
        Each detection includes: type, evidence, and timestamp.
        """
        detections: List[DetectionResult] = []
        now = telemetry.get("timestamp")
        if now is None:
            now = time.time()

        battery = float(telemetry.get("battery", 100.0))
        gps_status = telemetry.get("gps_status", "CONNECTED")
        gps_accuracy = float(telemetry.get("gps_accuracy", 4.0))
        satellites = int(telemetry.get("satellites", 10))
        communication = telemetry.get("communication", "CONNECTED")
        comm_loss_duration = float(telemetry.get("comm_loss_duration", 0.0))
        obstacle_detected = bool(telemetry.get("obstacle_detected", False))
        unauthorized_movement = bool(telemetry.get("unauthorized_movement", False))
        theft_detected = bool(telemetry.get("theft_detected", False))
        position = telemetry.get("position", [10.0, 80.0])
        last_known_pos = telemetry.get("last_known_position", position)
        dist_to_home = float(telemetry.get("distance_to_home", 0.0))
        consumption_rate = float(telemetry.get("battery_consumption_rate", config.BATTERY_CONSUMPTION))

        # -------------------------------------------------------------
        # 1. SECURITY & TAMPERING DETECTION
        # -------------------------------------------------------------
        if unauthorized_movement:
            detections.append(DetectionResult(
                type="UNAUTHORIZED_MOVEMENT",
                evidence=[
                    "Drone moved beyond station-holding hover radius without authorized command",
                    f"Current position: [{position[0]:.1f}, {position[1]:.1f}]"
                ],
                timestamp=now
            ))

        if theft_detected:
            detections.append(DetectionResult(
                type="THEFT_DETECTED",
                evidence=[
                    "Tampering / external forced displacement detected",
                    "Simulated theft alarm triggered"
                ],
                timestamp=now
            ))

        # -------------------------------------------------------------
        # 2. ENERGY & BATTERY DETECTION
        # -------------------------------------------------------------
        # Calculate energy required to return home plus safety reserve
        energy_to_home = dist_to_home * consumption_rate
        energy_needed_rth = energy_to_home + config.SAFETY_RESERVE

        if battery <= config.CRITICAL_BATTERY_THRESHOLD or (dist_to_home > 0 and battery <= energy_needed_rth):
            reason_parts = []
            if battery <= config.CRITICAL_BATTERY_THRESHOLD:
                reason_parts.append(f"Battery level {battery:.1f}% <= critical threshold ({config.CRITICAL_BATTERY_THRESHOLD:.1f}%)")
            if dist_to_home > 0 and battery <= energy_needed_rth:
                reason_parts.append(
                    f"Available energy ({battery:.1f}%) insufficient for safe RTH ({energy_to_home:.1f}% energy + {config.SAFETY_RESERVE:.1f}% reserve = {energy_needed_rth:.1f}%)"
                )
            detections.append(DetectionResult(
                type="CRITICAL_BATTERY",
                evidence=reason_parts,
                timestamp=now
            ))
        elif battery <= config.LOW_BATTERY_THRESHOLD:
            detections.append(DetectionResult(
                type="LOW_BATTERY",
                evidence=[
                    f"Battery level {battery:.1f}% <= warning threshold ({config.LOW_BATTERY_THRESHOLD:.1f}%)",
                    f"Remaining battery above critical reserve ({config.CRITICAL_BATTERY_THRESHOLD:.1f}%)"
                ],
                timestamp=now
            ))

        # -------------------------------------------------------------
        # 3. GPS & NAVIGATION DETECTION
        # -------------------------------------------------------------
        if gps_status == "LOST":
            detections.append(DetectionResult(
                type="GPS_FAILURE",
                evidence=[
                    "GPS receiver status is LOST",
                    f"Satellites locked: {satellites}",
                    f"GPS accuracy report: {gps_accuracy}m (unreliable)"
                ],
                timestamp=now
            ))
        elif gps_status == "DEGRADED" or gps_accuracy > config.GPS_ACCURACY_THRESHOLD or satellites < config.MIN_SATELLITES:
            reasons = []
            if gps_status == "DEGRADED":
                reasons.append("GPS status flagged as DEGRADED")
            if gps_accuracy > config.GPS_ACCURACY_THRESHOLD:
                reasons.append(f"GPS accuracy {gps_accuracy:.1f}m exceeds maximum allowed threshold ({config.GPS_ACCURACY_THRESHOLD:.1f}m)")
            if satellites < config.MIN_SATELLITES:
                reasons.append(f"Satellites locked ({satellites}) below minimum required ({config.MIN_SATELLITES})")
            detections.append(DetectionResult(
                type="GPS_DEGRADED",
                evidence=reasons,
                timestamp=now
            ))

        # -------------------------------------------------------------
        # 4. COMMUNICATION DETECTION
        # -------------------------------------------------------------
        if communication == "LOST":
            detections.append(DetectionResult(
                type="COMMUNICATION_FAILURE",
                evidence=[
                    "Heartbeat telemetry link to Ground Control Station LOST",
                    f"Communication loss duration: {comm_loss_duration:.1f} seconds"
                ],
                timestamp=now
            ))

        # -------------------------------------------------------------
        # 5. OBSTACLE DETECTION
        # -------------------------------------------------------------
        if obstacle_detected:
            detections.append(DetectionResult(
                type="OBSTACLE_DETECTED",
                evidence=[
                    "Proximity sensors detected unexpected obstacle on active route vector",
                    "Forward flight corridor blocked"
                ],
                timestamp=now
            ))

        # -------------------------------------------------------------
        # 6. GEOFENCE & AIRSPACE DETECTION
        # -------------------------------------------------------------
        # Check both active position and last known position (critical for GPS loss over restricted airspace)
        check_pos = last_known_pos if gps_status == "LOST" else position

        if point_in_rect(check_pos, config.RESTRICTED_AIRSPACE):
            detections.append(DetectionResult(
                type="RESTRICTED_ZONE",
                evidence=[
                    f"Drone coordinate [{check_pos[0]:.1f}, {check_pos[1]:.1f}] is inside {config.RESTRICTED_AIRSPACE['name']}",
                    f"Restricted bounds: X [{config.RESTRICTED_AIRSPACE['x_min']}-{config.RESTRICTED_AIRSPACE['x_max']}], Y [{config.RESTRICTED_AIRSPACE['y_min']}-{config.RESTRICTED_AIRSPACE['y_max']}]"
                ],
                timestamp=now
            ))
        elif point_in_rect(check_pos, config.PRIVATE_PROPERTY):
            detections.append(DetectionResult(
                type="RESTRICTED_ZONE",
                evidence=[
                    f"Drone coordinate [{check_pos[0]:.1f}, {check_pos[1]:.1f}] is inside {config.PRIVATE_PROPERTY['name']}",
                    f"Private property bounds: X [{config.PRIVATE_PROPERTY['x_min']}-{config.PRIVATE_PROPERTY['x_max']}], Y [{config.PRIVATE_PROPERTY['y_min']}-{config.PRIVATE_PROPERTY['y_max']}]"
                ],
                timestamp=now
            ))

        return detections
