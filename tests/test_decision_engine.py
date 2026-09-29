"""
Tests for decision_engine/decision_engine.py and decision_engine/rules.py
Validates Part M, N, O, P requirements:
- GPS LOSS + LEGAL POSITION -> HOVER
- GPS LOSS + RESTRICTED POSITION -> RELOCATE_AND_HOVER
- CRITICAL BATTERY + FEASIBLE RTH -> RETURN_TO_HOME
- CRITICAL BATTERY + INFEASIBLE RTH -> EMERGENCY_LANDING
- OBSTACLE -> ALTERNATE_ROUTE
- UNAUTHORIZED MOVEMENT -> SECURITY_ESCALATION
- MULTI-FAILURE -> combined decision
- Decision latching and pre-emption
- Explainability fields (reason, evidence, rules_fired, rejected_options)
"""

import pytest
import config
from decision_engine.decision_engine import EmergencyBrain
from decision_engine.interfaces import DecisionType


@pytest.fixture
def brain():
    return EmergencyBrain()


def test_nominal_continue_mission(brain):
    """Nominal conditions produce CONTINUE_MISSION."""
    telem = {
        "battery": 90.0,
        "gps_status": "CONNECTED",
        "gps_accuracy": 3.0,
        "satellites": 10,
        "communication": "CONNECTED",
        "position": [15.0, 75.0],
        "distance_to_home": 5.0,
        "distance_to_destination": 95.0
    }
    decision = brain.evaluate(telem)
    assert decision.decision == DecisionType.CONTINUE_MISSION.value
    assert "R14_NOMINAL" in decision.rules_fired
    assert len(decision.evidence) > 0


def test_gps_loss_legal_position_hover(brain):
    """
    Phase 3 Requirement:
    GPS LOSS + LEGAL POSITION -> HOVER
    """
    telem = {
        "battery": 80.0,
        "gps_status": "LOST",
        "gps_accuracy": 99.0,
        "satellites": 0,
        "communication": "CONNECTED",
        "position": [20.0, 70.0],
        "last_known_position": [20.0, 70.0],  # Outside restricted / private property
        "distance_to_home": 15.0,
        "distance_to_destination": 85.0
    }
    decision = brain.evaluate(telem)
    assert decision.decision == DecisionType.HOVER.value
    assert "R6_GPS_LOST_LEGAL_HOVER" in decision.rules_fired
    assert len(decision.reason) > 0
    assert len(decision.evidence) > 0
    assert len(decision.rejected_options) > 0


def test_gps_loss_restricted_position_relocate_and_hover(brain):
    """
    Phase 3 Flagship Requirement:
    GPS LOSS + RESTRICTED POSITION -> RELOCATE_AND_HOVER
    Must reject hovering at current restricted position and select nearest legal hover zone (HZ1).
    """
    telem = {
        "battery": 80.0,
        "gps_status": "LOST",
        "gps_accuracy": 99.0,
        "satellites": 0,
        "communication": "CONNECTED",
        "position": [50.0, 50.0],
        "last_known_position": [50.0, 50.0],  # INSIDE restricted airspace (42-62, 40-60)
        "distance_to_home": 50.0,
        "distance_to_destination": 50.0
    }
    decision = brain.evaluate(telem)
    assert decision.decision == DecisionType.RELOCATE_AND_HOVER.value
    assert "R5_GPS_LOST_RESTRICTED_ZONE" in decision.rules_fired
    assert decision.selected_zone_id == "HZ1"
    assert decision.target_position == [36.0, 66.0]

    # Verify rejected options contain explanation of why hovering at [50, 50] was rejected
    rejected_reasons = [r["reason"] for r in decision.rejected_options]
    assert any("Restricted Airspace" in r for r in rejected_reasons)


def test_critical_battery_feasible_rth(brain):
    """
    Phase 3 Requirement:
    CRITICAL BATTERY + FEASIBLE RTH -> RETURN_TO_HOME
    """
    telem = {
        "battery": 19.0,                      # <= 20% critical threshold
        "gps_status": "CONNECTED",
        "gps_accuracy": 4.0,
        "satellites": 10,
        "communication": "CONNECTED",
        "position": [20.0, 72.0],
        "last_known_position": [20.0, 72.0],
        "home": [10.0, 80.0],
        "destination": [90.0, 20.0],
        "distance_to_home": 12.8,             # 12.8 * 0.4% = 5.12% + 10% reserve = 15.12% <= 19% -> Feasible
        "distance_to_destination": 85.0,
        "battery_consumption_rate": 0.4
    }
    decision = brain.evaluate(telem)
    assert decision.decision == DecisionType.RETURN_TO_HOME.value
    assert "R2_CRITICAL_BATTERY_RTH" in decision.rules_fired
    assert decision.target_position == [10.0, 80.0]


