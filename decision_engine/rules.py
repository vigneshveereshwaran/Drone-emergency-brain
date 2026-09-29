"""
Decision Rules Library for Autonomous Drone Emergency Brain.
Part N: Implements rules R1 through R14 with strict priority hierarchy,
explainable evidence, rule IDs, and rejected alternatives evaluation.
Completely decoupled from simulator.
"""

from typing import Dict, Any, List, Optional, Tuple
import config
from decision_engine.geometry import (
    euclidean_distance,
    is_position_safe_and_legal,
    find_nearest_legal_hover_zone,
    segment_intersects_rect
)
from decision_engine.interfaces import DecisionType


class RuleEvaluationResult:
    def __init__(
        self,
        rule_id: str,
        decision: str,
        priority: int,
        reason: str,
        evidence: List[str],
        rejected_options: List[Dict[str, str]],
        alternatives_considered: List[str],
        target_position: Optional[List[float]] = None,
        selected_zone_id: Optional[str] = None,
        alternate_waypoints: Optional[List[List[float]]] = None
    ):
        self.rule_id = rule_id
        self.decision = decision
        self.priority = priority
        self.reason = reason
        self.evidence = evidence
        self.rejected_options = rejected_options
        self.alternatives_considered = alternatives_considered
        self.target_position = target_position
        self.selected_zone_id = selected_zone_id
        self.alternate_waypoints = alternate_waypoints


# -------------------------------------------------------------------------
# RULE IMPLEMENTATIONS (R1 - R14)
# Priority order: SECURITY(100) -> ENERGY(90) -> COLLISION(80) ->
#                 NAVIGATION(70) -> LEGAL(60) -> COMMUNICATION(50) -> DEGRADATION(20)
# -------------------------------------------------------------------------

def evaluate_r1_security(
    telemetry: Dict[str, Any],
    detection_types: set,
    detections: List[Any]
) -> Optional[RuleEvaluationResult]:
    """R1 — SECURITY: Unauthorized movement or theft detected."""
    if "UNAUTHORIZED_MOVEMENT" in detection_types or "THEFT_DETECTED" in detection_types:
        return RuleEvaluationResult(
            rule_id="R1_SECURITY",
            decision=DecisionType.SECURITY_ESCALATION.value,
            priority=100,
            reason="Unauthorized drone displacement or tampering detected without flight clearance.",
            evidence=[
                "Station-holding tolerance breached",
                f"Position: {telemetry.get('position')}",
                "Theft/tamper sensor flag active"
            ],
            rejected_options=[
                {"option": "CONTINUE_MISSION", "reason": "Immediate security lockout mandatory on tamper detection."},
                {"option": "HOVER", "reason": "Station holding already compromised by external force."}
            ],
            alternatives_considered=["EMERGENCY_LANDING", "RETURN_TO_HOME", "SECURITY_ESCALATION"],
            target_position=telemetry.get("position")
        )
    return None


