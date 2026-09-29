"""
Emergency Brain Decision Engine.
Part M: Holistic situational evaluation, rule resolution, priority arbitrament,
decision latching (Part O), and explainability generation (Part P).
Completely decoupled from simulator.
"""

from typing import Dict, Any, List, Optional
import time
from decision_engine.interfaces import DecisionResult, DecisionType, SeverityLevel, ImpactLevel
from decision_engine.detector import FailureDetector
from decision_engine.classifier import FailureClassifier
from decision_engine.risk_assessor import RiskAssessor
from decision_engine.rules import (
    RuleEvaluationResult,
    evaluate_r1_security,
    evaluate_r2_r3_critical_battery,
    evaluate_r4_obstacle,
    evaluate_r5_r6_gps_lost,
    evaluate_r7_restricted_zone,
    evaluate_r8_r9_r10_comm_loss,
    evaluate_r11_r12_low_battery,
    evaluate_r13_gps_degraded,
    evaluate_r14_nominal
)


class EmergencyBrain:
    """
    Central Autonomous Emergency Decision Engine.
    Executes the pipeline: MONITOR -> DETECT -> CLASSIFY -> ASSESS IMPACT -> DECIDE.
    Guarantees explainability, deterministic rule prioritization, and anti-flip-flop latching.
    """

    def __init__(
        self,
        detector: Optional[FailureDetector] = None,
        classifier: Optional[FailureClassifier] = None,
        risk_assessor: Optional[RiskAssessor] = None
    ):
        self.detector = detector or FailureDetector()
        self.classifier = classifier or FailureClassifier()
        self.risk_assessor = risk_assessor or RiskAssessor()

        # Decision Latching State (Part O)
        self.latched_decision: Optional[DecisionResult] = None
        self.latched_priority: int = 0
        self.preemption_log: List[Dict[str, Any]] = []

    def clear_latch(self) -> None:
        """Clears the active decision latch (e.g. on reset or when recovery is completed)."""
        self.latched_decision = None
        self.latched_priority = 0

    def evaluate(self, telemetry: Dict[str, Any]) -> DecisionResult:
        """
        Processes a telemetry frame through detection, classification, risk assessment,
        and rule arbitration to produce an explainable decision.
        """
        now = telemetry.get("timestamp") or time.time()

        # 1. DETECT
        detections = self.detector.detect_failures(telemetry)
        detection_types = {d.type for d in detections}

        # 2. CLASSIFY & IMPACT ASSESSMENT
        classified, overall_sev, overall_imp, compound_notes = self.classifier.evaluate(detections)

        # 3. ASSESS RISK
        risk_result = self.risk_assessor.assess_risk(telemetry, detections)

        # 4. RULE ARBITRATION (Evaluated strictly by priority hierarchy)
        # Hierarchy: SECURITY(100) -> ENERGY(90) -> COLLISION(80) -> NAVIGATION(70) ->
        #            LEGAL(60) -> COMMUNICATION(50) -> DEGRADATION(20) -> NOMINAL(0)
        rule_result: Optional[RuleEvaluationResult] = None

        if not detections:
            rule_result = evaluate_r14_nominal(telemetry)
        else:
            rule_candidates = [
                evaluate_r1_security(telemetry, detection_types, detections),
                evaluate_r2_r3_critical_battery(telemetry, detection_types),
                evaluate_r4_obstacle(telemetry, detection_types),
                evaluate_r5_r6_gps_lost(telemetry, detection_types),
                evaluate_r7_restricted_zone(telemetry, detection_types),
                evaluate_r8_r9_r10_comm_loss(telemetry, detection_types),
                evaluate_r11_r12_low_battery(telemetry, detection_types),
                evaluate_r13_gps_degraded(telemetry, detection_types)
            ]
            valid_candidates = [c for c in rule_candidates if c is not None]
            if valid_candidates:
                # Select the highest priority rule
                valid_candidates.sort(key=lambda r: r.priority, reverse=True)
                rule_result = valid_candidates[0]
            else:
                rule_result = evaluate_r14_nominal(telemetry)

        # 5. DECISION LATCHING (Part O: Anti-flip-flopping)
        # If a non-nominal recovery decision is currently latched:
        # A new decision can PRE-EMPT only if its priority is STRICTLY HIGHER!
        # If all failures cleared (nominal), latch is released.
        if not detections:
            self.clear_latch()
        elif self.latched_decision is not None and self.latched_priority > 0:
            if rule_result.priority > self.latched_priority:
                # Pre-empt latched decision
                preempt_note = (
                    f"Higher-priority emergency pre-emption: {rule_result.rule_id} (Priority {rule_result.priority}) "
                    f"pre-empted active {self.latched_decision.decision} (Priority {self.latched_priority})"
                )
                self.preemption_log.append({
                    "timestamp": now,
                    "previous_decision": self.latched_decision.decision,
                    "new_decision": rule_result.decision,
                    "reason": preempt_note
                })
                compound_notes.append(preempt_note)
                self.latched_priority = rule_result.priority
            else:
                # Retain latched decision to prevent flip-flopping
                return self.latched_decision

        # Combine all evidence
        evidence_list = list(rule_result.evidence)
        for note in compound_notes:
            evidence_list.append(note)

        # Build full explainable DecisionResult
        decision = DecisionResult(
            decision=rule_result.decision,
            severity=overall_sev,
            mission_impact=overall_imp,
            reason=rule_result.reason,
            evidence=evidence_list,
            rules_fired=[rule_result.rule_id],
            rejected_options=rule_result.rejected_options,
            alternatives_considered=rule_result.alternatives_considered,
            target_position=rule_result.target_position,
            selected_zone_id=rule_result.selected_zone_id,
            timestamp=now
        )

        # If this is an active emergency recovery decision, latch it
        if rule_result.priority > 0 and rule_result.decision != DecisionType.CONTINUE_MISSION.value:
            self.latched_decision = decision
            self.latched_priority = rule_result.priority

        return decision
