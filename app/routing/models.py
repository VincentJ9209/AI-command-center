from dataclasses import dataclass
from enum import StrEnum


class Action(StrEnum):
    READ = "READ"
    ANALYZE = "ANALYZE"
    WRITE = "WRITE"
    PUBLISH = "PUBLISH"
    DELETE = "DELETE"
    FINANCIAL = "FINANCIAL"


class RiskLevel(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


@dataclass(frozen=True)
class TaskIntent:
    project_key: str
    task_type: str
    action: Action
    risk_level: RiskLevel
    requires_approval: bool
    user_request: str