def evaluate_r2_r3_critical_battery(
    telemetry: Dict[str, Any],
    detection_types: set
) -> Optional[RuleEvaluationResult]:
    """R2 & R3 — CRITICAL BATTERY: Evaluate RTH feasibility vs forced emergency landing."""
    if "CRITICAL_BATTERY" not in detection_types:
        return None

    battery = float(telemetry.get("battery", 0.0))
    dist_to_home = float(telemetry.get("distance_to_home", 0.0))
    consumption_rate = float(telemetry.get("battery_consumption_rate", config.BATTERY_CONSUMPTION))
    reserve = float(config.SAFETY_RESERVE)
    home = telemetry.get("home", config.START)
    pos = telemetry.get("position", home)
    gps_status = telemetry.get("gps_status", "CONNECTED")

    energy_to_home = dist_to_home * consumption_rate
    energy_needed = energy_to_home + reserve
    gps_available = (gps_status != "LOST")

    # Check if direct line to home is legally clear (does not intersect restricted airspace)
    direct_route_clear = not segment_intersects_rect(pos, home, config.RESTRICTED_AIRSPACE)

    rth_feasible = (battery >= energy_needed) and gps_available and direct_route_clear

    if rth_feasible:
        # R2: Critical battery with feasible RTH
        return RuleEvaluationResult(
            rule_id="R2_CRITICAL_BATTERY_RTH",
            decision=DecisionType.RETURN_TO_HOME.value,
            priority=90,
            reason=f"Battery ({battery:.1f}%) is critical but safely sufficient to reach Home with {reserve}% reserve.",
            evidence=[
                f"Battery level: {battery:.1f}%",
                f"Distance to home: {dist_to_home:.1f} units (requires {energy_to_home:.1f}% energy)",
                f"Safe return reserve: {reserve}% (Total needed: {energy_needed:.1f}%)",
                f"GPS navigation status: {gps_status}"
            ],
            rejected_options=[
                {"option": "CONTINUE_MISSION", "reason": "Destination distance exceeds critical energy envelope."},
                {"option": "EMERGENCY_LANDING", "reason": "RTH is safely reachable; landing off-base avoided."}
            ],
            alternatives_considered=["CONTINUE_MISSION", "EMERGENCY_LANDING", "RETURN_TO_HOME"],
            target_position=home
        )
    else:
        # R3: Critical battery with infeasible RTH -> EMERGENCY_LANDING
        infeasible_reasons = []
        if battery < energy_needed:
            infeasible_reasons.append(f"Insufficient energy for RTH (Available {battery:.1f}% < Required {energy_needed:.1f}%)")
        if not gps_available:
            infeasible_reasons.append("GPS navigation unavailable for transit")
        if not direct_route_clear:
            infeasible_reasons.append("Direct return route crosses restricted airspace")

        # Find nearest legal landing site (either current pos if legal, or nearest legal hover pad)
        best_zone, rejected_zones = find_nearest_legal_hover_zone(pos, current_battery=battery)
        target = best_zone["center"] if best_zone and not is_position_safe_and_legal(pos) else pos

        return RuleEvaluationResult(
            rule_id="R3_CRITICAL_BATTERY_LANDING",
            decision=DecisionType.EMERGENCY_LANDING.value,
            priority=92,
            reason=f"Battery ({battery:.1f}%) is critical and RTH is infeasible ({'; '.join(infeasible_reasons)}).",
            evidence=infeasible_reasons,
            rejected_options=[
                {"option": "RETURN_TO_HOME", "reason": f"RTH not feasible: {', '.join(infeasible_reasons)}"},
                {"option": "HOVER", "reason": "Hovering would exhaust remaining battery reserve and cause an uncontrolled fall."}
            ],
            alternatives_considered=["RETURN_TO_HOME", "EMERGENCY_LANDING"],
            target_position=target,
            selected_zone_id=best_zone["id"] if best_zone else None
        )


