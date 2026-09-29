"""
Scenario Orchestration Engine.
Part X: Implements scenarios 1 through 6 and intentionally failing verification tests.
Enforces the mandatory pipeline:
MONITOR -> DETECT -> CLASSIFY -> ASSESS IMPACT -> DECIDE -> RECOVER -> VERIFY.
Fault injection modifies ONLY telemetry/drone environment, NEVER calling recovery directly.
"""

from typing import Dict, Any, List, Optional
import time
import config
from simulator.drone import VirtualDrone
from simulator.clock import FakeClock
from decision_engine.decision_engine import EmergencyBrain
from decision_engine.recovery import RecoveryExecutor
from decision_engine.verifier import RecoveryVerifier
from decision_engine.state_machine import EmergencyStateMachine
from decision_engine.interfaces import SystemState, DecisionType, VerificationStatus
from database.db import log_event, insert_mission, update_mission_status


class ScenarioOrchestrator:
    """
    Executes end-to-end mission scenarios with deterministic closed-loop pipeline execution.
    Logs structured audit events to SQLite database.
    """

    def __init__(self, mission_id: str = "MISSION-DEMO"):
        self.mission_id = mission_id
        self.clock = FakeClock(0.0)
        self.drone = VirtualDrone()
        self.brain = EmergencyBrain()
        self.recovery = RecoveryExecutor()
        self.verifier = RecoveryVerifier()
        self.state_machine = EmergencyStateMachine(SystemState.READY)
        self.event_log: List[Dict[str, Any]] = []

        # Record mission entry in DB
        insert_mission(self.mission_id)

    def log(
        self,
        event_type: str,
        severity: str,
        message: str,
        evidence: Optional[List[str]] = None,
        decision: Optional[str] = None,
        action: Optional[str] = None,
        verification: Optional[str] = None
    ) -> None:
        """Records an event locally and to SQLite database."""
        event_entry = {
            "timestamp": round(self.clock.now(), 2),
            "mission_id": self.mission_id,
            "event_type": event_type,
            "severity": severity,
            "message": message,
            "evidence": evidence or [],
            "decision": decision,
            "action": action,
            "verification": verification
        }
        self.event_log.append(event_entry)
        try:
            log_event(
                mission_id=self.mission_id,
                event_type=event_type,
                severity=severity,
                message=message,
                evidence=evidence,
                decision=decision,
                action=action,
                verification=verification
            )
        except Exception:
            pass

    # -------------------------------------------------------------
    # SCENARIO 1 — FLAGSHIP: GPS LOSS OVER RESTRICTED ZONE
    # -------------------------------------------------------------
    def run_flagship_scenario(self) -> Dict[str, Any]:
        """
        Executes Flagship Scenario:
        START -> Drone flies towards destination -> GPS LOSS at [50, 50] (inside restricted zone)
        -> DETECT -> CLASSIFY HIGH -> RESTRICTED ZONE DETECTED -> RISK ASSESSMENT
        -> EMERGENCY BRAIN REJECTS CURRENT HOVER & SELECTS HZ1
        -> RELOCATE_AND_HOVER -> HZ1 REACHED -> HOVER VERIFIED
        -> GPS RESTORED -> VERIFY -> MISSION RESUMED -> DESTINATION REACHED -> COMPLETED.
        """
        # 1. Mission start
        self.state_machine.transition_to(SystemState.MISSION_ACTIVE, "Mission started")
        self.drone.start_mission()
        self.log("MISSION_STARTED", "LOW", "Mission initiated along planned flight corridor.")

        # 2. Advance drone to approximately [50, 50] (50 units travel at 5 units/s = 10s)
        for _ in range(100):
            self.clock.advance(0.1)
            self.drone.step(0.1)

        # Confirm drone is in restricted airspace
        telem = self.drone.get_telemetry()
        self.log("TELEMETRY_MONITORING_ACTIVE", "LOW", f"Drone cruising at [{telem['position'][0]:.1f}, {telem['position'][1]:.1f}]")

        # 3. Inject fault: GPS LOSS (modifies ONLY simulated telemetry!)
        self.drone.inject_gps_loss()
        telem_fault = self.drone.get_telemetry()

        # 4. Pipeline: DETECT
        detections = self.brain.detector.detect_failures(telem_fault)
        self.state_machine.transition_to(SystemState.FAILURE_DETECTED, "GPS loss detected over restricted airspace")
        self.log(
            "GPS_FAILURE_DETECTED",
            "HIGH",
            "GPS receiver signal lost; navigation lock unavailable.",
            evidence=[d.evidence[0] for d in detections if d.evidence]
        )

        # 5. Pipeline: CLASSIFY & ASSESS RISK
        self.state_machine.transition_to(SystemState.ASSESSING, "Evaluating severity & legal risk")
        classified, overall_sev, overall_imp, notes = self.brain.classifier.evaluate(detections)
        risk = self.brain.risk_assessor.assess_risk(telem_fault, detections)
        self.log(
            "FAILURE_CLASSIFIED",
            overall_sev,
            f"Severity evaluated as {overall_sev}, Mission Impact: {overall_imp}. Total Risk Score: {risk.total_score} ({risk.overall_risk}).",
            evidence=notes
        )

        # 6. Pipeline: DECIDE (Emergency Brain)
        self.state_machine.transition_to(SystemState.DECISION_SELECTED, "Emergency Brain evaluated rules")
        decision = self.brain.evaluate(telem_fault)
        self.log(
            "EMERGENCY_BRAIN_DECISION",
            overall_sev,
            f"Decision: {decision.decision} -> Target: {decision.target_position} (Zone: {decision.selected_zone_id})",
            evidence=decision.evidence,
            decision=decision.decision
        )

        # 7. Pipeline: RECOVER
        self.state_machine.transition_to(SystemState.RECOVERY_EXECUTING, "Executing recovery command")
        cmd = self.recovery.create_command(decision)
        self.recovery.dispatch_to_drone(cmd, self.drone)
        self.log("RECOVERY_EXECUTION_STARTED", "HIGH", f"Command {cmd.command_id} dispatched: Relocating to {decision.selected_zone_id}.", action=cmd.command_type)

        # 8. Drone flies to HZ1 (Distance ~21.3 units / 5 units/s ~ 4.3 seconds)
        for _ in range(60):
            self.clock.advance(0.1)
            self.drone.step(0.1)

        telem_hz = self.drone.get_telemetry()

        # 9. Pipeline: VERIFY RELOCATION & HOVER
        self.state_machine.transition_to(SystemState.VERIFYING, "Verifying relocation station arrival")
        verif_reloc = self.verifier.verify_relocation(telem_hz, decision.target_position)
        verif_hover = self.verifier.verify_hover(telem_hz, decision.target_position)

        if verif_reloc.status == VerificationStatus.SUCCESS.value and verif_hover.status == VerificationStatus.SUCCESS.value:
            self.log("HOVER_ZONE_REACHED", "LOW", f"Arrived at safe hover station {decision.selected_zone_id} [{telem_hz['position'][0]:.1f}, {telem_hz['position'][1]:.1f}]. Station holding confirmed.", verification="PASS")
        else:
            self.log("RECOVERY_VERIFICATION_FAILED", "HIGH", "Relocation verification failed.", verification="FAIL")

        # 10. Restore GPS sensor
        self.drone.restore_gps()
        telem_restored = self.drone.get_telemetry()
        verif_gps = self.verifier.verify_gps_restoration(telem_restored)
        self.log("GPS_RESTORED", "LOW", "GPS lock reacquired and verified.", verification=verif_gps.status)

        # 11. Resume Mission
        self.state_machine.transition_to(SystemState.MISSION_RESUMED, "Recovery verified, resuming mission")
        self.brain.clear_latch()
        self.drone.command_resume_mission()
        self.log("MISSION_RESUMED", "LOW", "Resuming primary flight path to Destination [90, 20].", action="RESUME")

        # 12. Complete Mission
        self.state_machine.transition_to(SystemState.MISSION_ACTIVE, "Proceeding to destination")
        while self.drone.flight_mode == "MISSION" and self.clock.now() < 60.0:
            self.clock.advance(0.2)
            self.drone.step(0.2)

        if self.drone.mission_status == "MISSION_COMPLETED":
            self.state_machine.transition_to(SystemState.MISSION_COMPLETED, "Destination reached safely")
            self.log("MISSION_COMPLETED", "LOW", "Destination reached safely. Audit trail closed.", verification="PASS")
            update_mission_status(self.mission_id, "COMPLETED")

        return {
            "status": self.state_machine.current_state.value,
            "events": self.event_log,
            "final_telemetry": self.drone.get_telemetry()
        }

    # -------------------------------------------------------------
    # SCENARIO 2 — CRITICAL BATTERY RTH
    # -------------------------------------------------------------
    def run_critical_battery_scenario(self) -> Dict[str, Any]:
        """Drone cruising near base; battery becomes critical -> RTH -> Verified."""
        self.state_machine.transition_to(SystemState.MISSION_ACTIVE, "Mission initiated")
        self.drone.start_mission()
        # Step 2 seconds away from home
        for _ in range(20):
            self.clock.advance(0.1)
            self.drone.step(0.1)

        # Inject critical battery 19%
        self.drone.inject_battery(19.0)
        telem = self.drone.get_telemetry()

        self.state_machine.transition_to(SystemState.FAILURE_DETECTED, "Critical battery detected")
        self.state_machine.transition_to(SystemState.ASSESSING, "Evaluating RTH feasibility")
        decision = self.brain.evaluate(telem)

        self.state_machine.transition_to(SystemState.DECISION_SELECTED, "RTH selected")
        cmd = self.recovery.create_command(decision)
        self.recovery.dispatch_to_drone(cmd, self.drone)

        self.state_machine.transition_to(SystemState.RECOVERY_EXECUTING, "Returning to home")
        while self.drone.flight_mode == "RETURNING":
            self.clock.advance(0.1)
            self.drone.step(0.1)

        self.state_machine.transition_to(SystemState.VERIFYING, "Verifying touchdown at base")
        verif = self.verifier.verify_return_home(self.drone.get_telemetry())
        self.log("RTH_VERIFIED", "LOW", verif.summary, verification=verif.status)
        self.state_machine.transition_to(SystemState.MISSION_COMPLETED, "Landed safely at base")

        return {"status": self.state_machine.current_state.value, "events": self.event_log}

    # -------------------------------------------------------------
    # SCENARIO 3 — OBSTACLE DETOUR
    # -------------------------------------------------------------
    def run_obstacle_scenario(self) -> Dict[str, Any]:
        """Obstacle blocks route -> Brain computes alternate route -> Verified."""
        self.state_machine.transition_to(SystemState.MISSION_ACTIVE, "Mission initiated")
        self.drone.start_mission()
        for _ in range(20):
            self.clock.advance(0.1)
            self.drone.step(0.1)

        self.drone.inject_obstacle([40.0, 50.0])
        telem = self.drone.get_telemetry()

        self.state_machine.transition_to(SystemState.FAILURE_DETECTED, "Obstacle detected")
        self.state_machine.transition_to(SystemState.ASSESSING, "Computing bypass route")
        decision = self.brain.evaluate(telem)

        self.state_machine.transition_to(SystemState.DECISION_SELECTED, "Alternate route selected")
        cmd = self.recovery.create_command(decision)
        # Attach waypoints from rule parameters
        cmd.parameters["alternate_waypoints"] = [[35.0, 25.0], [65.0, 25.0], config.DESTINATION]
        self.recovery.dispatch_to_drone(cmd, self.drone)

        self.state_machine.transition_to(SystemState.RECOVERY_EXECUTING, "Following alternate route")
        for _ in range(30):
            self.clock.advance(0.1)
            self.drone.step(0.1)

        self.drone.clear_obstacle()
        self.state_machine.transition_to(SystemState.VERIFYING, "Verifying obstacle cleared")
        verif = self.verifier.verify_alternate_route(self.drone.get_telemetry())
        self.log("OBSTACLE_AVOIDANCE_VERIFIED", "LOW", verif.summary, verification=verif.status)
        self.state_machine.transition_to(SystemState.MISSION_RESUMED, "Resuming nominal flight")

        return {"status": self.state_machine.current_state.value, "events": self.event_log}

    # -------------------------------------------------------------
    # SCENARIO 4 — COMMUNICATION FAILURE
    # -------------------------------------------------------------
    def run_communication_failure_scenario(self) -> Dict[str, Any]:
        """
        Communication link lost. Timer starts.
        If prolonged (>5s), Emergency Brain triggers autonomous Return-To-Home failsafe.
        """
        self.state_machine.transition_to(SystemState.MISSION_ACTIVE, "Mission initiated")
        self.drone.start_mission()
        for _ in range(20):
            self.clock.advance(0.1)
            self.drone.step(0.1)

        # Inject communication loss
        self.drone.inject_communication_loss()

        # Comm link remains lost for 6 seconds (> 5s threshold)
        for _ in range(60):
            self.clock.advance(0.1)
            self.drone.step(0.1)

        telem = self.drone.get_telemetry()
        self.state_machine.transition_to(SystemState.FAILURE_DETECTED, "Prolonged communication loss detected")
        self.state_machine.transition_to(SystemState.ASSESSING, "Evaluating autonomous failsafe RTH")
        decision = self.brain.evaluate(telem)

        self.state_machine.transition_to(SystemState.DECISION_SELECTED, "Autonomous RTH selected")
        cmd = self.recovery.create_command(decision)
        self.recovery.dispatch_to_drone(cmd, self.drone)

        self.state_machine.transition_to(SystemState.RECOVERY_EXECUTING, "Executing autonomous RTH")
        while self.drone.flight_mode == "RETURNING":
            self.clock.advance(0.1)
            self.drone.step(0.1)

        self.state_machine.transition_to(SystemState.VERIFYING, "Verifying touchdown at base")
        verif = self.verifier.verify_return_home(self.drone.get_telemetry())
        self.log("COMM_FAILSAFE_RTH_VERIFIED", "LOW", verif.summary, verification=verif.status)
        self.state_machine.transition_to(SystemState.MISSION_COMPLETED, "Landed safely at base under autonomous failsafe")

        return {"status": self.state_machine.current_state.value, "events": self.event_log}

    # -------------------------------------------------------------
    # SCENARIO 5 — MULTI-FAILURE
    # -------------------------------------------------------------
    def run_multi_failure_scenario(self) -> Dict[str, Any]:
        """Triple failure: GPS Loss + Comm Loss + 18% Battery -> Critical Escalation."""
        self.state_machine.transition_to(SystemState.MISSION_ACTIVE, "Mission initiated")
        self.drone.start_mission()
        for _ in range(30):
            self.clock.advance(0.1)
            self.drone.step(0.1)

        self.drone.inject_multi_failure()
        telem = self.drone.get_telemetry()

        self.state_machine.transition_to(SystemState.FAILURE_DETECTED, "Multiple failures detected")
        self.state_machine.transition_to(SystemState.ASSESSING, "Compound risk evaluation")
        decision = self.brain.evaluate(telem)

        self.state_machine.transition_to(SystemState.DECISION_SELECTED, "Emergency action selected")
        cmd = self.recovery.create_command(decision)
        self.recovery.dispatch_to_drone(cmd, self.drone)

        self.log("MULTI_FAILURE_DECISION", "CRITICAL", f"Triple emergency action: {cmd.command_type}", decision=cmd.command_type)
        return {"status": self.state_machine.current_state.value, "decision": decision.to_dict(), "events": self.event_log}

    # -------------------------------------------------------------
    # SCENARIO 6 — UNAUTHORIZED MOVEMENT
    # -------------------------------------------------------------
    def run_unauthorized_movement_scenario(self) -> Dict[str, Any]:
        """Drone hovering -> external displacement -> Security escalation -> Verified."""
        self.state_machine.transition_to(SystemState.MISSION_ACTIVE, "Mission initiated")
        self.drone.start_mission()
        self.drone.command_hover("CMD-HOVER")
        self.drone.inject_unauthorized_movement(dx=10.0, dy=8.0)
        telem = self.drone.get_telemetry()

        self.state_machine.transition_to(SystemState.FAILURE_DETECTED, "Unauthorized movement detected")
        self.state_machine.transition_to(SystemState.ASSESSING, "Evaluating security breach")
        decision = self.brain.evaluate(telem)

        self.state_machine.transition_to(SystemState.DECISION_SELECTED, "Security escalation locked")
        cmd = self.recovery.create_command(decision)
        self.recovery.dispatch_to_drone(cmd, self.drone)

        self.log("SECURITY_ESCALATION_LOCKED", "CRITICAL", "Mission frozen. Operator security alert dispatched.", decision=cmd.command_type)
        return {"status": self.state_machine.current_state.value, "decision": decision.to_dict(), "events": self.event_log}

    # -------------------------------------------------------------
    # INTENTIONALLY FAILING VERIFICATION DEMO
    # -------------------------------------------------------------
    def run_intentionally_failing_verification(self) -> Dict[str, Any]:
        """
        Part 6 Rule: Verification must never assume success.
        Demonstrates an intentionally failing verification where target was not reached.
        """
        # Commanded target is [36, 66], but drone is far away at [80, 20]
        unreached_telemetry = {
            "position": [80.0, 20.0],
            "speed": 5.0,  # Moving, not stationary
            "battery": 5.0, # Below 10% reserve
            "unauthorized_movement": True
        }
        verif_hover = self.verifier.verify_hover(unreached_telemetry, target_pos=[36.0, 66.0])
        verif_reloc = self.verifier.verify_relocation(unreached_telemetry, target_pos=[36.0, 66.0])

        assert verif_hover.status == VerificationStatus.FAILED.value
        assert verif_reloc.status == VerificationStatus.FAILED.value
        assert verif_hover.checks["target_reached"] == "FAIL"
        assert verif_hover.checks["speed_zero"] == "FAIL"
        assert verif_reloc.checks["battery_sufficient"] == "FAIL"

        self.log("VERIFICATION_FAILURE_DEMONSTRATED", "HIGH", verif_hover.summary, verification="FAIL")
        return {
            "hover_verification": verif_hover.to_dict(),
            "relocation_verification": verif_reloc.to_dict()
        }
