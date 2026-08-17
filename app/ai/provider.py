from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class AIExecutionRequest:
    task_id: str
    project_key: str
    user_request: str


@dataclass(frozen=True)
class AIExecutionResult:
    text: str
    response_id: str | None = None


class AIProviderError(RuntimeError):
    pass


class AIProvider(Protocol):
    def execute(self, request: AIExecutionRequest) -> AIExecutionResult:
        ...