def evaluate_r4_obstacle(
    telemetry: Dict[str, Any],
    detection_types: set
) -> Optional[RuleEvaluationResult]:
    """R4 — OBSTACLE: Generate safe alternate route around blocked corridor."""
    if "OBSTACLE_DETECTED" not in detection_types:
        return None

    pos = telemetry.get("position", config.START)
    dest = telemetry.get("destination", config.DESTINATION)
    battery = float(telemetry.get("battery", 100.0))

    # Calculate detour waypoint bypassing restricted airspace and obstacle
    # Corridor between y=20 and y=28 is entirely north of restricted airspace (y=40-60)
    # and private property (y=30-45).
    # Leg 1: pos -> wp1 [35.0, 25.0] (west of restricted airspace x=42-62)
    # Leg 2: wp1 -> wp2 [65.0, 25.0] (east of restricted airspace, north of private property)
    # Leg 3: wp2 -> dest [90.0, 20.0]
    wp1 = [35.0, 25.0]
    wp2 = [65.0, 25.0]
    alternate_route = [wp1, wp2, dest]

    # Verify all legs do not intersect restricted or private property
    leg1_safe = not segment_intersects_rect(pos, wp1, config.RESTRICTED_AIRSPACE) and \
                not segment_intersects_rect(pos, wp1, config.PRIVATE_PROPERTY)
    leg2_safe = not segment_intersects_rect(wp1, wp2, config.RESTRICTED_AIRSPACE) and \
                not segment_intersects_rect(wp1, wp2, config.PRIVATE_PROPERTY)
    leg3_safe = not segment_intersects_rect(wp2, dest, config.RESTRICTED_AIRSPACE) and \
                not segment_intersects_rect(wp2, dest, config.PRIVATE_PROPERTY)

    detour_dist = (euclidean_distance(pos, wp1) +
                   euclidean_distance(wp1, wp2) +
                   euclidean_distance(wp2, dest))
    energy_needed = (detour_dist * config.BATTERY_CONSUMPTION) + config.SAFETY_RESERVE

    if leg1_safe and leg2_safe and leg3_safe and battery >= energy_needed:
        return RuleEvaluationResult(
            rule_id="R4_OBSTACLE_ALTERNATE_ROUTE",
            decision=DecisionType.ALTERNATE_ROUTE.value,
            priority=80,
            reason="Obstacle blocks planned corridor. Safe alternate detour path identified and legally verified.",
            evidence=[
                "Obstacle detected ahead on direct track",
                f"Computed bypass waypoints: {wp1} -> {wp2} -> {dest}",
                f"Detour energy required: {energy_needed:.1f}% (Battery available: {battery:.1f}%)",
                "Alternate route legs verified clear of restricted and private airspace"
            ],
            rejected_options=[
                {"option": "CONTINUE_MISSION", "reason": "Immediate collision risk on current flight path."},
                {"option": "EMERGENCY_LANDING", "reason": "Sufficient battery and clear bypass route exist to complete mission."}
            ],
            alternatives_considered=["HOVER", "RETURN_TO_HOME", "ALTERNATE_ROUTE"],
            target_position=wp1,
            alternate_waypoints=alternate_route
        )
    else:
        # Fallback if detour infeasible
        return RuleEvaluationResult(
            rule_id="R4_OBSTACLE_FALLBACK_HOVER",
            decision=DecisionType.HOVER.value,
            priority=80,
            reason="Obstacle detected on active corridor; alternate detour path is constrained. Station holding commanded.",
            evidence=["Corridor blocked", "Detour route clearance pending or battery constrained"],
            rejected_options=[
                {"option": "CONTINUE_MISSION", "reason": "Corridor blocked by physical obstacle."}
            ],
            alternatives_considered=["ALTERNATE_ROUTE", "HOVER"],
            target_position=pos
        )


