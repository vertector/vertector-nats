"""Event consumer for NATS JetStream.

Provides high-level interface for consuming events with:
- Pull-based subscription (scalable)
- Automatic deserialization
- Message acknowledgment handling
- Error handling and retries
- Graceful shutdown
"""

import asyncio
import json
import logging
from typing import Awaitable, Callable, Optional

from nats.aio.msg import Msg
from nats.js.api import ConsumerConfig as JSConsumerConfig
from nats.js.errors import NotFoundError

from vertector_nats.client import NATSClient
from vertector_nats.config import ConsumerConfig
from vertector_nats.events import BaseEvent
from vertector_nats.metrics import (
    consume_duration_seconds,
    consumer_errors_total,
    consumer_processing_messages,
    events_consumed_total,
)

logger = logging.getLogger(__name__)

# Type alias for message handler functions
MessageHandler = Callable[[BaseEvent, Msg], Awaitable[None]]


class ConsumerError(Exception):
    """Raised when consumer operations fail."""

    pass


class EventConsumer:
    """High-level event consumer for NATS JetStream.

    Features:
    - Pull-based subscription for horizontal scaling
    - Automatic JSON deserialization to event objects
    - Configurable acknowledgment policies
    - Automatic retries with backoff
    - Graceful shutdown support
    - Message filtering by subject

    Example:
        >>> async def handle_course_event(event: BaseEvent, msg: Msg):
        ...     print(f"Received: {event.event_type}")
        ...     await msg.ack()
        ...
        >>> consumer = EventConsumer(
        ...     client=nats_client,
        ...     stream_name="ACADEMIC_EVENTS",
        ...     consumer_config=ConsumerConfig(
        ...         durable_name="notes-service-consumer",
        ...         filter_subjects=["academic.course.*"]
        ...     )
        ... )
        >>> await consumer.subscribe(handle_course_event)
    """

    def __init__(
        self,
        client: NATSClient,
        stream_name: str,
        consumer_config: ConsumerConfig,
        batch_size: int = 10,
        fetch_timeout: float = 5.0,
    ) -> None:
        """Initialize event consumer.

        Args:
            client: NATS client instance
            stream_name: Name of the JetStream stream to consume from
            consumer_config: Consumer configuration
            batch_size: Number of messages to fetch per batch
            fetch_timeout: Timeout for fetching messages in seconds
        """
        self.client = client
        self.stream_name = stream_name
        self.consumer_config = consumer_config
        self.batch_size = batch_size
        self.fetch_timeout = fetch_timeout

        self._running = False
        self._subscription = None

        logger.info(
            f"EventConsumer initialized for stream {stream_name}",
            extra={
                "stream": stream_name,
                "consumer": consumer_config.durable_name,
                "batch_size": batch_size,
            },
        )

    async def subscribe(
        self,
        handler: MessageHandler,
        graceful_shutdown_timeout: float = 30.0,
    ) -> None:
        """Subscribe to events and process them with the provided handler.

        This method runs indefinitely until stopped. It uses pull-based
        subscription for efficient, scalable message consumption.

        Args:
            handler: Async function to handle each message
            graceful_shutdown_timeout: Time to wait for in-flight messages on shutdown

        Raises:
            ConsumerError: If subscription fails

        Example:
            >>> async def my_handler(event: BaseEvent, msg: Msg):
            ...     if event.event_type == "academic.course.created":
            ...         await create_note_template(event.course_code)
            ...     await msg.ack()
            ...
            >>> await consumer.subscribe(my_handler)
        """
        try:
            # Create or get durable consumer
            await self._create_consumer()

            # Start pull subscription
            self._running = True
            await self._pull_loop(handler, graceful_shutdown_timeout)

        except Exception as e:
            logger.error(f"Subscription failed: {e}", exc_info=True)
            raise ConsumerError(f"Failed to subscribe: {e}") from e

    async def _create_consumer(self) -> None:
        """Create durable pull consumer if it doesn't exist."""
        js_consumer_config = JSConsumerConfig(
            durable_name=self.consumer_config.durable_name,
            ack_policy=self.consumer_config.ack_policy,
            ack_wait=self.consumer_config.ack_wait_seconds,
            max_deliver=self.consumer_config.max_deliver,
            filter_subjects=self.consumer_config.filter_subjects,
            deliver_policy=self.consumer_config.deliver_policy,
            replay_policy=self.consumer_config.replay_policy,
        )

        try:
            # Check if consumer exists
            await self.client.jetstream.consumer_info(
                self.stream_name,
                self.consumer_config.durable_name,
            )

            logger.info(
                f"Using existing consumer: {self.consumer_config.durable_name}",
                extra={
                    "stream": self.stream_name,
                    "consumer": self.consumer_config.durable_name,
                },
            )

        except NotFoundError:
            # Consumer doesn't exist, create it
            await self.client.jetstream.add_consumer(
                stream=self.stream_name,
                config=js_consumer_config,
            )

            logger.info(
                f"Created new consumer: {self.consumer_config.durable_name}",
                extra={
                    "stream": self.stream_name,
                    "consumer": self.consumer_config.durable_name,
                },
            )

    async def _pull_loop(
        self,
        handler: MessageHandler,
        graceful_shutdown_timeout: float,
    ) -> None:
        """Main pull loop for consuming messages.

        Args:
            handler: Message handler function
            graceful_shutdown_timeout: Shutdown timeout
        """
        # Determine filter subject for pull subscribe
        filter_subject = ""
        if self.consumer_config.filter_subjects:
            if len(self.consumer_config.filter_subjects) == 1:
                filter_subject = self.consumer_config.filter_subjects[0]
            # If multiple subjects, we rely on server-side filtering

        # Create pull subscription
        self._subscription = await self.client.jetstream.pull_subscribe(
            subject=filter_subject,
            durable=self.consumer_config.durable_name,
            stream=self.stream_name,
        )

        logger.info(
            f"Started pull subscription for {self.consumer_config.durable_name}",
            extra={
                "stream": self.stream_name,
                "consumer": self.consumer_config.durable_name,
                "filter": filter_subject or "all",
            },
        )

        # Process messages in batches
        try:
            while self._running:
                await self._fetch_and_process_batch(handler)

        except asyncio.CancelledError:
            logger.info("Consumer loop cancelled, shutting down gracefully")
            await self._graceful_shutdown(graceful_shutdown_timeout)
            raise

        except Exception as e:
            logger.error(f"Error in pull loop: {e}", exc_info=True)
            raise

    async def _fetch_and_process_batch(self, handler: MessageHandler) -> None:
        """Fetch and process a batch of messages.

        Args:
            handler: Message handler function
        """
        try:
            # Fetch batch of messages
            messages = await self._subscription.fetch(
                batch=self.batch_size,
                timeout=self.fetch_timeout,
            )

            if not messages:
                return

            logger.debug(
                f"Fetched {len(messages)} messages",
                extra={"count": len(messages)},
            )

            # Process each message
            for msg in messages:
                await self._process_message(msg, handler)

        except TimeoutError:
            # No messages available, continue polling
            pass

        except Exception as e:
            logger.error(f"Error fetching/processing batch: {e}", exc_info=True)

    async def _process_message(self, msg: Msg, handler: MessageHandler) -> None:
        """Process a single message.

        Args:
            msg: NATS message
            handler: Message handler function
        """
        consumer_name = self.consumer_config.durable_name
        event_type_str = "unknown"

        # Track in-flight message processing
        consumer_processing_messages.labels(consumer=consumer_name).inc()

        try:
            # Deserialize message payload
            data = json.loads(msg.data.decode("utf-8"))

            # Parse into BaseEvent
            event = BaseEvent(**data)
            event_type_str = str(event.event_type)

            logger.debug(
                f"Processing event {event.event_type}",
                extra={
                    "event_id": str(event.event_id),
                    "event_type": event.event_type,
                },
            )

            # Time the handler execution
            with consume_duration_seconds.labels(
                event_type=event_type_str,
                consumer=consumer_name
            ).time():
                # Call handler
                await handler(event, msg)

            # Record successful consumption (handler should ack/nak)
            # We assume success if no exception was raised
            events_consumed_total.labels(
                event_type=event_type_str,
                consumer=consumer_name,
                status="ack"
            ).inc()

        except json.JSONDecodeError as e:
            error_type = "JSONDecodeError"
            logger.error(f"Failed to decode message: {e}", exc_info=True)

            # Record error
            consumer_errors_total.labels(
                consumer=consumer_name,
                error_type=error_type
            ).inc()

            events_consumed_total.labels(
                event_type=event_type_str,
                consumer=consumer_name,
                status="nak"
            ).inc()

            # NAK to retry (might be corrupted)
            await msg.nak()

        except Exception as e:
            error_type = type(e).__name__
            logger.error(
                f"Error processing message: {e}",
                exc_info=True,
                extra={"subject": msg.subject},
            )

            # Record error
            consumer_errors_total.labels(
                consumer=consumer_name,
                error_type=error_type
            ).inc()

            events_consumed_total.labels(
                event_type=event_type_str,
                consumer=consumer_name,
                status="error"
            ).inc()

            # NAK to retry
            await msg.nak()

        finally:
            # Decrement in-flight counter
            consumer_processing_messages.labels(consumer=consumer_name).dec()

    async def stop(self) -> None:
        """Stop consuming messages gracefully."""
        logger.info("Stopping consumer")
        self._running = False

        if self._subscription:
            try:
                await self._subscription.unsubscribe()
            except Exception as e:
                logger.error(f"Error unsubscribing: {e}", exc_info=True)

    async def _graceful_shutdown(self, timeout: float) -> None:
        """Gracefully shutdown, waiting for in-flight messages.

        Args:
            timeout: Maximum time to wait for in-flight messages
        """
        logger.info(f"Graceful shutdown initiated (timeout: {timeout}s)")

        try:
            if self._subscription:
                # Unsubscribe from pull subscription (PullSubscription doesn't have drain())
                await asyncio.wait_for(
                    self._subscription.unsubscribe(),
                    timeout=timeout,
                )
        except asyncio.TimeoutError:
            logger.warning("Graceful shutdown timeout, forcing stop")
        except Exception as e:
            logger.error(f"Error during graceful shutdown: {e}", exc_info=True)

    async def __aenter__(self) -> "EventConsumer":
        """Enter async context manager."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:  # type: ignore
        """Exit async context manager."""
        await self.stop()
