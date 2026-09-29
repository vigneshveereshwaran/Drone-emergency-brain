"""
System Controller and Mission Coordinator.
Bridges the Virtual Drone Simulator, Emergency Brain, State Machine, and Audit Logging
without coupling decision logic into the simulator or actuators.
"""

import time
import threading
from typing import Dict, Any, List, Optional
import config
from simulator.drone import VirtualDrone
from simulator.clock import RealClock
from simulator.geofence import GeofenceManager
from decision_engine.decision_engine import EmergencyBrain
from decision_engine.recovery import RecoveryExecutor
from decision_engine.verifier import RecoveryVerifier
from decision_engine.state_machine import EmergencyStateMachine
from decision_engine.interfaces import SystemState, DecisionType, VerificationStatus
from database.db import log_event, insert_mission, update_mission_status, get_events


class SystemController:
    """
    Central controller managing simulation ticking, pipeline execution,
    thread-safe telemetry access, and fault injections.
    """

    def __init__(self, mission_id: str = "MISSION-001"):
        self.mission_id = mission_id
        self.geofence = GeofenceManager()
        self.drone = VirtualDrone(geofence_mgr=self.geofence)
        self.clock = RealClock(time_scale=1.0)
        self.brain = EmergencyBrain()
        self.recovery = RecoveryExecutor()
        self.verifier = RecoveryVerifier()
        self.state_machine = EmergencyStateMachine(SystemState.READY)

        self._lock = threading.Lock()
        self._is_running = False
        self._loop_thread: Optional[threading.Thread] = None
        self.tick_dt = 0.1  # 10 Hz

        # Active recovery tracking
        self.active_recovery_target: Optional[List[float]] = None
        self.active_decision: Optional[Dict[str, Any]] = None

        insert_mission(self.mission_id)

    # -------------------------------------------------------------
    # LIFECYCLE & TICK PIPELINE
    # -------------------------------------------------------------
    def start_mission(self) -> None:
        """Arms drone and starts real-time simulation background loop."""
        with self._lock:
            if self.state_machine.current_state == SystemState.READY:
                self.state_machine.transition_to(SystemState.MISSION_ACTIVE, "Mission initiated")
            self.drone.start_mission()
            self._is_running = True
            log_event(self.mission_id, "MISSION_STARTED", "LOW", "Mission initiated along planned flight corridor.")

            if not self._loop_thread or not self._loop_thread.is_alive():
                self._loop_thread = threading.Thread(target=self._run_loop, daemon=True)
                self._loop_thread.start()

    def pause_mission(self) -> None:
        """Pauses in-flight movement."""
        with self._lock:
            self._is_running = False
            self.drone.pause_mission()
            log_event(self.mission_id, "MISSION_PAUSED", "LOW", "Mission movement paused by operator.")

    def reset(self) -> None:
        """Resets all simulation and state machine components."""
        with self._lock:
            self._is_running = False
            self.drone.reset()
            self.brain.clear_latch()
            self.state_machine.reset()
            self.active_recovery_target = None
            self.active_decision = None
            insert_mission(self.mission_id, status="READY")
            log_event(self.mission_id, "SYSTEM_RESET", "LOW", "System reset to initial state.")

    def set_simulation_speed(self, multiplier: float) -> None:
        """Sets real-time speed multiplier (1x, 2x, 4x)."""
        with self._lock:
            self.clock.time_scale = multiplier

    # -------------------------------------------------------------
    # TICK PIPELINE: MONITOR -> DETECT -> CLASSIFY -> DECIDE -> RECOVER -> VERIFY
    # -------------------------------------------------------------
    def step_pipeline(self, dt: Optional[float] = None) -> Dict[str, Any]:
        """
        Executes one full step of the pipeline.
        Thread-safe and deterministic.
        """
        step_dt = dt if dt is not None else self.tick_dt
        with self._lock:
            self.clock.advance(step_dt)
            self.drone.step(step_dt)
            telem = self.drone.get_telemetry()
            current_state = self.state_machine.current_state

            # 1. EVALUATION DURING ACTIVE MISSION
            if current_state in (SystemState.MISSION_ACTIVE, SystemState.MISSION_RESUMED):
                detections = self.brain.detector.detect_failures(telem)
                if detections:
                    # Anomaly detected!
                    self.state_machine.transition_to(SystemState.FAILURE_DETECTED, "Telemetry anomaly detected")
                    log_event(
                        self.mission_id,
                        "FAILURE_DETECTED",
                        "HIGH",
                        f"Detected {len(detections)} anomaly: {detections[0].type}",
                        evidence=detections[0].evidence
                    )

                    # Assess
                    self.state_machine.transition_to(SystemState.ASSESSING, "Evaluating severity & risk")
                    decision = self.brain.evaluate(telem)
                    self.active_decision = decision.to_dict()

                    # Decide
                    self.state_machine.transition_to(SystemState.DECISION_SELECTED, f"Emergency Brain chose {decision.decision}")
                    log_event(
                        self.mission_id,
                        "DECISION_SELECTED",
                        decision.severity,
                        f"Emergency Brain decision: {decision.decision} - {decision.reason}",
                        evidence=decision.evidence,
                        decision=decision.decision
                    )

                    # Recover
                    if decision.decision != DecisionType.CONTINUE_MISSION.value:
                        self.state_machine.transition_to(SystemState.RECOVERY_EXECUTING, "Executing recovery command")
                        cmd = self.recovery.create_command(decision)
                        # Pass alternate waypoints if obstacle
                        if decision.decision == DecisionType.ALTERNATE_ROUTE.value:
                            cmd.parameters["alternate_waypoints"] = [[35.0, 25.0], [65.0, 25.0], config.DESTINATION]
                        self.recovery.dispatch_to_drone(cmd, self.drone)
                        self.active_recovery_target = decision.target_position
                        log_event(
                            self.mission_id,
                            "RECOVERY_EXECUTING",
                            decision.severity,
                            f"Dispatched {cmd.command_type} (ID: {cmd.command_id})",
                            action=cmd.command_type
                        )
                    else:
                        self.state_machine.transition_to(SystemState.MISSION_RESUMED, "Continuing under nominal monitoring")

            # 2. EVALUATION DURING RECOVERY EXECUTION
            elif current_state == SystemState.RECOVERY_EXECUTING:
                # Check if recovery objective reached
                if self.drone.flight_mode in ("HOVER", "LANDED"):
                    self.state_machine.transition_to(SystemState.VERIFYING, "Recovery target reached; starting verification")

            # 3. EVALUATION DURING VERIFICATION
            elif current_state == SystemState.VERIFYING:
                # Verify based on active flight mode
                if self.drone.flight_mode == "HOVER":
                    verif = self.verifier.verify_hover(telem, target_pos=self.active_recovery_target)
                    log_event(self.mission_id, "HOVER_VERIFIED", "LOW", verif.summary, verification=verif.status)
                    # If GPS restored and vehicle safe in hover zone, resume mission
                    if telem.get("gps_status") == "CONNECTED" and not telem.get("obstacle_detected"):
                        self.state_machine.transition_to(SystemState.MISSION_RESUMED, "Recovery verified and GPS lock restored")
                        self.brain.clear_latch()
                        self.drone.command_resume_mission()
                        log_event(self.mission_id, "MISSION_RESUMED", "LOW", "Resuming mission to destination", action="RESUME")
                        self.state_machine.transition_to(SystemState.MISSION_ACTIVE, "Navigating to destination")

                elif self.drone.flight_mode == "LANDED":
                    verif = self.verifier.verify_return_home(telem)
                    log_event(self.mission_id, "RTH_VERIFIED", "LOW", verif.summary, verification=verif.status)
                    self.state_machine.transition_to(SystemState.MISSION_COMPLETED, "Safely landed at base")
                    update_mission_status(self.mission_id, "COMPLETED")

            # 4. NORMAL MISSION COMPLETION CHECK
            elif current_state == SystemState.MISSION_ACTIVE:
                if self.drone.mission_status == "MISSION_COMPLETED":
                    self.state_machine.transition_to(SystemState.MISSION_COMPLETED, "Destination reached safely")
                    log_event(self.mission_id, "MISSION_COMPLETED", "LOW", "Destination reached safely", verification="PASS")
                    update_mission_status(self.mission_id, "COMPLETED")

            return telem

    def _run_loop(self) -> None:
        """Continuous background execution loop."""
        last_time = time.time()
        while True:
            with self._lock:
                if not self._is_running:
                    break
            now = time.time()
            elapsed = now - last_time
            if elapsed >= self.tick_dt:
                self.step_pipeline(self.tick_dt)
                last_time = now
            else:
                time.sleep(max(0.005, self.tick_dt - elapsed))

    # -------------------------------------------------------------
    # QUERY INTERFACES
    # -------------------------------------------------------------
    def get_state(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "state": self.state_machine.current_state.value,
                "mission_id": self.mission_id,
                "flight_mode": self.drone.flight_mode,
                "mission_status": self.drone.mission_status,
                "is_terminal": self.state_machine.is_terminal,
                "is_running": self._is_running,
                "sim_time": round(self.clock.now(), 2),
                "history": self.state_machine.history
            }

    def get_telemetry(self) -> Dict[str, Any]:
        with self._lock:
            return self.drone.get_telemetry()

    def get_decision_evaluation(self) -> Dict[str, Any]:
        """Runs full evaluation on demand without altering state."""
        with self._lock:
            telem = self.drone.get_telemetry()
            detections = self.brain.detector.detect_failures(telem)
            classifications, overall_sev, overall_imp, notes = self.brain.classifier.evaluate(detections)
            risk = self.brain.risk_assessor.assess_risk(telem, detections)
            decision = self.brain.evaluate(telem)
            return {
                "decision": decision.to_dict(),
                "risk": risk.to_dict(),
                "detections": [d.to_dict() for d in detections],
                "classifications": [c.to_dict() for c in classifications],
                "overall_severity": overall_sev,
                "mission_impact": overall_imp,
                "notes": notes
            }

    # -------------------------------------------------------------
    # FAULT INJECTIONS (Part I: Modifies ONLY simulated environment)
    # -------------------------------------------------------------
    def inject_gps_loss(self) -> None:
        with self._lock:
            self.drone.inject_gps_loss()
            log_event(self.mission_id, "FAULT_INJECTED", "HIGH", "Simulated GPS signal lost.")

    def restore_gps(self) -> None:
        with self._lock:
            self.drone.restore_gps()
            log_event(self.mission_id, "SENSOR_RESTORED", "LOW", "Simulated GPS signal restored.")

    def inject_gps_degrade(self) -> None:
        with self._lock:
            self.drone.inject_gps_degrade()
            log_event(self.mission_id, "FAULT_INJECTED", "LOW", "Simulated GPS accuracy degraded.")

    def inject_battery(self, level: float) -> None:
        with self._lock:
            self.drone.inject_battery(level)
            log_event(self.mission_id, "FAULT_INJECTED", "MEDIUM" if level > 20 else "HIGH", f"Simulated battery set to {level}%.")

    def inject_comm_loss(self) -> None:
        with self._lock:
            self.drone.inject_communication_loss()
            log_event(self.mission_id, "FAULT_INJECTED", "MEDIUM", "Simulated communication link lost.")

    def restore_comm(self) -> None:
        with self._lock:
            self.drone.restore_communication()
            log_event(self.mission_id, "LINK_RESTORED", "LOW", "Simulated communication link restored.")

    def inject_obstacle(self) -> None:
        with self._lock:
            self.drone.inject_obstacle()
            log_event(self.mission_id, "FAULT_INJECTED", "HIGH", "Simulated obstacle injected on active route.")

    def clear_obstacle(self) -> None:
        with self._lock:
            self.drone.clear_obstacle()
            log_event(self.mission_id, "FAULT_CLEARED", "LOW", "Simulated obstacle cleared.")

    def inject_unauthorized_movement(self) -> None:
        with self._lock:
            self.drone.inject_unauthorized_movement()
            log_event(self.mission_id, "FAULT_INJECTED", "CRITICAL", "Simulated unauthorized movement / tampering injected.")

    def inject_multi_failure(self) -> None:
        with self._lock:
            self.drone.inject_multi_failure()
            log_event(self.mission_id, "FAULT_INJECTED", "CRITICAL", "Simulated multi-failure emergency injected (No GPS, No Comm, 18% Battery).")