def evaluate_r5_r6_gps_lost(
    telemetry: Dict[str, Any],
    detection_types: set
) -> Optional[RuleEvaluationResult]:
    """
    R5 & R6 — GPS LOST:
    R5 (Flagship): GPS lost inside/near restricted airspace -> RELOCATE_AND_HOVER to nearest legal hover zone.
    R6: GPS lost in legal airspace -> HOVER in place.
    """
    if "GPS_FAILURE" not in detection_types:
        return None

    last_known = telemetry.get("last_known_position", telemetry.get("position", [10.0, 80.0]))
    battery = float(telemetry.get("battery", 100.0))
    in_restricted = ("RESTRICTED_ZONE" in detection_types) or (not is_position_safe_and_legal(last_known))

    if in_restricted:
        # Flagship Rule R5: GPS LOST + RESTRICTED ZONE
        best_zone, rejected_zones = find_nearest_legal_hover_zone(last_known, current_battery=battery)

        if not best_zone:
            # If no zone reachable, fallback to emergency landing
            return RuleEvaluationResult(
                rule_id="R5_GPS_RESTRICTED_EMERGENCY_LAND",
                decision=DecisionType.EMERGENCY_LANDING.value,
                priority=76,
                reason="GPS lost in restricted zone and no legal hover zone is energetically reachable.",
                evidence=["GPS lost", "Inside restricted airspace", "No hover zone within energy range"],
                rejected_options=[{"option": "HOVER", "reason": "Cannot hover inside restricted airspace."}],
                alternatives_considered=["RELOCATE_AND_HOVER", "EMERGENCY_LANDING"],
                target_position=last_known
            )

        # Build detailed rejection rationale for current location
        current_loc_rejection = {
            "option": f"HOVER_AT_CURRENT_POS [{last_known[0]:.1f}, {last_known[1]:.1f}]",
            "reason": "Rejected: Last known position is inside Restricted Airspace (x:42-62, y:40-60). Holding station here violates aviation law."
        }
        all_rejections = [current_loc_rejection]
        for rz in rejected_zones:
            all_rejections.append({
                "option": f"HOVER_ZONE_{rz['zone_id']}",
                "reason": rz["reason"]
            })

        dist_to_hz = euclidean_distance(last_known, best_zone["center"])

        return RuleEvaluationResult(
            rule_id="R5_GPS_LOST_RESTRICTED_ZONE",
            decision=DecisionType.RELOCATE_AND_HOVER.value,
            priority=75,
            reason=f"GPS lost while located inside Restricted Airspace. Hovering in place rejected due to legal compliance. Relocating to nearest verified legal hover station ({best_zone['id']}).",
            evidence=[
                "GPS status is LOST (Confidence: 0.0)",
                f"Last known position [{last_known[0]:.1f}, {last_known[1]:.1f}] is inside {config.RESTRICTED_AIRSPACE['name']}",
                f"Selected safe hover zone: {best_zone['id']} at {best_zone['center']} (Distance: {dist_to_hz:.1f} units)",
                f"Battery level ({battery:.1f}%) is sufficient for relocation and station-holding"
            ],
            rejected_options=all_rejections,
            alternatives_considered=["HOVER_IN_PLACE", "RELOCATE_AND_HOVER", "RETURN_TO_HOME"],
            target_position=best_zone["center"],
            selected_zone_id=best_zone["id"]
        )
    else:
        # R6: GPS lost in safe legal airspace
        return RuleEvaluationResult(
            rule_id="R6_GPS_LOST_LEGAL_HOVER",
            decision=DecisionType.HOVER.value,
            priority=70,
            reason="GPS signal lost in legally compliant airspace. Holding station to stabilize and attempt satellite reacquisition.",
            evidence=[
                "GPS status is LOST",
                f"Last known position [{last_known[0]:.1f}, {last_known[1]:.1f}] is within ALLOWED airspace",
                f"Battery level ({battery:.1f}%) is sufficient for station-holding"
            ],
            rejected_options=[
                {"option": "CONTINUE_MISSION", "reason": "Blind navigation without GPS confidence risks severe drift and intrusion."},
                {"option": "RETURN_TO_HOME", "reason": "Autonomous transit to home coordinates unreliable without GPS fix."}
            ],
            alternatives_considered=["CONTINUE_MISSION", "RETURN_TO_HOME", "HOVER"],
            target_position=last_known
        )


