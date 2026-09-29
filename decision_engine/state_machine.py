"""
State Machine for Autonomous Drone Emergency Brain.
Enforces strict valid transitions between system states, protects terminal states,
and logs state transition history.
"""

from typing import List, Dict, Any, Optional
import time
from decision_engine.interfaces import SystemState


class InvalidStateTransitionError(Exception):
    """Raised when an illegal state transition is attempted."""
    pass


class TerminalStateError(Exception):
    """Raised when attempting to transition out of a terminal state without reset."""
    pass


class EmergencyStateMachine:
    """
    Deterministic state machine for the emergency decision and recovery pipeline.
    Terminal states: MISSION_COMPLETED, MISSION_ABORTED.
    """

    ALLOWED_TRANSITIONS = {
        SystemState.READY: {
            SystemState.MISSION_ACTIVE
        },
        SystemState.MISSION_ACTIVE: {
            SystemState.FAILURE_DETECTED,
            SystemState.MISSION_COMPLETED,
            SystemState.MISSION_ABORTED,
        },
        SystemState.FAILURE_DETECTED: {
            SystemState.ASSESSING,
            SystemState.EMERGENCY_RECOVERY,
            SystemState.MISSION_ABORTED,
        },
        SystemState.ASSESSING: {
            SystemState.DECISION_SELECTED,
            SystemState.EMERGENCY_RECOVERY,
            SystemState.MISSION_ABORTED,
        },
        SystemState.DECISION_SELECTED: {
            SystemState.RECOVERY_EXECUTING,
            SystemState.MISSION_RESUMED,
            SystemState.EMERGENCY_RECOVERY,
            SystemState.MISSION_ABORTED,
        },
        SystemState.RECOVERY_EXECUTING: {
            SystemState.VERIFYING,
            SystemState.EMERGENCY_RECOVERY,
            SystemState.MISSION_ABORTED,
        },
        SystemState.VERIFYING: {
            SystemState.MISSION_RESUMED,
            SystemState.DECISION_SELECTED,
            SystemState.MISSION_COMPLETED,
            SystemState.MISSION_ABORTED,
            SystemState.EMERGENCY_RECOVERY,
        },
        SystemState.MISSION_RESUMED: {
            SystemState.MISSION_ACTIVE,
            SystemState.FAILURE_DETECTED,
            SystemState.MISSION_COMPLETED,
            SystemState.MISSION_ABORTED,
        },
        SystemState.EMERGENCY_RECOVERY: {
            SystemState.RECOVERY_EXECUTING,
            SystemState.VERIFYING,
            SystemState.MISSION_ABORTED,
        },
        # Terminal states
        SystemState.MISSION_COMPLETED: set(),
        SystemState.MISSION_ABORTED: set(),
    }

    def __init__(self, initial_state: SystemState = SystemState.READY):
        self._current_state: SystemState = initial_state
        self._history: List[Dict[str, Any]] = [
            {
                "from_state": None,
                "to_state": initial_state.value,
                "reason": "Initial state",
                "timestamp": time.time()
            }
        ]

    @property
    def current_state(self) -> SystemState:
        return self._current_state

    @property
    def is_terminal(self) -> bool:
        return self._current_state in (SystemState.MISSION_COMPLETED, SystemState.MISSION_ABORTED)

    @property
    def history(self) -> List[Dict[str, Any]]:
        return list(self._history)

    def transition_to(self, new_state: SystemState, reason: str = "") -> None:
        """
        Transitions to new_state if valid. Raises InvalidStateTransitionError or TerminalStateError otherwise.
        """
        if self.is_terminal:
            raise TerminalStateError(
                f"Cannot transition from terminal state '{self._current_state.value}' to '{new_state.value}'. "
                f"System must be reset first."
            )

        allowed = self.ALLOWED_TRANSITIONS.get(self._current_state, set())
        if new_state not in allowed:
            raise InvalidStateTransitionError(
                f"Invalid state transition: '{self._current_state.value}' -> '{new_state.value}'. "
                f"Allowed destinations: {[s.value for s in allowed]}"
            )

        prev = self._current_state
        self._current_state = new_state
        self._history.append({
            "from_state": prev.value,
            "to_state": new_state.value,
            "reason": reason,
            "timestamp": time.time()
        })

    def reset(self) -> None:
        """Resets the state machine back to READY."""
        prev = self._current_state
        self._current_state = SystemState.READY
        self._history.append({
            "from_state": prev.value,
            "to_state": SystemState.READY.value,
            "reason": "System Reset",
            "timestamp": time.time()
        })
