# AI-command-center

A LINE-based personal AI operations console and portfolio project.

## Current MVP progress

- FastAPI health endpoint
- LINE webhook HMAC-SHA256 signature verification
- LINE text-event parser
- AI Skill Market Intelligence routing
- Approval policy for high-risk actions
- SQLAlchemy task persistence and lifecycle
- OpenAI Responses API execution
- LINE ACK / DONE / FAILED / ACTION_REQUIRED notifications
- End-to-end webhook orchestration
- Environment-based production configuration
- PostgreSQL runtime wiring
- Docker / Docker Compose readiness

## Local development

Create `.env` from `.env.example`, then:

```bash
python -m pip install -e ".[dev]"
pytest -q
```

## Docker

```bash
docker compose up --build
```

Service endpoints:

- `GET /health`
- `GET /ready`
- `POST /webhooks/line`

## Next milestone

Move long-running AI execution out of the webhook request path so LINE webhook responses return quickly and task execution continues asynchronously.
