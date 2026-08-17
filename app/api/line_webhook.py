from __future__ import annotations

import json

from fastapi import APIRouter, Header, HTTPException, Request

from app.api.dependencies import get_line_webhook_dependencies
from app.line.security import InvalidLineSignature
from app.webhooks.line import LineWebhookOrchestrator


router = APIRouter()


@router.post("/webhooks/line")
async def line_webhook(
    request: Request,
    x_line_signature: str = Header(default=""),
) -> dict[str, int]:
    body = await request.body()

    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=400, detail="Invalid JSON payload") from exc

    dependencies = get_line_webhook_dependencies()
    session = dependencies.session_factory()

    try:
        orchestrator = LineWebhookOrchestrator(
            session=session,
            channel_secret=dependencies.channel_secret,
            provider=dependencies.provider,
            notification_service=dependencies.notification_service,
        )
        result = orchestrator.handle(
            body=body,
            signature=x_line_signature,
            payload=payload,
        )
    except InvalidLineSignature as exc:
        raise HTTPException(status_code=401, detail="Invalid LINE signature") from exc
    finally:
        session.close()

    return {
        "processed_events": result.processed_events,
        "created_tasks": result.created_tasks,
        "duplicate_events": result.duplicate_events,
    }
