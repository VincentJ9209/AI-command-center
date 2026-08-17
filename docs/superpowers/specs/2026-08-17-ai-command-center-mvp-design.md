# AI-command-center MVP Design

**Date:** 2026-08-17  
**Status:** Approved design baseline

## Purpose

AI-command-center is a personal AI operations console and portfolio project. LINE is the mobile command and notification interface. The backend routes tasks to the correct project workflow, invokes OpenAI for reasoning/execution, persists task state and audit logs, and returns completion or approval notifications.

## MVP Goal

A user sends a natural-language task through LINE. The system validates the LINE webhook, creates a Task ID, identifies intent/project/task type, runs the task through OpenAI, stores the result/status, and replies to LINE with a concise completion or failure message.

## Architecture

LINE User → LINE Messaging API → FastAPI Webhook → Signature Verification → Command Router → Task Service → OpenAI Executor → PostgreSQL Task Store / Audit Log → Notification Service → LINE

Local development uses Docker Compose. Production deployment uses Google Cloud Run with Secret Manager, Cloud SQL PostgreSQL, and Cloud Logging.

## Core Rules

- Support `AI_SKILL_MARKET_INTELLIGENCE` and `GENERAL` routing initially.
- Task lifecycle: `RECEIVED → RUNNING → COMPLETED | FAILED | WAITING_APPROVAL`.
- PostgreSQL is the MVP database.
- `READ` and `ANALYZE` may execute automatically.
- `PUBLISH`, `DELETE`, and `FINANCIAL` require explicit approval.
- Secrets must never be committed to Git.
- Redis/Celery, dashboard, Gmail/Calendar, multi-agent orchestration, voice/image input, multi-user support, and direct control of an existing chatgpt.com conversation are outside MVP v0.1.

## MVP Acceptance Criteria

Given a LINE request such as `幫我整理今天 AI Skill 市場值得追蹤的方向`:

- webhook validates the LINE event;
- exactly one Task ID is created;
- `project_key` resolves to `AI_SKILL_MARKET_INTELLIGENCE`;
- task reaches `RUNNING` then `COMPLETED` or `FAILED`;
- result is persisted;
- LINE receives acknowledgement and final status;
- automated tests pass locally;
- service runs using Docker Compose;
- production deployment is Cloud Run compatible with externalized secrets.
