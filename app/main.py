from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI, HTTPException
from sqlalchemy import text

from app.api.line_webhook import router as line_webhook_router
from app.bootstrap.runtime import Runtime, configure_runtime
from app.config.settings import Settings
from app.logging_config import configure_logging


logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = Settings.from_env()

    configure_logging(settings.log_level)

    runtime = configure_runtime(settings)

    app.state.runtime = runtime

    logger.info(
        "AI-command-center runtime configured"
    )

    try:
        yield
    finally:
        runtime.close()


app = FastAPI(
    title="AI-command-center",
    lifespan=lifespan,
)

app.include_router(line_webhook_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
    }


@app.get("/ready")
def ready() -> dict[str, str]:
    runtime: Runtime | None = getattr(
        app.state,
        "runtime",
        None,
    )

    if runtime is None:
        raise HTTPException(
            status_code=503,
            detail="Runtime not configured",
        )

    session = runtime.session_factory()

    try:
        session.execute(
            text("SELECT 1")
        )
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="Database unavailable",
        ) from exc
    finally:
        session.close()

    return {
        "status": "ready",
    }