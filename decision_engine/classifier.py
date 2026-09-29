"""
Failure Classification and Multi-Failure Analysis Module.
Part K: Determines severity, mission impact, dimensions, priority, and multi-failure escalation.
Completely decoupled from simulator.
"""

from typing import List, Dict, Any, Tuple
from decision_engine.interfaces import (
    DetectionResult,
    ClassificationResult,
    SeverityLevel,
    ImpactLevel,
    ImpactDimension
)


# Ordered severity ladder for escalation
SEVERITY_ORDER = [
    SeverityLevel.LOW.value,
    SeverityLevel.MEDIUM.value,
    SeverityLevel.HIGH.value,
    SeverityLevel.CRITICAL.value
]

IMPACT_ORDER = [
    ImpactLevel.NONE.value,
    ImpactLevel.LOW.value,
    ImpactLevel.MODERATE.value,
    ImpactLevel.HIGH.value,
    ImpactLevel.CRITICAL.value
]


def elevate_severity(current: str, levels: int = 1) -> str:
    """Escalates severity by N levels, capped at CRITICAL."""
    try:
        idx = SEVERITY_ORDER.index(current)
        new_idx = min(len(SEVERITY_ORDER) - 1, idx + levels)
        return SEVERITY_ORDER[new_idx]
    except ValueError:
        return SeverityLevel.CRITICAL.value


def elevate_impact(current: str, levels: int = 1) -> str:
    """Escalates impact by N levels, capped at CRITICAL."""
    try:
        idx = IMPACT_ORDER.index(current)
        new_idx = min(len(IMPACT_ORDER) - 1, idx + levels)
        return IMPACT_ORDER[new_idx]
    except ValueError:
        return ImpactLevel.CRITICAL.value


