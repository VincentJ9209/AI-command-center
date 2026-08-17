from types import SimpleNamespace

from app.bootstrap import runtime as runtime_module
from app.config.settings import Settings


def test_configure_runtime_wires_dependencies(monkeypatch) -> None:
    fake_engine = object()
    fake_factory = object()
    captured = {}

    monkeypatch.setattr(
        runtime_module,
        "build_engine",
        lambda *args, **kwargs: fake_engine,
    )
    monkeypatch.setattr(
        runtime_module.Base.metadata,
        "create_all",
        lambda engine: captured.setdefault("engine", engine),
    )
    monkeypatch.setattr(
        runtime_module,
        "build_session_factory",
        lambda engine: fake_factory,
    )
    monkeypatch.setattr(
        runtime_module,
        "OpenAIResponsesProvider",
        lambda model: SimpleNamespace(model=model),
    )
    monkeypatch.setattr(
        runtime_module,
        "LineMessagingClient",
        lambda channel_access_token: SimpleNamespace(
            channel_access_token=channel_access_token
        ),
    )
    monkeypatch.setattr(
        runtime_module,
        "NotificationService",
        lambda line_client: SimpleNamespace(line_client=line_client),
    )
    monkeypatch.setattr(
        runtime_module,
        "configure_line_webhook_dependencies",
        lambda dependencies: captured.setdefault("dependencies", dependencies),
    )

    settings = Settings(
        database_url="postgresql+psycopg://user:pass@db/app",
        line_channel_secret="secret",
        line_channel_access_token="token",
        openai_model="gpt-5.6",
    )

    runtime = runtime_module.configure_runtime(settings)

    assert captured["engine"] is fake_engine
    assert runtime.session_factory is fake_factory
    assert captured["dependencies"].session_factory is fake_factory
    assert captured["dependencies"].channel_secret == "secret"
    assert captured["dependencies"].provider.model == "gpt-5.6"
    assert (
        captured["dependencies"]
        .notification_service.line_client.channel_access_token
        == "token"
    )