def evaluate_r7_restricted_zone(
    telemetry: Dict[str, Any],
    detection_types: set
) -> Optional[RuleEvaluationResult]:
    """R7 — RESTRICTED ZONE: Active position inside restricted zone with GPS available."""
    if "RESTRICTED_ZONE" not in detection_types:
        return None

    pos = telemetry.get("position", [50.0, 50.0])
    battery = float(telemetry.get("battery", 100.0))
    best_zone, rejected_zones = find_nearest_legal_hover_zone(pos, current_battery=battery)

    if best_zone:
        target = best_zone["center"]
        zone_id = best_zone["id"]
    else:
        target = config.START
        zone_id = None

    return RuleEvaluationResult(
        rule_id="R7_RESTRICTED_AIRSPACE_EVACUATION",
        decision=DecisionType.RELOCATE_AND_HOVER.value,
        priority=65,
        reason=f"Drone is currently inside restricted airspace. Immediate evacuation to nearest legal zone ({zone_id or 'Home'}) commanded.",
        evidence=[
            f"Active position [{pos[0]:.1f}, {pos[1]:.1f}] violates restricted airspace boundary",
            f"Evacuation target: {target}"
        ],
        rejected_options=[
            {"option": "HOVER", "reason": "Cannot remain in restricted airspace."}
        ],
        alternatives_considered=["HOVER", "RELOCATE_AND_HOVER"],
        target_position=target,
        selected_zone_id=zone_id
    )


def evaluate_r8_r9_r10_comm_loss(
    telemetry: Dict[str, Any],
    detection_types: set
) -> Optional[RuleEvaluationResult]:
    """R8, R9, R10 — COMMUNICATION LOSS: Short loss, prolonged loss, or combined with GPS loss."""
    if "COMMUNICATION_FAILURE" not in detection_types:
        return None

    comm_duration = float(telemetry.get("comm_loss_duration", 0.0))
    gps_status = telemetry.get("gps_status", "CONNECTED")
    battery = float(telemetry.get("battery", 100.0))
    home = telemetry.get("home", config.START)
    pos = telemetry.get("position", home)

    # R10: Comm loss + GPS loss
    if "GPS_FAILURE" in detection_types or gps_status == "LOST":
        best_zone, _ = find_nearest_legal_hover_zone(pos, current_battery=battery)
        target = best_zone["center"] if best_zone and not is_position_safe_and_legal(pos) else pos
        dec = DecisionType.RELOCATE_AND_HOVER.value if not is_position_safe_and_legal(pos) else DecisionType.HOVER.value
        return RuleEvaluationResult(
            rule_id="R10_COMM_AND_GPS_LOSS",
            decision=dec,
            priority=58,
            reason="Compound failure: Simultaneous communication and GPS loss. Holding safe station / legal zone.",
            evidence=[
                f"Communication lost for {comm_duration:.1f}s",
                "GPS navigation lost"
            ],
            rejected_options=[{"option": "CONTINUE_MISSION", "reason": "No ground telemetry link and no navigation fix."}],
            alternatives_considered=["CONTINUE_MISSION", "HOVER", "EMERGENCY_LANDING"],
            target_position=target
        )

    # R8: Short comm loss (<= 5s)
    if comm_duration <= config.COMM_WARNING_THRESHOLD:
        return RuleEvaluationResult(
            rule_id="R8_SHORT_COMM_LOSS",
            decision=DecisionType.CONTINUE_MISSION.value,
            priority=50,
            reason=f"Brief telemetry communication drop ({comm_duration:.1f}s <= {config.COMM_WARNING_THRESHOLD}s threshold). Continuing mission under autonomous navigation while attempting reconnect.",
            evidence=[
                f"Communication loss duration: {comm_duration:.1f}s",
                "GPS navigation and sensors healthy",
                "Autonomous onboard flight controller maintaining planned waypoint track"
            ],
            rejected_options=[
                {"option": "RETURN_TO_HOME", "reason": "Unnecessary mission abort for transient radio interference."}
            ],
            alternatives_considered=["RETURN_TO_HOME", "HOVER", "CONTINUE_MISSION"]
        )

    # R9: Long comm loss (> 5s)
    dist_to_home = float(telemetry.get("distance_to_home", 0.0))
    energy_needed = (dist_to_home * config.BATTERY_CONSUMPTION) + config.SAFETY_RESERVE
    if battery >= energy_needed:
        return RuleEvaluationResult(
            rule_id="R9_LONG_COMM_LOSS_RTH",
            decision=DecisionType.RETURN_TO_HOME.value,
            priority=55,
            reason=f"Prolonged communication loss ({comm_duration:.1f}s > {config.COMM_WARNING_THRESHOLD}s threshold). Failsafe autonomous Return-To-Home triggered.",
            evidence=[
                f"Communication loss duration: {comm_duration:.1f}s",
                f"GPS navigation lock verified",
                f"Battery level ({battery:.1f}%) sufficient for RTH ({energy_needed:.1f}% needed)"
            ],
            rejected_options=[
                {"option": "CONTINUE_MISSION", "reason": "Prolonged loss of operator link violates safety regulation."}
            ],
            alternatives_considered=["CONTINUE_MISSION", "HOVER", "RETURN_TO_HOME"],
            target_position=home
        )
    else:
        return RuleEvaluationResult(
            rule_id="R9_LONG_COMM_LOSS_HOVER",
            decision=DecisionType.HOVER.value,
            priority=55,
            reason=f"Prolonged communication loss ({comm_duration:.1f}s) but RTH battery marginal. Holding station for link re-establishment.",
            evidence=[f"Comm loss duration: {comm_duration:.1f}s", f"Battery: {battery:.1f}%"],
            rejected_options=[{"option": "RETURN_TO_HOME", "reason": "Insufficient battery reserve for full return leg."}],
            alternatives_considered=["RETURN_TO_HOME", "HOVER"],
            target_position=pos
        )


