from typing import Any

from app.ai.provider import (
    AIExecutionRequest,
    AIExecutionResult,
    AIProviderError,
)


class OpenAIResponsesProvider:
    def __init__(
        self,
        *,
        model: str = "gpt-5.6",
        client: Any | None = None,
    ) -> None:
        if client is None:
            from openai import OpenAI

            client = OpenAI()

        self.client = client
        self.model = model

    def execute(self, request: AIExecutionRequest) -> AIExecutionResult:
        prompt = (
            "You are executing a task for AI-command-center.\n"
            f"Project: {request.project_key}\n"
            f"Task ID: {request.task_id}\n"
            f"User request: {request.user_request}\n"
            "Return a concise, useful result suitable for persistence and "
            "a mobile notification summary."
        )

        try:
            response = self.client.responses.create(
                model=self.model,
                input=prompt,
                store=False,
            )
        except Exception as exc:
            raise AIProviderError("OpenAI Responses API request failed") from exc

        output_text = getattr(response, "output_text", None)
        if not output_text:
            raise AIProviderError("OpenAI Responses API returned no output text")

        return AIExecutionResult(
            text=output_text,
            response_id=getattr(response, "id", None),
        )
