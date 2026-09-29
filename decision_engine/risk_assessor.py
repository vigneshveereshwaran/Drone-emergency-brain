"""
Risk Assessment Engine for Autonomous Drone Emergency Brain.
Part L: Calculates transparent risk scores, dimensional breakdowns, and maps to overall risk band.
Completely decoupled from simulator.
"""

from typing import List, Dict, Any, Optional
import config
from decision_engine.interfaces import RiskFactor, RiskAssessmentResult, DetectionResult


class RiskAssessor:
    """
    Transparently evaluates telemetry and detected failures, assigning explicit risk points
    and categorical risk bands.
    """

    def __init__(self):
        self.risk_points_config = dict(config.RISK_POINTS)
        self.risk_bands = list(config.RISK_BANDS)

    def assess_risk(
        self,
        telemetry: Dict[str, Any],
        detections: List[DetectionResult]
    ) -> RiskAssessmentResult:
        """
        Calculates total risk score and produces dimensional breakdown.
        """
        factors: List[RiskFactor] = []
        detection_types = {d.type for d in detections}

        # 1. Battery Risk
        if "CRITICAL_BATTERY" in detection_types:
            pts = self.risk_points_config.get("CRITICAL_BATTERY", 3)
            factors.append(RiskFactor(
                factor="Battery Risk (Critical)",
                points=pts,
                reason=f"Battery level ({telemetry.get('battery', 0):.1f}%) is critical / insufficient for RTH"
            ))
        elif "LOW_BATTERY" in detection_types:
            pts = self.risk_points_config.get("LOW_BATTERY", 1)
            factors.append(RiskFactor(
                factor="Battery Risk (Low)",
                points=pts,
                reason=f"Battery level ({telemetry.get('battery', 0):.1f}%) is below 30% warning threshold"
            ))

        # 2. Navigation Risk
        if "GPS_FAILURE" in detection_types:
            pts = self.risk_points_config.get("GPS_LOST", 3)
            factors.append(RiskFactor(
                factor="Navigation Risk (GPS Lost)",
                points=pts,
                reason="Complete loss of GPS positioning and satellite lock"
            ))
        elif "GPS_DEGRADED" in detection_types:
            pts = self.risk_points_config.get("GPS_DEGRADED", 1)
            factors.append(RiskFactor(
                factor="Navigation Risk (Degraded)",
                points=pts,
                reason=f"GPS degraded: accuracy={telemetry.get('gps_accuracy', 0)}m, satellites={telemetry.get('satellites', 0)}"
            ))

        # 3. Communication Risk
        if "COMMUNICATION_FAILURE" in detection_types:
            pts = self.risk_points_config.get("COMMUNICATION_LOST", 2)
            factors.append(RiskFactor(
                factor="Communication Risk",
                points=pts,
                reason="Heartbeat uplink to Ground Control Station is severed"
            ))
            comm_duration = float(telemetry.get("comm_loss_duration", 0.0))
            if comm_duration > config.COMM_WARNING_THRESHOLD:
                add_pts = self.risk_points_config.get("LONG_COMM_LOSS", 1)
                factors.append(RiskFactor(
                    factor="Communication Risk (Prolonged)",
                    points=add_pts,
                    reason=f"Communication loss duration ({comm_duration:.1f}s) exceeded {config.COMM_WARNING_THRESHOLD}s threshold"
                ))

        # 4. Obstacle / Collision Risk
        if "OBSTACLE_DETECTED" in detection_types:
            pts = self.risk_points_config.get("OBSTACLE", 2)
            factors.append(RiskFactor(
                factor="Collision Risk",
                points=pts,
                reason="Unscheduled obstacle detected directly along active flight corridor"
            ))

        # 5. Legal / Airspace Risk
        if "RESTRICTED_ZONE" in detection_types:
            pts = self.risk_points_config.get("RESTRICTED_ZONE", 3)
            factors.append(RiskFactor(
                factor="Legal Risk (Restricted Airspace)",
                points=pts,
                reason="Drone position or last known position is within restricted/private airspace"
            ))

        # 6. Security Risk
        if "UNAUTHORIZED_MOVEMENT" in detection_types or "THEFT_DETECTED" in detection_types:
            pts = self.risk_points_config.get("UNAUTHORIZED_MOVEMENT", 3)
            factors.append(RiskFactor(
                factor="Security Risk",
                points=pts,
                reason="External tampering or physical movement outside hover station without flight authorization"
            ))

        total_score = sum(f.points for f in factors)
        overall_risk = self._map_score_to_band(total_score)

        return RiskAssessmentResult(
            total_score=total_score,
            overall_risk=overall_risk,
            factors=factors
        )

    def _map_score_to_band(self, score: int) -> str:
        """Maps an integer risk score to LOW, MEDIUM, HIGH, or CRITICAL."""
        for min_score, max_score, label in self.risk_bands:
            if min_score <= score <= max_score:
                return label
        return "CRITICAL"
