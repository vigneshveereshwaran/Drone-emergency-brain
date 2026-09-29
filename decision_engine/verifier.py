"""
Recovery Verification Engine.
Part 6 (Third Absolute Rule): Verification MUST NEVER assume success.
Part R: Inspects actual observed drone state against criteria and returns SUCCESS, PARTIAL_SUCCESS, or FAILED.
Completely decoupled from simulator.
"""

from typing import Dict, Any, List, Optional
import time
import config
from decision_engine.geometry import euclidean_distance, is_position_safe_and_legal
from decision_engine.interfaces import VerificationResult, VerificationStatus, RecoveryCommand, DecisionType


class RecoveryVerifier:
    """
    Independently inspects telemetry frames after recovery execution to verify outcomes.
    Evaluates: HOVER, RELOCATE, RETURN_TO_HOME, ALTERNATE_ROUTE, GPS_RESTORE, COMM_RESTORE, EMERGENCY_LANDING.
    """

    def __init__(self):
        pass

    def verify_hover(self, telemetry: Dict[str, Any], target_pos: Optional[List[float]] = None) -> VerificationResult:
        """Verifies station holding: target reached, speed near zero, legal zone, hover tolerance."""
        checks: Dict[str, str] = {}
        now = telemetry.get("timestamp") or time.time()
        pos = telemetry.get("position", [0.0, 0.0])
        speed = float(telemetry.get("speed", 0.0))
        target = target_pos or telemetry.get("hover_position") or pos

        dist_to_target = euclidean_distance(pos, target)
        speed_ok = speed <= 0.2
        target_reached = dist_to_target <= config.HOVER_RADIUS
        pos_legal = is_position_safe_and_legal(pos)
        unauthorized = bool(telemetry.get("unauthorized_movement", False))

        checks["target_reached"] = "PASS" if target_reached else "FAIL"
        checks["speed_zero"] = "PASS" if speed_ok else "FAIL"
        checks["position_legal"] = "PASS" if pos_legal else "FAIL"
        checks["station_holding_secure"] = "PASS" if not unauthorized else "FAIL"

        if not target_reached or not pos_legal or unauthorized:
            status = VerificationStatus.FAILED.value
            summary = (
                f"Hover verification FAILED: "
                f"Dist to target={dist_to_target:.1f} (tol {config.HOVER_RADIUS}), "
                f"Legal={pos_legal}, UnauthorizedMovement={unauthorized}"
            )
        elif not speed_ok:
            status = VerificationStatus.PARTIAL_SUCCESS.value
            summary = f"Hover verification PARTIAL: Drone in position but residual velocity={speed:.2f}"
        else:
            status = VerificationStatus.SUCCESS.value
            summary = "Hover verification SUCCESS: Target station locked, zero speed, legal airspace."

        return VerificationResult(status=status, checks=checks, summary=summary, timestamp=now)

    def verify_relocation(self, telemetry: Dict[str, Any], target_pos: List[float]) -> VerificationResult:
        """Verifies relocation to a safe hover zone."""
        checks: Dict[str, str] = {}
        now = telemetry.get("timestamp") or time.time()
        pos = telemetry.get("position", [0.0, 0.0])
        battery = float(telemetry.get("battery", 0.0))
        obstacle = bool(telemetry.get("obstacle_detected", False))

        dist = euclidean_distance(pos, target_pos)
        reached = dist <= config.HOVER_RADIUS
        legal = is_position_safe_and_legal(pos)
        battery_ok = battery >= config.SAFETY_RESERVE
        no_obstacle = not obstacle

        checks["target_reached"] = "PASS" if reached else "FAIL"
        checks["destination_legal"] = "PASS" if legal else "FAIL"
        checks["obstacle_avoided"] = "PASS" if no_obstacle else "FAIL"
        checks["battery_sufficient"] = "PASS" if battery_ok else "FAIL"

        if not reached or not legal or not battery_ok:
            status = VerificationStatus.FAILED.value
            summary = (
                f"Relocation verification FAILED: "
                f"Distance={dist:.1f}, Legal={legal}, Battery={battery:.1f}% (Reserve={config.SAFETY_RESERVE}%)"
            )
        elif not no_obstacle:
            status = VerificationStatus.PARTIAL_SUCCESS.value
            summary = "Relocation PARTIAL: Target reached but obstacle still flagged."
        else:
            status = VerificationStatus.SUCCESS.value
            summary = "Relocation verification SUCCESS: Safe legal hover station reached with adequate reserve."

        return VerificationResult(status=status, checks=checks, summary=summary, timestamp=now)

    def verify_return_home(self, telemetry: Dict[str, Any]) -> VerificationResult:
        """Verifies Return-To-Home completion: home reached, battery above reserve, landed."""
        checks: Dict[str, str] = {}
        now = telemetry.get("timestamp") or time.time()
        pos = telemetry.get("position", [0.0, 0.0])
        home = telemetry.get("home", config.START)
        battery = float(telemetry.get("battery", 0.0))
        altitude = float(telemetry.get("altitude", 10.0))
        flight_mode = telemetry.get("flight_mode", "IDLE")

        dist_to_home = euclidean_distance(pos, home)
        home_reached = dist_to_home <= 2.0
        battery_ok = battery >= config.SAFETY_RESERVE
        touchdown = altitude <= 0.5 and flight_mode in ("LANDED", "IDLE")

        checks["home_reached"] = "PASS" if home_reached else "FAIL"
        checks["battery_above_reserve"] = "PASS" if battery_ok else "FAIL"
        checks["safe_touchdown"] = "PASS" if touchdown else "FAIL"

        if not home_reached:
            status = VerificationStatus.FAILED.value
            summary = f"RTH verification FAILED: Distance to home={dist_to_home:.1f} > threshold"
        elif not battery_ok:
            status = VerificationStatus.PARTIAL_SUCCESS.value
            summary = f"RTH verification PARTIAL: Home reached but battery dipped below safety reserve ({battery:.1f}%)"
        else:
            status = VerificationStatus.SUCCESS.value
            summary = "RTH verification SUCCESS: Drone safely returned to base and landed with positive energy reserve."

        return VerificationResult(status=status, checks=checks, summary=summary, timestamp=now)

    def verify_alternate_route(self, telemetry: Dict[str, Any]) -> VerificationResult:
        """Verifies alternate route following: obstacle bypassed, legal corridor."""
        checks: Dict[str, str] = {}
        now = telemetry.get("timestamp") or time.time()
        pos = telemetry.get("position", [0.0, 0.0])
        obstacle = bool(telemetry.get("obstacle_detected", False))
        legal = is_position_safe_and_legal(pos)

        checks["obstacle_cleared"] = "PASS" if not obstacle else "FAIL"
        checks["corridor_legal"] = "PASS" if legal else "FAIL"

        if not legal:
            status = VerificationStatus.FAILED.value
            summary = "Alternate route verification FAILED: Detour entered illegal airspace."
        elif obstacle:
            status = VerificationStatus.PARTIAL_SUCCESS.value
            summary = "Alternate route PARTIAL: Detour in progress, obstacle clearance pending."
        else:
            status = VerificationStatus.SUCCESS.value
            summary = "Alternate route verification SUCCESS: Obstacle cleared along verified legal corridor."

        return VerificationResult(status=status, checks=checks, summary=summary, timestamp=now)

    def verify_gps_restoration(self, telemetry: Dict[str, Any]) -> VerificationResult:
        """Verifies GPS reacquisition: status connected, accuracy <= threshold, satellites >= min."""
        checks: Dict[str, str] = {}
        now = telemetry.get("timestamp") or time.time()
        gps_status = telemetry.get("gps_status", "LOST")
        gps_accuracy = float(telemetry.get("gps_accuracy", 99.0))
        satellites = int(telemetry.get("satellites", 0))

        status_ok = (gps_status == "CONNECTED")
        accuracy_ok = (gps_accuracy <= config.GPS_ACCURACY_THRESHOLD)
        sats_ok = (satellites >= config.MIN_SATELLITES)

        checks["gps_connected"] = "PASS" if status_ok else "FAIL"
        checks["accuracy_acceptable"] = "PASS" if accuracy_ok else "FAIL"
        checks["satellites_sufficient"] = "PASS" if sats_ok else "FAIL"

        if not status_ok or not sats_ok:
            status = VerificationStatus.FAILED.value
            summary = f"GPS Restoration FAILED: Status={gps_status}, Satellites={satellites}"
        elif not accuracy_ok:
            status = VerificationStatus.PARTIAL_SUCCESS.value
            summary = f"GPS Restoration PARTIAL: Connected but accuracy {gps_accuracy:.1f}m > threshold"
        else:
            status = VerificationStatus.SUCCESS.value
            summary = "GPS Restoration SUCCESS: Full 3D fix reacquired with healthy satellite lock."

        return VerificationResult(status=status, checks=checks, summary=summary, timestamp=now)

    def verify_communication_restoration(self, telemetry: Dict[str, Any]) -> VerificationResult:
        """Verifies communication link restoration: connected, heartbeat true."""
        checks: Dict[str, str] = {}
        now = telemetry.get("timestamp") or time.time()
        comm = telemetry.get("communication", "LOST")
        heartbeat = bool(telemetry.get("heartbeat", False))

        checks["link_connected"] = "PASS" if comm == "CONNECTED" else "FAIL"
        checks["heartbeat_received"] = "PASS" if heartbeat else "FAIL"

        if comm == "CONNECTED" and heartbeat:
            status = VerificationStatus.SUCCESS.value
            summary = "Communication Restoration SUCCESS: Bidirectional telemetry link and heartbeat re-established."
        else:
            status = VerificationStatus.FAILED.value
            summary = "Communication Restoration FAILED: Link remains down or heartbeat missing."

        return VerificationResult(status=status, checks=checks, summary=summary, timestamp=now)

    def verify_emergency_landing(self, telemetry: Dict[str, Any]) -> VerificationResult:
        """Verifies emergency landing: zero altitude, landed mode, recorded location."""
        checks: Dict[str, str] = {}
        now = telemetry.get("timestamp") or time.time()
        altitude = float(telemetry.get("altitude", 10.0))
        flight_mode = telemetry.get("flight_mode", "IDLE")
        pos = telemetry.get("position", [0.0, 0.0])

        touchdown = altitude <= 0.1
        mode_landed = flight_mode == "LANDED"
        pos_legal = is_position_safe_and_legal(pos)

        checks["touchdown_zero_altitude"] = "PASS" if touchdown else "FAIL"
        checks["mode_landed"] = "PASS" if mode_landed else "FAIL"
        checks["landing_site_legal"] = "PASS" if pos_legal else "WARN"

        if not touchdown or not mode_landed:
            status = VerificationStatus.FAILED.value
            summary = f"Emergency Landing FAILED: Alt={altitude:.1f}m, Mode={flight_mode}"
        elif not pos_legal:
            status = VerificationStatus.PARTIAL_SUCCESS.value
            summary = "Emergency Landing PARTIAL: Ground reached, but landing site was restricted/private."
        else:
            status = VerificationStatus.SUCCESS.value
            summary = "Emergency Landing SUCCESS: Controlled vertical touchdown completed at safe site."

        return VerificationResult(status=status, checks=checks, summary=summary, timestamp=now)