def evaluate_r11_r12_low_battery(
    telemetry: Dict[str, Any],
    detection_types: set
) -> Optional[RuleEvaluationResult]:
    """R11 & R12 — LOW BATTERY: Check if destination is safely reachable, else RTH or Land."""
    if "LOW_BATTERY" not in detection_types:
        return None

    battery = float(telemetry.get("battery", 100.0))
    dist_to_dest = float(telemetry.get("distance_to_destination", 100.0))
    dist_to_home = float(telemetry.get("distance_to_home", 0.0))
    consumption_rate = float(telemetry.get("battery_consumption_rate", config.BATTERY_CONSUMPTION))
    reserve = float(config.SAFETY_RESERVE)
    dest = telemetry.get("destination", config.DESTINATION)
    home = telemetry.get("home", config.START)

    energy_to_dest = (dist_to_dest * consumption_rate) + reserve
    energy_to_home = (dist_to_home * consumption_rate) + reserve

    if battery >= energy_to_dest:
        # R11: Destination safely reachable
        return RuleEvaluationResult(
            rule_id="R11_LOW_BATTERY_CONTINUE",
            decision=DecisionType.CONTINUE_MISSION.value,
            priority=40,
            reason=f"Battery level ({battery:.1f}%) is low but destination is safely reachable with required {reserve}% reserve.",
            evidence=[
                f"Battery level: {battery:.1f}%",
                f"Distance to destination: {dist_to_dest:.1f} units (Requires {dist_to_dest * consumption_rate:.1f}% energy)",
                f"Total energy needed with safety reserve: {energy_to_dest:.1f}% <= Available ({battery:.1f}%)"
            ],
            rejected_options=[
                {"option": "RETURN_TO_HOME", "reason": "Destination is closer and requires less energy than returning home."}
            ],
            alternatives_considered=["RETURN_TO_HOME", "CONTINUE_MISSION"],
            target_position=dest
        )
    elif battery >= energy_to_home:
        # R12: Destination not feasible, but Home is reachable
        return RuleEvaluationResult(
            rule_id="R12_LOW_BATTERY_RTH",
            decision=DecisionType.RETURN_TO_HOME.value,
            priority=42,
            reason=f"Battery level ({battery:.1f}%) insufficient to reach destination ({energy_to_dest:.1f}% needed). Returning to Home base ({energy_to_home:.1f}% needed).",
            evidence=[
                f"Battery: {battery:.1f}%",
                f"Energy required to reach destination: {energy_to_dest:.1f}%",
                f"Energy required to return home: {energy_to_home:.1f}%"
            ],
            rejected_options=[
                {"option": "CONTINUE_MISSION", "reason": "Destination distance exceeds remaining battery reserve."}
            ],
            alternatives_considered=["CONTINUE_MISSION", "RETURN_TO_HOME"],
            target_position=home
        )
    else:
        # R12 Fallback: Nearest emergency landing
        pos = telemetry.get("position", home)
        return RuleEvaluationResult(
            rule_id="R12_LOW_BATTERY_LAND",
            decision=DecisionType.EMERGENCY_LANDING.value,
            priority=45,
            reason=f"Battery level ({battery:.1f}%) cannot guarantee safe transit to destination or home base. Initiating controlled emergency landing.",
            evidence=[f"Battery level: {battery:.1f}%", "Both destination and home exceed safe battery envelope"],
            rejected_options=[
                {"option": "CONTINUE_MISSION", "reason": "High risk of mid-air power exhaustion."},
                {"option": "RETURN_TO_HOME", "reason": "Insufficient energy to reach home base."}
            ],
            alternatives_considered=["CONTINUE_MISSION", "RETURN_TO_HOME", "EMERGENCY_LANDING"],
            target_position=pos
        )


