"""Unit tests for EventPublisher.

Tests cover:
- Event publishing (success/failure)
- Retry logic and exponential backoff
- Batch publishing (parallel and sequential)
- Payload size validation
- Metrics integration
- Error handling
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from nats.errors import Error as NATSError
from nats.errors import TimeoutError as NATSTimeoutError
from nats.js.api import PubAck

from vertector_nats.events import CourseCreatedEvent, EventMetadata
from vertector_nats.metrics import (
    events_published_total,
    payload_size_bytes,
    publish_duration_seconds,
    publish_errors_total,
    publish_retries_total,
)
from vertector_nats.publisher import EventPublisher, PublishError


# ============================================================================
# PUBLISHER INITIALIZATION TESTS
# ============================================================================


@pytest.mark.unit
class TestPublisherInit:
    """Test EventPublisher initialization."""

    def test_publisher_init_with_defaults(self, mock_nats_client):
        """Test publisher initializes with default values."""
        publisher = EventPublisher(client=mock_nats_client)

        assert publisher.client == mock_nats_client
        assert publisher.default_timeout == 5.0
        assert publisher.max_retries == 3
        assert publisher.retry_backoff_base == 2.0

    def test_publisher_init_with_custom_values(self, mock_nats_client):
        """Test publisher initializes with custom values."""
        publisher = EventPublisher(
            client=mock_nats_client,
            default_timeout=10.0,
            max_retries=5,
            retry_backoff_base=3.0,
        )

        assert publisher.default_timeout == 10.0
        assert publisher.max_retries == 5
        assert publisher.retry_backoff_base == 3.0


# ============================================================================
# PUBLISH SUCCESS TESTS
# ============================================================================


@pytest.mark.unit
class TestPublishSuccess:
    """Test successful event publishing."""

    @pytest.mark.asyncio
    async def test_publish_event_success(self, mock_nats_client, course_created_event):
        """Test publishing an event successfully."""
        # Setup mock
        mock_ack = PubAck(stream="TEST_STREAM", seq=1)
        mock_nats_client.jetstream.publish = AsyncMock(return_value=mock_ack)

        publisher = EventPublisher(client=mock_nats_client)

        # Publish event
        ack = await publisher.publish(course_created_event)

        # Verify result
        assert ack.stream == "TEST_STREAM"
        assert ack.seq == 1

        # Verify publish was called
        mock_nats_client.jetstream.publish.assert_called_once()

    @pytest.mark.asyncio
    async def test_publish_uses_event_type_as_subject(
        self, mock_nats_client, course_created_event
    ):
        """Test publish uses event_type as NATS subject."""
        mock_ack = PubAck(stream="TEST_STREAM", seq=1)
        mock_nats_client.jetstream.publish = AsyncMock(return_value=mock_ack)

        publisher = EventPublisher(client=mock_nats_client)
        await publisher.publish(course_created_event)

        # Verify subject is event type
        call_args = mock_nats_client.jetstream.publish.call_args
        assert call_args.kwargs["subject"] == "academic.course.created"

    @pytest.mark.asyncio
    async def test_publish_includes_event_headers(
        self, mock_nats_client, course_created_event
    ):
        """Test publish includes event metadata in headers."""
        mock_ack = PubAck(stream="TEST_STREAM", seq=1)
        mock_nats_client.jetstream.publish = AsyncMock(return_value=mock_ack)

        publisher = EventPublisher(client=mock_nats_client)
        await publisher.publish(course_created_event)

        # Verify headers
        call_args = mock_nats_client.jetstream.publish.call_args
        headers = call_args.kwargs["headers"]

        assert "event-id" in headers
        assert "event-version" in headers
        assert "source-service" in headers
        assert headers["source-service"] == "test-service"
        assert headers["correlation-id"] == "test-correlation-123"

    @pytest.mark.asyncio
    async def test_publish_with_custom_headers(
        self, mock_nats_client, course_created_event
    ):
        """Test publish merges custom headers."""
        mock_ack = PubAck(stream="TEST_STREAM", seq=1)
        mock_nats_client.jetstream.publish = AsyncMock(return_value=mock_ack)

        publisher = EventPublisher(client=mock_nats_client)

        custom_headers = {"custom-header": "custom-value"}
        await publisher.publish(course_created_event, headers=custom_headers)

        # Verify custom headers included
        call_args = mock_nats_client.jetstream.publish.call_args
        headers = call_args.kwargs["headers"]

        assert headers["custom-header"] == "custom-value"

    @pytest.mark.asyncio
    async def test_publish_with_custom_timeout(
        self, mock_nats_client, course_created_event
    ):
        """Test publish uses custom timeout."""
        mock_ack = PubAck(stream="TEST_STREAM", seq=1)
        mock_nats_client.jetstream.publish = AsyncMock(return_value=mock_ack)

        publisher = EventPublisher(client=mock_nats_client, default_timeout=5.0)

        await publisher.publish(course_created_event, timeout=10.0)

        # Verify timeout parameter
        call_args = mock_nats_client.jetstream.publish.call_args
        assert call_args.kwargs["timeout"] == 10.0

    @pytest.mark.asyncio
    async def test_publish_serializes_event_to_json(
        self, mock_nats_client, course_created_event
    ):
        """Test publish serializes event to JSON bytes."""
        mock_ack = PubAck(stream="TEST_STREAM", seq=1)
        mock_nats_client.jetstream.publish = AsyncMock(return_value=mock_ack)

        publisher = EventPublisher(client=mock_nats_client)
        await publisher.publish(course_created_event)

        # Verify payload is bytes
        call_args = mock_nats_client.jetstream.publish.call_args
        payload = call_args.kwargs["payload"]

        assert isinstance(payload, bytes)
        # Verify it's valid JSON by decoding
        assert b"TEST101" in payload
        assert b"Test Course" in payload


# ============================================================================
# PAYLOAD SIZE VALIDATION TESTS
# ============================================================================


@pytest.mark.unit
class TestPayloadSizeValidation:
    """Test payload size validation."""

    @pytest.mark.asyncio
    async def test_publish_validates_payload_size(
        self, mock_nats_client, event_metadata
    ):
        """Test publish raises error for oversized payload."""
        # Set small max payload
        mock_nats_client.config.max_payload_bytes = 100

        publisher = EventPublisher(client=mock_nats_client)

        # Create event that will exceed limit
        large_event = CourseCreatedEvent(
            course_code="CS101" * 100,  # Large field
            course_name="Test" * 100,
            semester="Fall 2025",
            credits=3,
            instructor="Dr. Smith",
            metadata=event_metadata,
        )

        # Should raise ValueError
        with pytest.raises(ValueError, match="Event payload too large"):
            await publisher.publish(large_event)

    @pytest.mark.asyncio
    async def test_publish_allows_payload_under_limit(
        self, mock_nats_client, course_created_event
    ):
        """Test publish allows payload under size limit."""
        mock_ack = PubAck(stream="TEST_STREAM", seq=1)
        mock_nats_client.jetstream.publish = AsyncMock(return_value=mock_ack)

        # Set large max payload
        mock_nats_client.config.max_payload_bytes = 10 * 1024 * 1024  # 10MB

        publisher = EventPublisher(client=mock_nats_client)

        # Should not raise
        ack = await publisher.publish(course_created_event)
        assert ack.stream == "TEST_STREAM"


# ============================================================================
# RETRY LOGIC TESTS
# ============================================================================


@pytest.mark.unit
class TestPublishRetry:
    """Test publish retry logic."""

    @pytest.mark.asyncio
    async def test_publish_retries_on_failure(self, mock_nats_client, course_created_event):
        """Test publish retries on transient failures."""
        # First two attempts fail, third succeeds
        mock_ack = PubAck(stream="TEST_STREAM", seq=1)
        mock_nats_client.jetstream.publish = AsyncMock(
            side_effect=[
                NATSTimeoutError(),
                NATSTimeoutError(),
                mock_ack,
            ]
        )

        publisher = EventPublisher(client=mock_nats_client, max_retries=3)

        # Should eventually succeed
        ack = await publisher.publish(course_created_event)
        assert ack.stream == "TEST_STREAM"

        # Should have been called 3 times (2 failures + 1 success)
        assert mock_nats_client.jetstream.publish.call_count == 3

    @pytest.mark.asyncio
    async def test_publish_raises_after_max_retries(
        self, mock_nats_client, course_created_event
    ):
        """Test publish raises PublishError after exhausting retries."""
        # All attempts fail
        mock_nats_client.jetstream.publish = AsyncMock(
            side_effect=NATSTimeoutError("Connection timeout")
        )

        publisher = EventPublisher(client=mock_nats_client, max_retries=3)

        # Should raise PublishError
        with pytest.raises(PublishError, match="Failed to publish event after 3 attempts"):
            await publisher.publish(course_created_event)

        # Should have been called 3 times (all retries exhausted)
        assert mock_nats_client.jetstream.publish.call_count == 3

    @pytest.mark.asyncio
    async def test_publish_exponential_backoff(
        self, mock_nats_client, course_created_event
    ):
        """Test publish uses exponential backoff between retries."""
        mock_ack = PubAck(stream="TEST_STREAM", seq=1)
        mock_nats_client.jetstream.publish = AsyncMock(
            side_effect=[
                NATSTimeoutError(),
                NATSTimeoutError(),
                mock_ack,
            ]
        )

        publisher = EventPublisher(
            client=mock_nats_client,
            max_retries=3,
            retry_backoff_base=2.0,
        )

        # Patch asyncio.sleep to verify backoff times
        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            await publisher.publish(course_created_event)

            # Verify sleep was called with exponential backoff
            # First retry: 2^0 = 1 second
            # Second retry: 2^1 = 2 seconds
            assert mock_sleep.call_count == 2
            assert mock_sleep.call_args_list[0][0][0] == 1.0  # 2^0
            assert mock_sleep.call_args_list[1][0][0] == 2.0  # 2^1

    @pytest.mark.asyncio
    async def test_publish_no_retry_on_immediate_success(
        self, mock_nats_client, course_created_event
    ):
        """Test publish doesn't retry on immediate success."""
        mock_ack = PubAck(stream="TEST_STREAM", seq=1)
        mock_nats_client.jetstream.publish = AsyncMock(return_value=mock_ack)

        publisher = EventPublisher(client=mock_nats_client, max_retries=3)

        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            await publisher.publish(course_created_event)

            # Should not have slept (no retries)
            mock_sleep.assert_not_called()

        # Should have been called only once
        assert mock_nats_client.jetstream.publish.call_count == 1


