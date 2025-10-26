"""Event publisher for NATS JetStream.

Provides high-level interface for publishing events with:
- Automatic serialization
- Batch publishing support
- Retry logic with exponential backoff
- Observability hooks
"""

import asyncio
import logging
from typing import Optional

from nats.js.api import PubAck

from vertector_nats.client import NATSClient
from vertector_nats.events import BaseEvent
from vertector_nats.metrics import (
    events_published_total,
    payload_size_bytes,
    publish_duration_seconds,
    publish_errors_total,
    publish_retries_total,
)

logger = logging.getLogger(__name__)


class PublishError(Exception):
    """Raised when event publishing fails."""

    pass


class EventPublisher:
    """High-level event publisher for NATS JetStream.

    Features:
    - Type-safe event publishing
    - Automatic JSON serialization
    - Batch publishing with parallel execution
    - Retry logic with exponential backoff
    - Publishing metrics and tracing

    Example:
        >>> publisher = EventPublisher(client)
        >>> event = CourseCreatedEvent(
        ...     course_code="CS101",
        ...     course_name="Intro to CS",
        ...     semester="Fall 2025",
        ...     credits=3,
        ...     instructor="Dr. Smith",
        ...     metadata=EventMetadata(source_service="schedule-service")
        ... )
        >>> ack = await publisher.publish(event)
    """

    def __init__(
        self,
        client: NATSClient,
        default_timeout: float = 5.0,
        max_retries: int = 3,
        retry_backoff_base: float = 2.0,
    ) -> None:
        """Initialize event publisher.

        Args:
            client: NATS client instance
            default_timeout: Default timeout for publish operations in seconds
            max_retries: Maximum number of retry attempts
            retry_backoff_base: Base for exponential backoff (seconds)
        """
        self.client = client
        self.default_timeout = default_timeout
        self.max_retries = max_retries
        self.retry_backoff_base = retry_backoff_base

        logger.info(
            "EventPublisher initialized",
            extra={
                "timeout": default_timeout,
                "max_retries": max_retries,
                "backoff_base": retry_backoff_base,
            },
        )

    async def publish(
        self,
        event: BaseEvent,
        headers: Optional[dict[str, str]] = None,
        timeout: Optional[float] = None,
    ) -> PubAck:
        """Publish a single event to JetStream.

        Args:
            event: Event to publish (must inherit from BaseEvent)
            headers: Optional NATS headers to attach
            timeout: Publish timeout in seconds (defaults to default_timeout)

        Returns:
            PubAck: Publication acknowledgment from NATS

        Raises:
            PublishError: If publication fails after all retries
            ValueError: If event validation fails

        Example:
            >>> event = AssignmentCreatedEvent(
            ...     assignment_id="a123",
            ...     course_code="MATH201",
            ...     title="Homework 1",
            ...     due_date=datetime.now(),
            ...     metadata=EventMetadata(source_service="schedule-service")
            ... )
            >>> ack = await publisher.publish(event)
            >>> print(f"Published to stream {ack.stream}, seq {ack.seq}")
        """
        timeout = timeout or self.default_timeout

        # Serialize event to JSON bytes (Pydantic validates on creation)
        payload = event.model_dump_json().encode("utf-8")

        # Convert event_type to string for metrics
        event_type_str = str(event.event_type.value) if hasattr(event.event_type, 'value') else str(event.event_type)

        # Record payload size metric
        payload_size_bytes.labels(event_type=event_type_str).observe(len(payload))

        # Validate payload size
        max_payload = self.client.config.max_payload_bytes
        if len(payload) > max_payload:
            raise ValueError(
                f"Event payload too large: {len(payload):,} bytes "
                f"(max: {max_payload:,} bytes). "
                f"Event: {event.event_type} (ID: {event.event_id}). "
                f"Consider splitting into multiple events or reducing payload size."
            )

        logger.debug(
            f"Serialized event payload: {len(payload)} bytes",
            extra={"event_id": str(event.event_id), "payload_size": len(payload)}
        )

        # Convert event_type to string (handles both Enum and str)
        subject = str(event.event_type.value) if hasattr(event.event_type, 'value') else str(event.event_type)

        # Prepare headers
        pub_headers = headers or {}
        pub_headers.update(
            {
                "event-id": str(event.event_id),
                "event-version": event.event_version,
                "source-service": event.metadata.source_service,
            }
        )

        if event.metadata.correlation_id:
            pub_headers["correlation-id"] = event.metadata.correlation_id

        # Publish with retries
        last_error = None
        for attempt in range(self.max_retries):
            try:
                # Time the publish operation
                with publish_duration_seconds.labels(event_type=event_type_str).time():
                    ack = await self.client.jetstream.publish(
                        subject=subject,
                        payload=payload,
                        headers=pub_headers,
                        timeout=timeout,
                    )

                # Record successful publish
                events_published_total.labels(
                    event_type=event_type_str,
                    stream=ack.stream,
                    status="success"
                ).inc()

                logger.info(
                    f"Published event {event.event_type}",
                    extra={
                        "event_id": str(event.event_id),
                        "event_type": event.event_type,
                        "stream": ack.stream,
                        "sequence": ack.seq,
                        "attempt": attempt + 1,
                    },
                )

                return ack

            except Exception as e:
                last_error = e
                error_type = type(e).__name__
                wait_time = self.retry_backoff_base ** attempt

                # Record retry attempt
                if attempt > 0:  # Don't count first attempt as retry
                    publish_retries_total.labels(
                        event_type=event_type_str,
                        attempt=str(attempt + 1)
                    ).inc()

                logger.warning(
                    f"Publish attempt {attempt + 1}/{self.max_retries} failed: {e}",
                    extra={
                        "event_id": str(event.event_id),
                        "event_type": event.event_type,
                        "attempt": attempt + 1,
                        "wait_time": wait_time,
                        "error_type": error_type,
                    },
                )

                if attempt < self.max_retries - 1:
                    await asyncio.sleep(wait_time)

        # All retries exhausted - record final failure
        error_type = type(last_error).__name__ if last_error else "Unknown"

        # Record failed publish
        events_published_total.labels(
            event_type=event_type_str,
            stream="unknown",  # Stream unknown on failure
            status="failure"
        ).inc()

        # Record error by type
        publish_errors_total.labels(
            event_type=event_type_str,
            error_type=error_type
        ).inc()

        error_msg = f"Failed to publish event after {self.max_retries} attempts"
        logger.error(
            error_msg,
            extra={
                "event_id": str(event.event_id),
                "event_type": event.event_type,
                "last_error": str(last_error),
            },
        )
        raise PublishError(f"{error_msg}: {last_error}") from last_error

    async def publish_batch(
        self,
        events: list[BaseEvent],
        headers: Optional[dict[str, str]] = None,
        timeout: Optional[float] = None,
        parallel: bool = True,
    ) -> list[PubAck]:
        """Publish multiple events efficiently.

        Args:
            events: List of events to publish
            headers: Optional headers to attach to all events
            timeout: Publish timeout for each event
            parallel: If True, publish events in parallel; if False, sequential

        Returns:
            List of PubAck acknowledgments in the same order as events

        Raises:
            PublishError: If any publication fails

        Example:
            >>> events = [
            ...     CourseCreatedEvent(...),
            ...     AssignmentCreatedEvent(...),
            ...     ExamCreatedEvent(...),
            ... ]
            >>> acks = await publisher.publish_batch(events, parallel=True)
        """
        if not events:
            logger.warning("publish_batch called with empty events list")
            return []

        logger.info(
            f"Publishing batch of {len(events)} events",
            extra={"count": len(events), "parallel": parallel},
        )

        if parallel:
            # Publish all events in parallel
            tasks = [self.publish(event, headers, timeout) for event in events]
            acks = await asyncio.gather(*tasks, return_exceptions=False)
        else:
            # Publish sequentially
            acks = []
            for event in events:
                ack = await self.publish(event, headers, timeout)
                acks.append(ack)

        logger.info(
            f"Successfully published batch of {len(events)} events",
            extra={"count": len(events)},
        )

        return acks

    async def publish_with_reply(
        self,
        event: BaseEvent,
        reply_subject: str,
        headers: Optional[dict[str, str]] = None,
        timeout: Optional[float] = None,
    ) -> PubAck:
        """Publish event with a reply subject for request-reply pattern.

        Args:
            event: Event to publish
            reply_subject: Subject where replies should be sent
            headers: Optional headers
            timeout: Publish timeout

        Returns:
            PubAck: Publication acknowledgment

        Raises:
            PublishError: If publication fails

        Example:
            >>> reply_inbox = "_INBOX.reply123"
            >>> ack = await publisher.publish_with_reply(
            ...     event,
            ...     reply_subject=reply_inbox
            ... )
        """
        pub_headers = headers or {}
        pub_headers["reply-to"] = reply_subject

        return await self.publish(event, headers=pub_headers, timeout=timeout)