def test_critical_battery_infeasible_rth_emergency_landing(brain):
    """
    Phase 3 Requirement:
    CRITICAL BATTERY + INFEASIBLE RTH -> EMERGENCY_LANDING
    """
    telem = {
        "battery": 15.0,
        "gps_status": "CONNECTED",
        "communication": "CONNECTED",
        "position": [80.0, 30.0],
        "last_known_position": [80.0, 30.0],
        "home": [10.0, 80.0],
        "distance_to_home": 86.0,             # 86 * 0.4% = 34.4% + 10% reserve = 44.4% > 15% -> Infeasible!
        "distance_to_destination": 15.0,
        "battery_consumption_rate": 0.4
    }
    decision = brain.evaluate(telem)
    assert decision.decision == DecisionType.EMERGENCY_LANDING.value
    assert "R3_CRITICAL_BATTERY_LANDING" in decision.rules_fired


def test_obstacle_alternate_route(brain):
    """
    Phase 3 Requirement:
    OBSTACLE -> ALTERNATE_ROUTE
    """
    telem = {
        "battery": 80.0,
        "gps_status": "CONNECTED",
        "communication": "CONNECTED",
        "obstacle_detected": True,
        "position": [30.0, 60.0],
        "last_known_position": [30.0, 60.0],
        "destination": [90.0, 20.0],
        "battery_consumption_rate": 0.4
    }
    decision = brain.evaluate(telem)
    assert decision.decision == DecisionType.ALTERNATE_ROUTE.value
    assert "R4_OBSTACLE_ALTERNATE_ROUTE" in decision.rules_fired
    assert decision.target_position == [35.0, 25.0]


def test_unauthorized_movement_security_escalation(brain):
    """
    Phase 3 Requirement:
    UNAUTHORIZED MOVEMENT -> SECURITY_ESCALATION
    """
    telem = {
        "battery": 80.0,
        "gps_status": "CONNECTED",
        "communication": "CONNECTED",
        "unauthorized_movement": True,
        "theft_detected": True,
        "position": [35.0, 65.0],
        "last_known_position": [35.0, 65.0]
    }
    decision = brain.evaluate(telem)
    assert decision.decision == DecisionType.SECURITY_ESCALATION.value
    assert "R1_SECURITY" in decision.rules_fired
    assert decision.severity == "CRITICAL"


def test_multi_failure_combined_decision(brain):
    """
    Phase 3 Requirement:
    MULTI-FAILURE -> combined decision with synthesized rules and severity.
    """
    telem = {
        "battery": 18.0,
        "gps_status": "LOST",
        "gps_accuracy": 99.0,
        "satellites": 0,
        "communication": "LOST",
        "comm_loss_duration": 10.0,
        "position": [50.0, 50.0],
        "last_known_position": [50.0, 50.0],
        "distance_to_home": 50.0
    }
    decision = brain.evaluate(telem)
    assert decision.severity == "CRITICAL"
    assert decision.mission_impact == "CRITICAL"
    # Energy / Security takes precedence over pure GPS or Comm
    assert decision.decision in (DecisionType.EMERGENCY_LANDING.value, DecisionType.RELOCATE_AND_HOVER.value)
    assert len(decision.evidence) > 0


def test_decision_latching_and_preemption(brain):
    """
    Part O: Latching prevents flip-flopping.
    Only a strictly higher-priority emergency can pre-empt an executing decision.
    """
    # 1. Establish an initial recovery decision: RELOCATE_AND_HOVER (Priority 75)
    telem_gps_loss = {
        "battery": 80.0,
        "gps_status": "LOST",
        "position": [50.0, 50.0],
        "last_known_position": [50.0, 50.0]
    }
    d1 = brain.evaluate(telem_gps_loss)
    assert d1.decision == DecisionType.RELOCATE_AND_HOVER.value
    assert brain.latched_decision is not None

    # 2. Simulate a lower-priority event occurring simultaneously (e.g. comm loss, Priority 55)
    # The brain must retain the latched decision (RELOCATE_AND_HOVER) rather than flip-flopping
    telem_comm_loss = dict(telem_gps_loss, communication="LOST", comm_loss_duration=6.0)
    d2 = brain.evaluate(telem_comm_loss)
    assert d2.decision == DecisionType.RELOCATE_AND_HOVER.value

    # 3. Simulate a strictly higher-priority emergency: CRITICAL_BATTERY with infeasible RTH (Priority 92)
    # The brain must pre-empt the latched decision!
    telem_crit_bat = dict(telem_comm_loss, battery=12.0, distance_to_home=60.0)
    d3 = brain.evaluate(telem_crit_bat)
    assert d3.decision == DecisionType.EMERGENCY_LANDING.value
    assert len(brain.preemption_log) > 0
    assert brain.preemption_log[0]["previous_decision"] == DecisionType.RELOCATE_AND_HOVER.value
    assert brain.preemption_log[0]["new_decision"] == DecisionType.EMERGENCY_LANDING.value