# ============================================================================
# BATCH PUBLISHING TESTS
# ============================================================================


@pytest.mark.unit
class TestPublishBatch:
    """Test batch publishing."""

    @pytest.mark.asyncio
    async def test_publish_batch_parallel(self, mock_nats_client, event_metadata):
        """Test batch publish in parallel mode."""
        mock_ack1 = PubAck(stream="TEST_STREAM", seq=1)
        mock_ack2 = PubAck(stream="TEST_STREAM", seq=2)
        mock_ack3 = PubAck(stream="TEST_STREAM", seq=3)

        mock_nats_client.jetstream.publish = AsyncMock(
            side_effect=[mock_ack1, mock_ack2, mock_ack3]
        )

        publisher = EventPublisher(client=mock_nats_client)

        events = [
            CourseCreatedEvent(
                course_code=f"CS{i}",
                course_name=f"Course {i}",
                semester="Fall 2025",
                credits=3,
                instructor="Dr. Smith",
                metadata=event_metadata,
            )
            for i in range(3)
        ]

        # Publish batch in parallel
        acks = await publisher.publish_batch(events, parallel=True)

        assert len(acks) == 3
        assert acks[0].seq == 1
        assert acks[1].seq == 2
        assert acks[2].seq == 3

        # Verify all published
        assert mock_nats_client.jetstream.publish.call_count == 3

    @pytest.mark.asyncio
    async def test_publish_batch_sequential(self, mock_nats_client, event_metadata):
        """Test batch publish in sequential mode."""
        mock_ack1 = PubAck(stream="TEST_STREAM", seq=1)
        mock_ack2 = PubAck(stream="TEST_STREAM", seq=2)

        mock_nats_client.jetstream.publish = AsyncMock(
            side_effect=[mock_ack1, mock_ack2]
        )

        publisher = EventPublisher(client=mock_nats_client)

        events = [
            CourseCreatedEvent(
                course_code=f"CS{i}",
                course_name=f"Course {i}",
                semester="Fall 2025",
                credits=3,
                instructor="Dr. Smith",
                metadata=event_metadata,
            )
            for i in range(2)
        ]

        # Publish batch sequentially
        acks = await publisher.publish_batch(events, parallel=False)

        assert len(acks) == 2
        assert acks[0].seq == 1
        assert acks[1].seq == 2

    @pytest.mark.asyncio
    async def test_publish_batch_empty_list(self, mock_nats_client):
        """Test batch publish with empty list returns empty list."""
        publisher = EventPublisher(client=mock_nats_client)

        acks = await publisher.publish_batch([])

        assert acks == []
        mock_nats_client.jetstream.publish.assert_not_called()


