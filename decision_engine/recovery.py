"""
Recovery Command Generator and Dispatcher.
Part 5 (Second Absolute Rule): Recovery does NOT make decisions.
Part Q: Executes the already-selected command from the Decision Engine.
Decoupled from simulator: does not import simulator classes.
"""

import uuid
import time
from typing import Dict, Any, Optional, List
from decision_engine.interfaces import DecisionResult, RecoveryCommand, DecisionType


class RecoveryExecutor:
    """
    Translates DecisionResult into actionable RecoveryCommands and dispatches them
    to the drone execution interface without any decision-making logic.
    """

    def __init__(self):
        self.active_command: Optional[RecoveryCommand] = None
        self.command_history: List[RecoveryCommand] = []

    def create_command(self, decision: DecisionResult) -> RecoveryCommand:
        """
        Pure command packaging: maps decision type and targets into RecoveryCommand.
        Contains ZERO severity calculations, risk evaluations, or zone selection.
        """
        cmd_id = f"CMD-{uuid.uuid4().hex[:8].upper()}"
        now = decision.timestamp or time.time()

        cmd = RecoveryCommand(
            command_id=cmd_id,
            command_type=decision.decision,
            target_position=decision.target_position,
            parameters={
                "selected_zone_id": decision.selected_zone_id,
                "reason": decision.reason,
                "rules_fired": decision.rules_fired
            },
            latched=True,
            timestamp=now
        )
        self.active_command = cmd
        self.command_history.append(cmd)
        return cmd

    def dispatch_to_drone(self, command: RecoveryCommand, drone: Any) -> None:
        """
        Executes the command on the drone interface.
        Directly delegates execution according to command_type.
        """
        ctype = command.command_type

        if ctype == DecisionType.HOVER.value:
            drone.command_hover(command.command_id)
        elif ctype == DecisionType.RELOCATE_AND_HOVER.value:
            target = command.target_position or drone.home
            drone.command_relocate(target, command.command_id)
        elif ctype == DecisionType.RETURN_TO_HOME.value:
            drone.command_return_to_home(command.command_id)
        elif ctype == DecisionType.ALTERNATE_ROUTE.value:
            # Check for alternate waypoints in parameters
            waypoints = command.parameters.get("alternate_waypoints")
            if not waypoints:
                waypoints = [command.target_position] if command.target_position else []
            drone.command_alternate_route(waypoints, command.command_id)
        elif ctype == DecisionType.EMERGENCY_LANDING.value:
            drone.command_emergency_landing(command.command_id)
        elif ctype == DecisionType.SECURITY_ESCALATION.value:
            drone.command_hover(command.command_id)
        elif ctype == DecisionType.CONTINUE_MISSION.value:
            drone.command_resume_mission()
