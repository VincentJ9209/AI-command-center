from types import SimpleNamespace

from app.bootstrap import runtime as runtime_module


class RecordingDispatcher:
    def __init__(self) -> None:
        self.shutdown_calls: list[bool] = []

    def shutdown(
        self,
        *,
        wait: bool = True,
    ) -> None:
        self.shutdown_calls.append(wait)

class RecordingLineClient:
    def __init__(self, events: list[str]) -> None:
        self.events = events

    def close(self) -> None:
        self.events.append("line_client")


class RecordingEngine:
    def __init__(self, events: list[str]) -> None:
        self.events = events

    def dispose(self) -> None:
        self.events.append("engine")


class OrderedRecordingDispatcher:
    def __init__(self, events: list[str]) -> None:
        self.events = events

    def shutdown(
        self,
        *,
        wait: bool = True,
    ) -> None:
        self.events.append("dispatcher")


def test_configure_runtime_wires_background_dispatcher(
    monkeypatch,
) -> None:
    fake_engine = object()
    fake_factory = object()
    fake_worker = object()
    fake_dispatcher = RecordingDispatcher()

    captured = {}

    monkeypatch.setattr(
        runtime_module,
        "build_engine",
        lambda *args, **kwargs: fake_engine,
    )

    monkeypatch.setattr(
        runtime_module.Base.metadata,
        "create_all",
        lambda engine: captured.setdefault(
            "engine",
            engine,
        ),
    )

    monkeypatch.setattr(
        runtime_module,
        "build_session_factory",
        lambda engine: fake_factory,
    )

    fake_provider = SimpleNamespace(
        model="gpt-5.6",
    )

    monkeypatch.setattr(
        runtime_module,
        "OpenAIResponsesProvider",
        lambda model: fake_provider,
    )

    fake_line_client = SimpleNamespace(
        channel_access_token="token",
    )

    monkeypatch.setattr(
        runtime_module,
        "LineMessagingClient",
        lambda channel_access_token: fake_line_client,
    )

    fake_notification_service = SimpleNamespace(
        line_client=fake_line_client,
    )

    monkeypatch.setattr(
        runtime_module,
        "NotificationService",
        lambda line_client: fake_notification_service,
    )

    def build_worker(
        *,
        session_factory,
        provider,
        notification_service,
    ):
        captured["worker_session_factory"] = (
            session_factory
        )
        captured["worker_provider"] = provider
        captured["worker_notification_service"] = (
            notification_service
        )
        return fake_worker

    monkeypatch.setattr(
        runtime_module,
        "TaskJobWorker",
        build_worker,
        raising=False,
    )

    def build_dispatcher(
        worker,
        *,
        max_workers,
    ):
        captured["dispatcher_worker"] = worker
        captured["max_workers"] = max_workers
        return fake_dispatcher

    monkeypatch.setattr(
        runtime_module,
        "LocalJobDispatcher",
        build_dispatcher,
        raising=False,
    )

    monkeypatch.setattr(
        runtime_module,
        "configure_line_webhook_dependencies",
        lambda dependencies: captured.setdefault(
            "dependencies",
            dependencies,
        ),
    )

    settings = SimpleNamespace(
        database_url=(
            "postgresql+psycopg://user:pass@db/app"
        ),
        line_channel_secret="secret",
        line_channel_access_token="token",
        openai_model="gpt-5.6",
        background_max_workers=3,
    )

    runtime = runtime_module.configure_runtime(
        settings
    )

    assert captured["engine"] is fake_engine

    assert runtime.session_factory is fake_factory
    assert runtime.dispatcher is fake_dispatcher

    assert (
        captured["worker_session_factory"]
        is fake_factory
    )
    assert (
        captured["worker_provider"]
        is fake_provider
    )
    assert (
        captured["worker_notification_service"]
        is fake_notification_service
    )

    assert (
        captured["dispatcher_worker"]
        is fake_worker
    )
    assert captured["max_workers"] == 3

    dependencies = captured[
        "dependencies"
    ]

    assert (
        dependencies.session_factory
        is fake_factory
    )
    assert (
        dependencies.channel_secret
        == "secret"
    )
    assert (
        dependencies.dispatcher
        is fake_dispatcher
    )
    assert (
        dependencies.notification_service
        is fake_notification_service
    )


def test_runtime_close_shuts_down_dispatcher() -> None:
    dispatcher = RecordingDispatcher()
    events: list[str] = []

    runtime = runtime_module.Runtime(
        session_factory=object(),
        dispatcher=dispatcher,
        line_client=RecordingLineClient(events),
        engine=RecordingEngine(events),
    )

    runtime.close()

    assert dispatcher.shutdown_calls == [
        True,
    ]

def test_runtime_close_releases_resources_in_order() -> None:
    events: list[str] = []

    runtime = runtime_module.Runtime(
        session_factory=object(),
        dispatcher=OrderedRecordingDispatcher(events),
        line_client=RecordingLineClient(events),
        engine=RecordingEngine(events),
    )

    runtime.close()

    assert events == [
        "dispatcher",
        "line_client",
        "engine",
    ]