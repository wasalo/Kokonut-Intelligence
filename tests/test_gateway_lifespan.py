"""Gateway lifecycle resource management tests."""

import asyncio

import pytest

pytest.importorskip("fastapi")

from services.gateway.app import create_app  # noqa: E402


def test_audit_replay_lifespan_cancels_worker_on_shutdown(monkeypatch) -> None:
    app = create_app()
    replay_tasks = []
    create_task = asyncio.create_task

    def capture_task(coroutine):
        task = create_task(coroutine)
        replay_tasks.append(task)
        return task

    monkeypatch.setattr("services.gateway.app.asyncio.create_task", capture_task)
    monkeypatch.setattr("services.gateway.audit.GatewayAudit.replay_pending", lambda self, limit=100: 0)

    async def exercise_lifespan():
        async with app.router.lifespan_context(app):
            await asyncio.sleep(0)
            assert len(replay_tasks) == 1
            assert not replay_tasks[0].done()
        assert replay_tasks[0].cancelled()

    asyncio.run(exercise_lifespan())