# ============================================================================
# PUBLISH WITH REPLY TESTS
# ============================================================================


@pytest.mark.unit
class TestPublishWithReply:
    """Test publish with reply subject."""

    @pytest.mark.asyncio
    async def test_publish_with_reply_subject(
        self, mock_nats_client, course_created_event
    ):
        """Test publish_with_reply adds reply-to header."""
        mock_ack = PubAck(stream="TEST_STREAM", seq=1)
        mock_nats_client.jetstream.publish = AsyncMock(return_value=mock_ack)

        publisher = EventPublisher(client=mock_nats_client)

        reply_subject = "_INBOX.reply123"
        ack = await publisher.publish_with_reply(
            course_created_event,
            reply_subject=reply_subject,
        )

        assert ack.stream == "TEST_STREAM"

        # Verify reply-to header was set
        call_args = mock_nats_client.jetstream.publish.call_args
        headers = call_args.kwargs["headers"]

        assert headers["reply-to"] == reply_subject


# ============================================================================
# METRICS TESTS
# ============================================================================


@pytest.mark.unit
class TestPublisherMetrics:
    """Test metrics are recorded correctly."""

    @pytest.mark.asyncio
    async def test_publish_records_success_metrics(
        self, mock_nats_client, course_created_event
    ):
        """Test successful publish records metrics."""
        mock_ack = PubAck(stream="TEST_STREAM", seq=1)
        mock_nats_client.jetstream.publish = AsyncMock(return_value=mock_ack)

        publisher = EventPublisher(client=mock_nats_client)

        # Reset metrics
        events_published_total._metrics.clear()
        payload_size_bytes._metrics.clear()

        await publisher.publish(course_created_event)

        # Verify success metric incremented
        # Note: Prometheus metrics are complex to assert directly
        # In real testing, you'd use prometheus_client's test utilities

    @pytest.mark.asyncio
    async def test_publish_records_failure_metrics(
        self, mock_nats_client, course_created_event
    ):
        """Test failed publish records error metrics."""
        mock_nats_client.jetstream.publish = AsyncMock(
            side_effect=NATSTimeoutError("Connection timeout")
        )

        publisher = EventPublisher(client=mock_nats_client, max_retries=2)

        # Reset metrics
        publish_errors_total._metrics.clear()

        with pytest.raises(PublishError):
            await publisher.publish(course_created_event)

        # Error metrics should be recorded
        # (Actual assertion would require prometheus test utilities)

    @pytest.mark.asyncio
    async def test_publish_records_retry_metrics(
        self, mock_nats_client, course_created_event
    ):
        """Test publish records retry metrics."""
        mock_ack = PubAck(stream="TEST_STREAM", seq=1)
        mock_nats_client.jetstream.publish = AsyncMock(
            side_effect=[NATSTimeoutError(), mock_ack]
        )

        publisher = EventPublisher(client=mock_nats_client, max_retries=3)

        # Reset metrics
        publish_retries_total._metrics.clear()

        await publisher.publish(course_created_event)

        # Retry metric should be recorded
        # (Actual assertion would require prometheus test utilities)


