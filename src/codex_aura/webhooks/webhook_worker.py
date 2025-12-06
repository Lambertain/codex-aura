#!/usr/bin/env python3
"""Webhook worker using arq."""

import asyncio
import logging
import sys
from pathlib import Path

# Add src to path for imports
src_path = Path(__file__).parent.parent
sys.path.insert(0, str(src_path))

from .queue import WorkerSettings, set_webhook_processor, get_worker
from .processor import WebhookProcessor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def main():
    """Main worker function."""
    logger.info("Starting webhook worker...")

    try:
        # Initialize webhook processor
        # Note: You might need to pass dependencies like graph_updater here
        processor = WebhookProcessor(graph_updater=None)  # TODO: inject proper dependencies
        set_webhook_processor(processor)

        # Create and start worker
        worker = await get_worker()
        logger.info("Webhook worker started successfully")

        # Run worker
        await worker.async_run()

    except KeyboardInterrupt:
        logger.info("Webhook worker stopped by user")
    except Exception as e:
        logger.error(f"Webhook worker failed: {e}")
        raise
    finally:
        logger.info("Webhook worker shutdown complete")


if __name__ == "__main__":
    asyncio.run(main())