"""
Tests for decision_engine/state_machine.py
Validates Part S requirements:
- Deterministic state transitions
- Invalid transitions are rejected
- Terminal states (MISSION_COMPLETED, MISSION_ABORTED) reject transitions until reset
"""

import pytest
from decision_engine.interfaces import SystemState
from decision_engine.state_machine import (
    EmergencyStateMachine,
    InvalidStateTransitionError,
    TerminalStateError
)


def test_initial_state():
    sm = EmergencyStateMachine()
    assert sm.current_state == SystemState.READY
    assert not sm.is_terminal
    assert len(sm.history) == 1


def test_valid_mission_lifecycle():
    sm = EmergencyStateMachine()

    # READY -> MISSION_ACTIVE
    sm.transition_to(SystemState.MISSION_ACTIVE, "Mission initiated")
    assert sm.current_state == SystemState.MISSION_ACTIVE

    # MISSION_ACTIVE -> FAILURE_DETECTED
    sm.transition_to(SystemState.FAILURE_DETECTED, "GPS lost")
    assert sm.current_state == SystemState.FAILURE_DETECTED

    # FAILURE_DETECTED -> ASSESSING
    sm.transition_to(SystemState.ASSESSING, "Evaluating severity & risk")
    assert sm.current_state == SystemState.ASSESSING

    # ASSESSING -> DECISION_SELECTED
    sm.transition_to(SystemState.DECISION_SELECTED, "Emergency Brain chose RELOCATE_AND_HOVER")
    assert sm.current_state == SystemState.DECISION_SELECTED

    # DECISION_SELECTED -> RECOVERY_EXECUTING
    sm.transition_to(SystemState.RECOVERY_EXECUTING, "Executing relocation to HZ1")
    assert sm.current_state == SystemState.RECOVERY_EXECUTING

    # RECOVERY_EXECUTING -> VERIFYING
    sm.transition_to(SystemState.VERIFYING, "Verifying hover conditions")
    assert sm.current_state == SystemState.VERIFYING

    # VERIFYING -> MISSION_RESUMED
    sm.transition_to(SystemState.MISSION_RESUMED, "Recovery verified, GPS signal restored")
    assert sm.current_state == SystemState.MISSION_RESUMED

    # MISSION_RESUMED -> MISSION_COMPLETED
    sm.transition_to(SystemState.MISSION_COMPLETED, "Destination reached safely")
    assert sm.current_state == SystemState.MISSION_COMPLETED
    assert sm.is_terminal is True


def test_invalid_transitions():
    sm = EmergencyStateMachine()
    # Cannot jump from READY directly to DECISION_SELECTED
    with pytest.raises(InvalidStateTransitionError):
        sm.transition_to(SystemState.DECISION_SELECTED)

    # Move to MISSION_ACTIVE
    sm.transition_to(SystemState.MISSION_ACTIVE)

    # Cannot jump from MISSION_ACTIVE to RECOVERY_EXECUTING without failure/assessment
    with pytest.raises(InvalidStateTransitionError):
        sm.transition_to(SystemState.RECOVERY_EXECUTING)


def test_terminal_state_lock_and_reset():
    sm = EmergencyStateMachine()
    sm.transition_to(SystemState.MISSION_ACTIVE)
    sm.transition_to(SystemState.MISSION_ABORTED, "Critical failure abort")
    assert sm.is_terminal is True

    # Attempting any transition while in terminal state must raise TerminalStateError
    with pytest.raises(TerminalStateError):
        sm.transition_to(SystemState.MISSION_ACTIVE)

    # Resetting restores READY state
    sm.reset()
    assert sm.current_state == SystemState.READY
    assert sm.is_terminal is False

    # After reset, can transition normally again
    sm.transition_to(SystemState.MISSION_ACTIVE)
    assert sm.current_state == SystemState.MISSION_ACTIVE
