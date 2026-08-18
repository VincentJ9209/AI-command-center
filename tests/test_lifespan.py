import asyncio
from types import SimpleNamespace

import pytest

from app import main as main_module


class RecordingRuntime:
    def __init__(self) -> None:
        self.close_calls = 0

    def close(self) -> None:
        self.close_calls += 1


def _configure_lifespan_dependencies(
    monkeypatch,
    runtime: RecordingRuntime,
) -> None:
    settings = SimpleNamespace(
        log_level="INFO",
    )

    monkeypatch.setattr(
        main_module.Settings,
        "from_env",
        classmethod(
            lambda cls: settings
        ),
    )

    monkeypatch.setattr(
        main_module,
        "configure_logging",
        lambda level: None,
    )

    monkeypatch.setattr(
        main_module,
        "configure_runtime",
        lambda received_settings: runtime,
    )


def test_lifespan_closes_runtime_on_shutdown(
    monkeypatch,
) -> None:
    runtime = RecordingRuntime()

    _configure_lifespan_dependencies(
        monkeypatch,
        runtime,
    )

    async def exercise() -> None:
        async with main_module.lifespan(
            main_module.app
        ):
            assert (
                main_module.app.state.runtime
                is runtime
            )
            assert runtime.close_calls == 0

        assert runtime.close_calls == 1

    asyncio.run(exercise())


def test_lifespan_closes_runtime_when_application_fails(
    monkeypatch,
) -> None:
    runtime = RecordingRuntime()

    _configure_lifespan_dependencies(
        monkeypatch,
        runtime,
    )

    async def exercise() -> None:
        with pytest.raises(
            RuntimeError,
            match="application failure",
        ):
            async with main_module.lifespan(
                main_module.app
            ):
                raise RuntimeError(
                    "application failure"
                )

    asyncio.run(exercise())

    assert runtime.close_calls == 1