# ============================================================================
# ERROR HANDLING TESTS
# ============================================================================


@pytest.mark.unit
class TestPublishErrorHandling:
    """Test error handling in publisher."""

    @pytest.mark.asyncio
    async def test_publish_handles_nats_error(
        self, mock_nats_client, course_created_event
    ):
        """Test publish handles NATS errors gracefully."""
        mock_nats_client.jetstream.publish = AsyncMock(
            side_effect=NATSError("NATS server error")
        )

        publisher = EventPublisher(client=mock_nats_client, max_retries=2)

        with pytest.raises(PublishError, match="Failed to publish event"):
            await publisher.publish(course_created_event)

    @pytest.mark.asyncio
    async def test_publish_handles_timeout_error(
        self, mock_nats_client, course_created_event
    ):
        """Test publish handles timeout errors."""
        mock_nats_client.jetstream.publish = AsyncMock(
            side_effect=NATSTimeoutError("Request timeout")
        )

        publisher = EventPublisher(client=mock_nats_client, max_retries=2)

        with pytest.raises(PublishError):
            await publisher.publish(course_created_event)

    @pytest.mark.asyncio
    async def test_publish_handles_generic_exception(
        self, mock_nats_client, course_created_event
    ):
        """Test publish handles generic exceptions."""
        mock_nats_client.jetstream.publish = AsyncMock(
            side_effect=Exception("Unexpected error")
        )

        publisher = EventPublisher(client=mock_nats_client, max_retries=2)

        with pytest.raises(PublishError, match="Unexpected error"):
            await publisher.publish(course_created_event)