class FailureClassifier:
    """
    Classifies individual failure detections and performs multi-failure synthesis.
    """

    # Base classifications: (severity, impact, primary_dimension, priority)
    BASE_MAP = {
        "UNAUTHORIZED_MOVEMENT": (SeverityLevel.CRITICAL.value, ImpactLevel.CRITICAL.value, ImpactDimension.SECURITY.value, 100),
        "THEFT_DETECTED": (SeverityLevel.CRITICAL.value, ImpactLevel.CRITICAL.value, ImpactDimension.SECURITY.value, 95),
        "CRITICAL_BATTERY": (SeverityLevel.CRITICAL.value, ImpactLevel.HIGH.value, ImpactDimension.ENERGY.value, 90),
        "OBSTACLE_DETECTED": (SeverityLevel.HIGH.value, ImpactLevel.MODERATE.value, ImpactDimension.COLLISION.value, 80),
        "GPS_FAILURE": (SeverityLevel.HIGH.value, ImpactLevel.HIGH.value, ImpactDimension.NAVIGATION.value, 75),
        "RESTRICTED_ZONE": (SeverityLevel.HIGH.value, ImpactLevel.HIGH.value, ImpactDimension.LEGAL.value, 70),
        "COMMUNICATION_FAILURE": (SeverityLevel.MEDIUM.value, ImpactLevel.MODERATE.value, ImpactDimension.COMMUNICATION.value, 50),
        "LOW_BATTERY": (SeverityLevel.LOW.value, ImpactLevel.LOW.value, ImpactDimension.ENERGY.value, 40),
        "GPS_DEGRADED": (SeverityLevel.LOW.value, ImpactLevel.LOW.value, ImpactDimension.NAVIGATION.value, 30),
    }

    def __init__(self):
        pass

    def classify_detection(self, detection: DetectionResult) -> ClassificationResult:
        """Classifies a single detection into severity, impact, evidence, and priority."""
        ftype = detection.type
        sev, imp, dim, prio = self.BASE_MAP.get(
            ftype,
            (SeverityLevel.MEDIUM.value, ImpactLevel.MODERATE.value, ImpactDimension.MISSION.value, 10)
        )

        return ClassificationResult(
            failure_type=ftype,
            severity=sev,
            mission_impact=imp,
            evidence=list(detection.evidence),
            priority=prio
        )

    def evaluate(self, detections: List[DetectionResult]) -> Tuple[List[ClassificationResult], str, str, List[str]]:
        """
        Classifies all detections and applies multi-failure compounding rules.
        Returns:
            (individual_classifications, overall_severity, overall_impact, compounding_notes)
        """
        if not detections:
            return ([], SeverityLevel.LOW.value, ImpactLevel.NONE.value, [])

        classified = [self.classify_detection(d) for d in detections]
        # Sort by priority descending
        classified.sort(key=lambda c: c.priority, reverse=True)

        types_present = {c.failure_type for c in classified}
        compounding_notes = []

        # Find initial highest severity & impact among single failures
        max_sev_idx = max(SEVERITY_ORDER.index(c.severity) for c in classified)
        overall_sev = SEVERITY_ORDER[max_sev_idx]

        max_imp_idx = max(IMPACT_ORDER.index(c.mission_impact) for c in classified)
        overall_imp = IMPACT_ORDER[max_imp_idx]

        # -------------------------------------------------------------
        # MULTI-FAILURE RULES (Part K)
        # -------------------------------------------------------------
        # Rule: If two or more simultaneous failures exist, increase overall severity by one level
        if len(classified) >= 2:
            escalated_sev = elevate_severity(overall_sev, 1)
            compounding_notes.append(
                f"Multi-failure escalation: {len(classified)} concurrent failures detected; severity elevated from {overall_sev} to {escalated_sev}"
            )
            overall_sev = escalated_sev

        # Rule: CRITICAL BATTERY + NAVIGATION FAILURE -> CRITICAL
        if "CRITICAL_BATTERY" in types_present and ("GPS_FAILURE" in types_present or "GPS_DEGRADED" in types_present):
            overall_sev = SeverityLevel.CRITICAL.value
            overall_imp = ImpactLevel.CRITICAL.value
            compounding_notes.append("Multi-failure compound rule fired: Critical battery combined with degraded/lost navigation")

        # Rule: CRITICAL BATTERY + COMMUNICATION FAILURE -> CRITICAL
        if "CRITICAL_BATTERY" in types_present and "COMMUNICATION_FAILURE" in types_present:
            overall_sev = SeverityLevel.CRITICAL.value
            overall_imp = ImpactLevel.CRITICAL.value
            compounding_notes.append("Multi-failure compound rule fired: Critical battery combined with loss of communication link")

        # Rule: GPS LOSS + RESTRICTED ZONE + LOW BATTERY -> CRITICAL
        if "GPS_FAILURE" in types_present and "RESTRICTED_ZONE" in types_present and ("LOW_BATTERY" in types_present or "CRITICAL_BATTERY" in types_present):
            overall_sev = SeverityLevel.CRITICAL.value
            overall_imp = ImpactLevel.CRITICAL.value
            compounding_notes.append("Multi-failure compound rule fired: GPS loss inside restricted airspace with depleted battery")

        # Rule: GPS LOSS + LOW BATTERY != GPS LOSS alone
        if "GPS_FAILURE" in types_present and "LOW_BATTERY" in types_present:
            if SEVERITY_ORDER.index(overall_sev) < SEVERITY_ORDER.index(SeverityLevel.HIGH.value):
                overall_sev = SeverityLevel.HIGH.value
            overall_imp = elevate_impact(overall_imp, 1)
            compounding_notes.append("Multi-failure compound rule fired: GPS loss with reduced battery reserve (cannot loiter indefinitely)")

        # Flagship Scenario 5: GPS LOSS + COMM LOSS + BATTERY 18% (Critical Battery)
        if "GPS_FAILURE" in types_present and "COMMUNICATION_FAILURE" in types_present and "CRITICAL_BATTERY" in types_present:
            overall_sev = SeverityLevel.CRITICAL.value
            overall_imp = ImpactLevel.CRITICAL.value
            compounding_notes.append("Triple emergency failure: Total isolation (No GPS + No Comm) with critically low battery")

        return classified, overall_sev, overall_imp, compounding_notes
