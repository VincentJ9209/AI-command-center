from fastapi import FastAPI

from app.api.line_webhook import router as line_webhook_router


app = FastAPI(title="AI-command-center")
app.include_router(line_webhook_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
