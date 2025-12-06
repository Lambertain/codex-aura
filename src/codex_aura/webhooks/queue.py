"""Webhook processing queue."""

import asyncio
import logging
from typing import Optional
from .models import WebhookEvent

logger = logging.getLogger(__name__)


class WebhookQueue:
    """Asynchronous queue for webhook events."""

    def __init__(self, maxsize: int = 1000):
        self.queue: asyncio.Queue[WebhookEvent] = asyncio.Queue(maxsize=maxsize)
        self._processing_task: Optional[asyncio.Task] = None
        self._running = False

    async def enqueue(self, event: WebhookEvent) -> None:
        """Add webhook event to processing queue."""
        try:
            await self.queue.put(event)
            logger.info(f"Enqueued webhook event: {event.event} for repo {event.repo_id}")
        except asyncio.QueueFull:
            logger.error("Webhook queue is full, dropping event")
            raise RuntimeError("Webhook queue is full")

    async def dequeue(self) -> WebhookEvent:
        """Get next webhook event from queue."""
        return await self.queue.get()

    def start_processing(self, processor_func):
        """Start background processing of webhook events."""
        if self._processing_task is not None:
            logger.warning("Webhook processing already running")
            return

        self._running = True
        self._processing_task = asyncio.create_task(self._process_queue(processor_func))
        logger.info("Started webhook processing")

    async def stop_processing(self):
        """Stop background processing."""
        self._running = False
        if self._processing_task:
            self._processing_task.cancel()
            try:
                await self._processing_task
            except asyncio.CancelledError:
                pass
        logger.info("Stopped webhook processing")

    async def _process_queue(self, processor_func):
        """Background task to process webhook events."""
        while self._running:
            try:
                event = await self.dequeue()
                logger.info(f"Processing webhook event: {event.event} for repo {event.repo_id}")

                # Process the event
                await processor_func(event)

                # Mark as processed
                event.processed = True
                event.processing_completed_at = event.received_at.__class__.utcnow()

            except Exception as e:
                logger.error(f"Error processing webhook event: {e}")
                if 'event' in locals():
                    event.error = str(e)

    def get_queue_size(self) -> int:
        """Get current queue size."""
        return self.queue.qsize()

    def is_processing(self) -> bool:
        """Check if processing is active."""
        return self._running and self._processing_task and not self._processing_task.done()