"""
Interfaces and data models for the Autonomous Drone Emergency Brain.
Pure data transfer objects and enums decoupled from the simulator.
"""

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import List, Dict, Any, Optional


class SystemState(str, Enum):
    READY = "READY"
    MISSION_ACTIVE = "MISSION_ACTIVE"
    FAILURE_DETECTED = "FAILURE_DETECTED"
    ASSESSING = "ASSESSING"
    DECISION_SELECTED = "DECISION_SELECTED"
    RECOVERY_EXECUTING = "RECOVERY_EXECUTING"
    VERIFYING = "VERIFYING"
    MISSION_RESUMED = "MISSION_RESUMED"
    MISSION_COMPLETED = "MISSION_COMPLETED"
    MISSION_ABORTED = "MISSION_ABORTED"
    EMERGENCY_RECOVERY = "EMERGENCY_RECOVERY"


class FlightMode(str, Enum):
    IDLE = "IDLE"
    MISSION = "MISSION"
    HOVER = "HOVER"
    RELOCATING = "RELOCATING"
    RETURNING = "RETURNING"
    ALTERNATE_ROUTE = "ALTERNATE_ROUTE"
    LANDING = "LANDING"
    LANDED = "LANDED"


class SeverityLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ImpactLevel(str, Enum):
    NONE = "NONE"
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ImpactDimension(str, Enum):
    NAVIGATION = "NAVIGATION"
    ENERGY = "ENERGY"
    COMMUNICATION = "COMMUNICATION"
    COLLISION = "COLLISION"
    LEGAL = "LEGAL"
    SECURITY = "SECURITY"
    MISSION = "MISSION"


class DecisionType(str, Enum):
    CONTINUE_MISSION = "CONTINUE_MISSION"
    HOVER = "HOVER"
    RELOCATE_AND_HOVER = "RELOCATE_AND_HOVER"
    RETURN_TO_HOME = "RETURN_TO_HOME"
    ALTERNATE_ROUTE = "ALTERNATE_ROUTE"
    EMERGENCY_LANDING = "EMERGENCY_LANDING"
    ABORT_MISSION = "ABORT_MISSION"
    SECURITY_ESCALATION = "SECURITY_ESCALATION"


class VerificationStatus(str, Enum):
    SUCCESS = "SUCCESS"
    PARTIAL_SUCCESS = "PARTIAL_SUCCESS"
    FAILED = "FAILED"


class ZoneType(str, Enum):
    ALLOWED = "ALLOWED"
    RESTRICTED = "RESTRICTED"
    PRIVATE = "PRIVATE"
    HOVER_ZONE = "HOVER_ZONE"


@dataclass
class TelemetryData:
    battery: float = 100.0
    battery_consumption_rate: float = 0.4
    gps_status: str = "CONNECTED"             # "CONNECTED", "DEGRADED", "LOST"
    gps_accuracy: float = 4.0                 # meters
    satellites: int = 10
    gps_confidence: float = 1.0               # 0.0 - 1.0
    communication: str = "CONNECTED"          # "CONNECTED", "LOST"
    heartbeat: bool = True
    comm_loss_duration: float = 0.0           # seconds
    position: List[float] = field(default_factory=lambda: [10.0, 80.0])
    last_known_position: List[float] = field(default_factory=lambda: [10.0, 80.0])
    home: List[float] = field(default_factory=lambda: [10.0, 80.0])
    destination: List[float] = field(default_factory=lambda: [90.0, 20.0])
    distance_to_home: float = 0.0
    distance_to_destination: float = 100.0
    obstacle_detected: bool = False
    mission_status: str = "READY"
    flight_mode: str = "MISSION"
    altitude: float = 10.0
    speed: float = 0.0
    zone_type: str = "ALLOWED"
    hover_position: Optional[List[float]] = None
    hover_duration: float = 0.0
    unauthorized_movement: bool = False
    theft_detected: bool = False
    active_command_id: Optional[str] = None
    timestamp: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TelemetryData":
        # Filter keys to match dataclass fields
        valid_keys = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in valid_keys}
        return cls(**filtered)


@dataclass
class DetectionResult:
    type: str
    evidence: List[str]
    timestamp: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ClassificationResult:
    failure_type: str
    severity: str
    mission_impact: str
    evidence: List[str]
    priority: int

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RiskFactor:
    factor: str
    points: int
    reason: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RiskAssessmentResult:
    total_score: int
    overall_risk: str
    factors: List[RiskFactor] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_score": self.total_score,
            "overall_risk": self.overall_risk,
            "factors": [f.to_dict() for f in self.factors]
        }


@dataclass
class DecisionResult:
    decision: str
    severity: str
    mission_impact: str
    reason: str
    evidence: List[str]
    rules_fired: List[str]
    rejected_options: List[Dict[str, str]]
    alternatives_considered: List[str]
    target_position: Optional[List[float]] = None
    selected_zone_id: Optional[str] = None
    timestamp: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RecoveryCommand:
    command_id: str
    command_type: str
    target_position: Optional[List[float]] = None
    target_altitude: Optional[float] = None
    target_speed: Optional[float] = None
    parameters: Dict[str, Any] = field(default_factory=dict)
    latched: bool = False
    timestamp: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class VerificationResult:
    status: str                               # SUCCESS, PARTIAL_SUCCESS, FAILED
    checks: Dict[str, str] = field(default_factory=dict) # e.g. {"target_reached": "PASS", "position_legal": "PASS"}
    summary: str = ""
    timestamp: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
