# AI-command-center MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement task-by-task.

**Goal:** Build an MVP LINE-based personal AI command center that validates LINE webhooks, routes tasks, persists lifecycle state, executes low-risk AI tasks, and sends status notifications.

**Architecture:** FastAPI handles transport concerns. LINE, routing, task lifecycle, provider execution, persistence, and notifications are isolated behind small modules. PostgreSQL is used for durable state. External providers are mockable in tests.

**Tech Stack:** Python 3.12+, FastAPI, pytest, PostgreSQL, SQLAlchemy, Alembic, OpenAI Responses API, LINE Messaging API, Docker Compose, Google Cloud Run.

## Global Constraints

- Repository name: `AI-command-center`.
- Incremental commits are required.
- TDD is used for production behavior.
- Secrets are never committed.
- `PUBLISH`, `DELETE`, and `FINANCIAL` require approval.
- Redis/Celery is excluded from v0.1.

---

### Task 1: Application bootstrap and health endpoint
- Add FastAPI app.
- Add `GET /health`.
- Verify with pytest.

### Task 2: LINE webhook security and text parser
- Verify `X-Line-Signature` with HMAC-SHA256.
- Parse supported LINE text-message events.
- Ignore unsupported event types safely.

### Task 3: Command Router and Approval Policy
- Route AI Skill requests to `AI_SKILL_MARKET_INTELLIGENCE`.
- Use `GENERAL` fallback.
- Require approval for `PUBLISH`, `DELETE`, and `FINANCIAL`.

### Task 4: Persistence and task lifecycle
- Add `tasks`, `task_events`, and `approvals`.
- Enforce allowed status transitions.
- Add message-id idempotency.

### Task 5: OpenAI executor abstraction
- Add provider interface.
- Add OpenAI Responses API adapter.
- Make provider failures transition tasks to `FAILED`.

### Task 6: Notification service
- Add ACK, DONE, FAILED, ACTION_REQUIRED formatting.
- Add LINE reply/push adapter.

### Task 7: Webhook orchestration integration
- Implement receive → verify → parse → create → route → execute → persist → notify.
- Mock external providers in integration tests.

### Task 8: Docker and production readiness
- Add Dockerfile and Docker Compose.
- Add PostgreSQL service.
- Add environment example.
- Document Cloud Run / Cloud SQL / Secret Manager deployment.
