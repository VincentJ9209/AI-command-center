# AI-command-center

A LINE-based personal AI operations console and portfolio project.

## Current MVP progress

- FastAPI health endpoint
- LINE webhook HMAC-SHA256 signature verification
- LINE text-event parser
- AI Skill Market Intelligence routing
- Approval policy for high-risk actions
- Pytest test suite

## Local test

```bash
python -m pip install -e ".[dev]"
pytest -q
```

## Next milestone

Task persistence and lifecycle management with PostgreSQL.
