"""Webhook processing queue using Redis with arq."""

import logging
from typing import Optional
from arq import create_pool
from arq.connections import RedisSettings
from arq.worker import Worker
from .models import WebhookEvent
from .processor import WebhookProcessor

logger = logging.getLogger(__name__)

# Redis settings
redis_settings = RedisSettings(host="localhost", port=6379, database=0)

# Global processor instance
_processor: Optional[WebhookProcessor] = None


def set_webhook_processor(processor: WebhookProcessor) -> None:
    """Set the global webhook processor instance."""
    global _processor
    _processor = processor


async def process_webhook(ctx, event_data: dict) -> None:
    """
    Process webhook event using arq.

    This function is called by arq worker with retry logic.
    """
    if _processor is None:
        raise RuntimeError("Webhook processor not initialized")

    try:
        # Convert dict back to WebhookEvent
        event = WebhookEvent(**event_data)
        logger.info(f"Processing webhook event: {event.event} for repo {event.repo_id}")

        # Process the event
        await _processor.process_event(event)

        logger.info(f"Successfully processed webhook event: {event.event} for repo {event.repo_id}")

    except Exception as e:
        logger.error(f"Error processing webhook event: {e}")
        # Re-raise to trigger arq retry logic
        raise


async def process_failed_webhook(ctx, event_data: dict) -> None:
    """
    Handle failed webhook events - dead letter queue.

    This function processes events that have failed all retries.
    """
    try:
        event = WebhookEvent(**event_data)
        logger.error(f"Webhook event failed permanently: {event.event} for repo {event.repo_id}")

        # Here you could:
        # - Store in database for manual review
        # - Send notification to admin
        # - Log to monitoring system
        # For now, just log the failure

    except Exception as e:
        logger.critical(f"Error in dead letter queue handler: {e}")


class WebhookQueue:
    """Redis-based queue for webhook events using arq."""

    def __init__(self):
        self.redis_pool = None

    async def initialize(self) -> None:
        """Initialize Redis connection pool."""
        if self.redis_pool is None:
            self.redis_pool = await create_pool(redis_settings)
            logger.info("Webhook queue Redis pool initialized")

    async def enqueue(self, event: WebhookEvent) -> None:
        """Add webhook event to Redis queue."""
        if self.redis_pool is None:
            await self.initialize()

        try:
            # Convert event to dict for arq
            event_dict = event.dict()
            await self.redis_pool.enqueue_job('process_webhook', event_dict)
            logger.info(f"Enqueued webhook event: {event.event} for repo {event.repo_id}")
        except Exception as e:
            logger.error(f"Failed to enqueue webhook event: {e}")
            raise

    async def close(self) -> None:
        """Close Redis connection pool."""
        if self.redis_pool:
            await self.redis_pool.close()
            self.redis_pool = None
            logger.info("Webhook queue Redis pool closed")


# Worker settings for arq
class WorkerSettings:
    """Arq worker configuration."""

    functions = [process_webhook, process_failed_webhook]
    redis_settings = redis_settings

    # Retry configuration
    max_jobs = 10  # Concurrent jobs
    job_timeout = 300  # 5 minutes timeout per job
    max_tries = 3  # Retry failed jobs up to 3 times
    retry_delay = 60  # Wait 60 seconds between retries

    # Health check
    health_check_interval = 60

    # Dead letter queue - jobs that fail all retries go here
    # Note: arq doesn't have built-in DLQ, but we can implement it
    # by catching JobExecutionFailed and enqueueing to another queue


async def get_worker() -> Worker:
    """Create and return arq worker instance."""
    return Worker(WorkerSettings)