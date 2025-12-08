import pytest
from unittest.mock import AsyncMock

from src.codex_aura.webhooks.models import WebhookEvent
from src.codex_aura.webhooks.processor import WebhookProcessor
from src.codex_aura.webhooks.queue import (
    set_webhook_processor,
    process_webhook,
    process_failed_webhook,
)


@pytest.mark.asyncio
async def test_github_push_webhook_creates_snapshots():
    """Push event должен триггерить создание снапшотов по каждому коммиту."""
    snapshot_service = AsyncMock()
    snapshot_service.create_snapshot = AsyncMock()
    processor = WebhookProcessor(snapshot_service=snapshot_service)

    event = WebhookEvent(
        repo_id="test-repo",
        event="push",
        data={
            "commits": [
                {"id": "abc123", "message": "test1"},
                {"id": "def456", "message": "test2"},
            ]
        },
    )

    await processor.process_event(event)

    assert snapshot_service.create_snapshot.await_count == 2
    snapshot_service.create_snapshot.assert_any_await("test-repo", "abc123")
    snapshot_service.create_snapshot.assert_any_await("test-repo", "def456")


@pytest.mark.asyncio
async def test_push_continues_on_snapshot_error():
    """Ошибки по одному коммиту не должны блокировать остальные."""
    snapshot_service = AsyncMock()
    snapshot_service.create_snapshot = AsyncMock(side_effect=[Exception("fail"), "ok"])
    processor = WebhookProcessor(snapshot_service=snapshot_service)

    event = WebhookEvent(
        repo_id="test-repo",
        event="push",
        data={"commits": [{"id": "bad"}, {"id": "good"}]},
    )

    await processor.process_event(event)

    assert snapshot_service.create_snapshot.await_count == 2
    snapshot_service.create_snapshot.assert_any_await("test-repo", "bad")
    snapshot_service.create_snapshot.assert_any_await("test-repo", "good")


@pytest.mark.asyncio
async def test_unknown_event_graceful():
    """Неизвестные события не должны падать и не зовут снапшоты."""
    snapshot_service = AsyncMock()
    snapshot_service.create_snapshot = AsyncMock()
    processor = WebhookProcessor(snapshot_service=snapshot_service)

    event = WebhookEvent(repo_id="test-repo", event="unknown", data={})

    await processor.process_event(event)

    snapshot_service.create_snapshot.assert_not_called()


@pytest.mark.asyncio
async def test_gitlab_merge_request_event_no_crash():
    """Событие merge_request (gitlab) обрабатывается без исключений."""
    snapshot_service = AsyncMock()
    processor = WebhookProcessor(snapshot_service=snapshot_service)

    event = WebhookEvent(
        repo_id="test-repo",
        event="pull_request",
        data={"action": "merge_request", "pull_request": {"id": 1}},
    )

    # Просто должен выполниться без ошибок и без вызова снапшотов
    await processor.process_event(event)
    snapshot_service.create_snapshot.assert_not_called()


@pytest.mark.asyncio
async def test_process_webhook_propagates_error_for_retry():
    """process_webhook выбрасывает исключение для триггера retry в arq."""
    class FailingProcessor:
        async def process_event(self, event):
            raise RuntimeError("fail")

    set_webhook_processor(FailingProcessor())
    event_data = WebhookEvent(repo_id="r1", event="push", data={}).dict()

    with pytest.raises(RuntimeError):
        await process_webhook(None, event_data)


@pytest.mark.asyncio
async def test_dead_letter_handler_handles_event():
    """process_failed_webhook не падает на некорректных данных."""
    event_data = WebhookEvent(repo_id="r1", event="push", data={}).dict()
    await process_failed_webhook(None, event_data)