def evaluate_r13_gps_degraded(
    telemetry: Dict[str, Any],
    detection_types: set
) -> Optional[RuleEvaluationResult]:
    """R13 — GPS DEGRADED: Mild degradation while confidence is acceptable."""
    if "GPS_DEGRADED" not in detection_types:
        return None

    confidence = float(telemetry.get("gps_confidence", 1.0))
    if confidence >= 0.4:
        return RuleEvaluationResult(
            rule_id="R13_GPS_DEGRADED_CONTINUE",
            decision=DecisionType.CONTINUE_MISSION.value,
            priority=30,
            reason=f"GPS telemetry degraded but estimated confidence ({confidence * 100:.0f}%) remains acceptable for course maintenance. Continuing mission with heightened monitoring.",
            evidence=[
                f"GPS Accuracy: {telemetry.get('gps_accuracy')}m",
                f"Satellites: {telemetry.get('satellites')}",
                f"Calculated GPS confidence: {confidence:.2f}"
            ],
            rejected_options=[
                {"option": "EMERGENCY_LANDING", "reason": "Degradation is minor; vehicle position remains within safety margins."}
            ],
            alternatives_considered=["HOVER", "CONTINUE_MISSION"]
        )
    else:
        # Heavy degradation -> Hover to re-lock
        pos = telemetry.get("position", [10.0, 80.0])
        return RuleEvaluationResult(
            rule_id="R13_GPS_DEGRADED_HOVER",
            decision=DecisionType.HOVER.value,
            priority=35,
            reason=f"GPS confidence ({confidence * 100:.0f}%) is too low for safe flight corridor tracking. Holding station to stabilize satellite lock.",
            evidence=[f"GPS confidence: {confidence:.2f}"],
            rejected_options=[{"option": "CONTINUE_MISSION", "reason": "Position uncertainty exceeds corridor bounds."}],
            alternatives_considered=["CONTINUE_MISSION", "HOVER"],
            target_position=pos
        )


def evaluate_r14_nominal(telemetry: Dict[str, Any]) -> RuleEvaluationResult:
    """R14 — NO FAILURE: All systems nominal."""
    return RuleEvaluationResult(
        rule_id="R14_NOMINAL",
        decision=DecisionType.CONTINUE_MISSION.value,
        priority=0,
        reason="All simulated telemetry streams, sensor locks, energy reserves, and airspace checks are nominal.",
        evidence=["No failures detected", "Battery above threshold", "GPS lock healthy", "Communication link active"],
        rejected_options=[],
        alternatives_considered=[]
    )
