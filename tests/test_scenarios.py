"""
Tests for simulator/scenarios.py
Phase 4 Exit Gate requirements:
- Flagship scenario end-to-end execution
- Critical low battery scenario
- Obstacle blocked route scenario
- Multi-failure emergency scenario
- Unauthorized movement scenario
- Intentionally failing verification demonstration
"""

import pytest
from simulator.scenarios import ScenarioOrchestrator
from decision_engine.interfaces import SystemState


def test_flagship_scenario_end_to_end():
    """
    Mandatory Phase 4 Exit Gate Flagship Scenario:
    GPS LOSS -> HIGH -> RESTRICTED -> RELOCATE_AND_HOVER -> HZ1 -> VERIFY -> GPS RESTORED -> MISSION RESUMED -> COMPLETED.
    """
    orch = ScenarioOrchestrator(mission_id="TEST-FLAGSHIP-001")
    result = orch.run_flagship_scenario()

    assert result["status"] == SystemState.MISSION_COMPLETED.value

    # Verify event types and ordered execution
    events = result["events"]
    event_types = [e["event_type"] for e in events]

    assert "MISSION_STARTED" in event_types
    assert "GPS_FAILURE_DETECTED" in event_types
    assert "FAILURE_CLASSIFIED" in event_types
    assert "EMERGENCY_BRAIN_DECISION" in event_types
    assert "RECOVERY_EXECUTION_STARTED" in event_types
    assert "HOVER_ZONE_REACHED" in event_types
    assert "GPS_RESTORED" in event_types
    assert "MISSION_RESUMED" in event_types
    assert "MISSION_COMPLETED" in event_types

    # Verify decision chosen was RELOCATE_AND_HOVER to HZ1
    decision_ev = next(e for e in events if e["event_type"] == "EMERGENCY_BRAIN_DECISION")
    assert decision_ev["decision"] == "RELOCATE_AND_HOVER"
    assert "HZ1" in decision_ev["message"]

    # Verify HZ1 arrived and verified
    hover_ev = next(e for e in events if e["event_type"] == "HOVER_ZONE_REACHED")
    assert hover_ev["verification"] == "PASS"


def test_critical_battery_scenario_end_to_end():
    """Critical low battery returns home and completes."""
    orch = ScenarioOrchestrator(mission_id="TEST-BATTERY-002")
    result = orch.run_critical_battery_scenario()
    assert result["status"] == SystemState.MISSION_COMPLETED.value
    event_types = [e["event_type"] for e in result["events"]]
    assert "RTH_VERIFIED" in event_types


def test_obstacle_scenario_end_to_end():
    """Obstacle scenario generates alternate route and verifies avoidance."""
    orch = ScenarioOrchestrator(mission_id="TEST-OBSTACLE-003")
    result = orch.run_obstacle_scenario()
    assert result["status"] == SystemState.MISSION_RESUMED.value
    event_types = [e["event_type"] for e in result["events"]]
    assert "OBSTACLE_AVOIDANCE_VERIFIED" in event_types


def test_multi_failure_scenario_end_to_end():
    """Multi-failure emergency yields critical severity decision."""
    orch = ScenarioOrchestrator(mission_id="TEST-MULTI-004")
    result = orch.run_multi_failure_scenario()
    assert result["decision"]["severity"] == "CRITICAL"
    assert result["decision"]["mission_impact"] == "CRITICAL"


def test_unauthorized_movement_scenario_end_to_end():
    """Unauthorized movement scenario locks security escalation."""
    orch = ScenarioOrchestrator(mission_id="TEST-SECURITY-005")
    result = orch.run_unauthorized_movement_scenario()
    assert result["decision"]["decision"] == "SECURITY_ESCALATION"
    assert result["decision"]["severity"] == "CRITICAL"


def test_communication_scenario_end_to_end():
    """Prolonged communication failure triggers autonomous RTH and completes."""
    orch = ScenarioOrchestrator(mission_id="TEST-COMM-007")
    result = orch.run_communication_failure_scenario()
    assert result["status"] == SystemState.MISSION_COMPLETED.value
    event_types = [e["event_type"] for e in result["events"]]
    assert "COMM_FAILSAFE_RTH_VERIFIED" in event_types


def test_flagship_scenario_deterministic_three_runs():
    """
    Phase 7 Mandatory Exit Gate Requirement:
    Run flagship scenario three times.
    Expected:
    - Same event order
    - Same decision
    - Same recovery
    - Same final result
    This proves deterministic behavior.
    """
    run_results = []
    for i in range(3):
        orch = ScenarioOrchestrator(mission_id=f"DETERMINISTIC-RUN-{i+1}")
        result = orch.run_flagship_scenario()
        run_results.append(result)

    first_events = [e["event_type"] for e in run_results[0]["events"]]
    first_decision = next(e["decision"] for e in run_results[0]["events"] if e["event_type"] == "EMERGENCY_BRAIN_DECISION")
    first_action = next(e["action"] for e in run_results[0]["events"] if e["event_type"] == "RECOVERY_EXECUTION_STARTED")
    first_status = run_results[0]["status"]

    assert first_status == SystemState.MISSION_COMPLETED.value
    assert first_decision == "RELOCATE_AND_HOVER"
    assert first_action == "RELOCATE_AND_HOVER"

    for i in (1, 2):
        other_events = [e["event_type"] for e in run_results[i]["events"]]
        other_decision = next(e["decision"] for e in run_results[i]["events"] if e["event_type"] == "EMERGENCY_BRAIN_DECISION")
        other_action = next(e["action"] for e in run_results[i]["events"] if e["event_type"] == "RECOVERY_EXECUTION_STARTED")
        other_status = run_results[i]["status"]

        # Exact deterministic equality checks
        assert other_events == first_events, f"Run {i+1} produced different event sequence!"
        assert other_decision == first_decision, f"Run {i+1} produced different decision!"
        assert other_action == first_action, f"Run {i+1} produced different recovery action!"
        assert other_status == first_status, f"Run {i+1} produced different terminal state!"


def test_intentionally_failing_verification_end_to_end():
    """Verification failure demonstration proves verification never assumes success."""
    orch = ScenarioOrchestrator(mission_id="TEST-FAIL-VERIF-006")
    result = orch.run_intentionally_failing_verification()
    assert result["hover_verification"]["status"] == "FAILED"
    assert result["relocation_verification"]["status"] == "FAILED"

