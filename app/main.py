from fastapi import FastAPI

app = FastAPI(title="AI-command-center")

@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
