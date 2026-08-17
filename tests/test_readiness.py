from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.main import app


class FakeSession:
    def __init__(self, should_fail: bool = False) -> None:
        self.should_fail = should_fail
        self.closed = False

    def execute(self, statement):
        if self.should_fail:
            raise RuntimeError("db down")
        return None

    def close(self):
        self.closed = True


def test_ready_returns_503_when_runtime_missing() -> None:
    app.state.runtime = None

    response = TestClient(app).get("/ready")

    assert response.status_code == 503


def test_ready_checks_database() -> None:
    session = FakeSession()
    app.state.runtime = SimpleNamespace(
        session_factory=lambda: session
    )

    response = TestClient(app).get("/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}
    assert session.closed is True


def test_ready_returns_503_when_database_fails() -> None:
    session = FakeSession(should_fail=True)
    app.state.runtime = SimpleNamespace(
        session_factory=lambda: session
    )

    response = TestClient(app).get("/ready")

    assert response.status_code == 503
    assert session.closed is True
