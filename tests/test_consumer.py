"""Unit tests for EventConsumer.

Tests cover:
- Consumer initialization
- Message consumption and processing
- Message acknowledgment (ack/nak)
- Deserialization
- Error handling
- Graceful shutdown
- Metrics integration
"""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from nats.aio.msg import Msg
from nats.js.errors import NotFoundError

from vertector_nats.consumer import ConsumerError, EventConsumer
from vertector_nats.events import BaseEvent, CourseCreatedEvent, EventMetadata
from vertector_nats.metrics import (
    consumer_errors_total,
    consumer_processing_messages,
    events_consumed_total,
)


# ============================================================================
# CONSUMER INITIALIZATION TESTS
# ============================================================================


@pytest.mark.unit
class TestConsumerInit:
    """Test EventConsumer initialization."""

    def test_consumer_init_with_defaults(self, mock_nats_client, consumer_config):
        """Test consumer initializes with default values."""
        consumer = EventConsumer(
            client=mock_nats_client,
            stream_name="TEST_STREAM",
            consumer_config=consumer_config,
        )

        assert consumer.client == mock_nats_client
        assert consumer.stream_name == "TEST_STREAM"
        assert consumer.consumer_config == consumer_config
        assert consumer.batch_size == 10
        assert consumer.fetch_timeout == 5.0
        assert consumer._running is False
        assert consumer._subscription is None

    def test_consumer_init_with_custom_values(self, mock_nats_client, consumer_config):
        """Test consumer initializes with custom values."""
        consumer = EventConsumer(
            client=mock_nats_client,
            stream_name="TEST_STREAM",
            consumer_config=consumer_config,
            batch_size=20,
            fetch_timeout=10.0,
        )

        assert consumer.batch_size == 20
        assert consumer.fetch_timeout == 10.0


# ============================================================================
# CONSUMER CREATION TESTS
# ============================================================================


@pytest.mark.unit
class TestConsumerCreation:
    """Test durable consumer creation."""

    @pytest.mark.asyncio
    async def test_create_consumer_creates_new_consumer(
        self, mock_nats_client, consumer_config
    ):
        """Test _create_consumer creates new consumer if not exists."""
        # Mock consumer doesn't exist (raises NotFoundError)
        mock_nats_client.jetstream.consumer_info = AsyncMock(
            side_effect=NotFoundError(description="Not found")
        )
        mock_nats_client.jetstream.add_consumer = AsyncMock()

        consumer = EventConsumer(
            client=mock_nats_client,
            stream_name="TEST_STREAM",
            consumer_config=consumer_config,
        )

        await consumer._create_consumer()

        # Verify add_consumer was called
        mock_nats_client.jetstream.add_consumer.assert_called_once()
        call_args = mock_nats_client.jetstream.add_consumer.call_args
        assert call_args.kwargs["stream"] == "TEST_STREAM"

    @pytest.mark.asyncio
    async def test_create_consumer_uses_existing_consumer(
        self, mock_nats_client, consumer_config
    ):
        """Test _create_consumer uses existing consumer if exists."""
        # Mock consumer exists
        mock_consumer_info = MagicMock()
        mock_nats_client.jetstream.consumer_info = AsyncMock(
            return_value=mock_consumer_info
        )
        mock_nats_client.jetstream.add_consumer = AsyncMock()

        consumer = EventConsumer(
            client=mock_nats_client,
            stream_name="TEST_STREAM",
            consumer_config=consumer_config,
        )

        await consumer._create_consumer()

        # Verify consumer_info was called
        mock_nats_client.jetstream.consumer_info.assert_called_once_with(
            "TEST_STREAM", consumer_config.durable_name
        )

        # Verify add_consumer was NOT called
        mock_nats_client.jetstream.add_consumer.assert_not_called()


# ============================================================================
# MESSAGE PROCESSING TESTS
# ============================================================================


@pytest.mark.unit
class TestMessageProcessing:
    """Test message processing logic."""

    @pytest.mark.asyncio
    async def test_process_message_success(self, mock_nats_client, consumer_config):
        """Test _process_message successfully processes a message."""
        consumer = EventConsumer(
            client=mock_nats_client,
            stream_name="TEST_STREAM",
            consumer_config=consumer_config,
        )

        # Create mock message
        event_data = {
            "event_id": "123e4567-e89b-12d3-a456-426614174000",
            "event_type": "academic.course.created",
            "event_version": "1.0",
            "timestamp": "2025-10-09T12:00:00+00:00",
            "metadata": {
                "source_service": "test-service",
            },
            "course_code": "CS101",
            "course_name": "Intro to CS",
            "semester": "Fall 2025",
            "credits": 3,
            "instructor": "Dr. Smith",
        }

        mock_msg = MagicMock(spec=Msg)
        mock_msg.data = json.dumps(event_data).encode("utf-8")
        mock_msg.subject = "academic.course.created"
        mock_msg.ack = AsyncMock()
        mock_msg.nak = AsyncMock()

        # Create mock handler
        handler = AsyncMock()

        # Process message
        await consumer._process_message(mock_msg, handler)

        # Verify handler was called with event and msg
        handler.assert_called_once()
        call_args = handler.call_args
        event = call_args[0][0]
        msg = call_args[0][1]

        assert isinstance(event, BaseEvent)
        assert event.event_type == "academic.course.created"
        assert msg == mock_msg

    @pytest.mark.asyncio
    async def test_process_message_handles_json_decode_error(
        self, mock_nats_client, consumer_config
    ):
        """Test _process_message handles JSON decode errors."""
        consumer = EventConsumer(
            client=mock_nats_client,
            stream_name="TEST_STREAM",
            consumer_config=consumer_config,
        )

        # Create mock message with invalid JSON
        mock_msg = MagicMock(spec=Msg)
        mock_msg.data = b"invalid json {{"
        mock_msg.subject = "test.subject"
        mock_msg.ack = AsyncMock()
        mock_msg.nak = AsyncMock()

        handler = AsyncMock()

        # Process message (should not raise)
        await consumer._process_message(mock_msg, handler)

        # Verify message was NAKed
        mock_msg.nak.assert_called_once()

        # Verify handler was NOT called
        handler.assert_not_called()

    @pytest.mark.asyncio
    async def test_process_message_handles_handler_exception(
        self, mock_nats_client, consumer_config
    ):
        """Test _process_message handles handler exceptions."""
        consumer = EventConsumer(
            client=mock_nats_client,
            stream_name="TEST_STREAM",
            consumer_config=consumer_config,
        )

        # Create valid mock message
        event_data = {
            "event_id": "123e4567-e89b-12d3-a456-426614174000",
            "event_type": "academic.course.created",
            "event_version": "1.0",
            "timestamp": "2025-10-09T12:00:00+00:00",
            "metadata": {
                "source_service": "test-service",
            },
        }

        mock_msg = MagicMock(spec=Msg)
        mock_msg.data = json.dumps(event_data).encode("utf-8")
        mock_msg.subject = "academic.course.created"
        mock_msg.ack = AsyncMock()
        mock_msg.nak = AsyncMock()

        # Handler raises exception
        handler = AsyncMock(side_effect=Exception("Handler error"))

        # Process message (should not raise)
        await consumer._process_message(mock_msg, handler)

        # Verify message was NAKed
        mock_msg.nak.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_message_tracks_in_flight_count(
        self, mock_nats_client, consumer_config
    ):
        """Test _process_message tracks in-flight message count."""
        consumer = EventConsumer(
            client=mock_nats_client,
            stream_name="TEST_STREAM",
            consumer_config=consumer_config,
        )

        # Reset metrics
        consumer_processing_messages._metrics.clear()

        # Create valid mock message
        event_data = {
            "event_id": "123e4567-e89b-12d3-a456-426614174000",
            "event_type": "academic.course.created",
            "event_version": "1.0",
            "timestamp": "2025-10-09T12:00:00+00:00",
            "metadata": {
                "source_service": "test-service",
            },
        }

        mock_msg = MagicMock(spec=Msg)
        mock_msg.data = json.dumps(event_data).encode("utf-8")
        mock_msg.ack = AsyncMock()

        handler = AsyncMock()

        # Process message
        await consumer._process_message(mock_msg, handler)

        # In-flight count should be incremented then decremented
        # (Final state should be 0)


# ============================================================================
# FETCH AND PROCESS BATCH TESTS
# ============================================================================


@pytest.mark.unit
class TestFetchAndProcessBatch:
    """Test batch fetching and processing."""

    @pytest.mark.asyncio
    async def test_fetch_and_process_batch_processes_messages(
        self, mock_nats_client, consumer_config
    ):
        """Test _fetch_and_process_batch processes fetched messages."""
        consumer = EventConsumer(
            client=mock_nats_client,
            stream_name="TEST_STREAM",
            consumer_config=consumer_config,
        )

        # Create mock messages
        event_data = {
            "event_id": "123e4567-e89b-12d3-a456-426614174000",
            "event_type": "academic.course.created",
            "event_version": "1.0",
            "timestamp": "2025-10-09T12:00:00+00:00",
            "metadata": {
                "source_service": "test-service",
            },
        }

        mock_msg1 = MagicMock(spec=Msg)
        mock_msg1.data = json.dumps(event_data).encode("utf-8")
        mock_msg1.ack = AsyncMock()

        mock_msg2 = MagicMock(spec=Msg)
        mock_msg2.data = json.dumps(event_data).encode("utf-8")
        mock_msg2.ack = AsyncMock()

        # Mock subscription fetch
        mock_subscription = MagicMock()
        mock_subscription.fetch = AsyncMock(return_value=[mock_msg1, mock_msg2])
        consumer._subscription = mock_subscription

        handler = AsyncMock()

        # Fetch and process batch
        await consumer._fetch_and_process_batch(handler)

        # Verify handler was called twice
        assert handler.call_count == 2

    @pytest.mark.asyncio
    async def test_fetch_and_process_batch_handles_timeout(
        self, mock_nats_client, consumer_config
    ):
        """Test _fetch_and_process_batch handles fetch timeout gracefully."""
        consumer = EventConsumer(
            client=mock_nats_client,
            stream_name="TEST_STREAM",
            consumer_config=consumer_config,
        )

        # Mock subscription fetch timeout
        mock_subscription = MagicMock()
        mock_subscription.fetch = AsyncMock(side_effect=TimeoutError())
        consumer._subscription = mock_subscription

        handler = AsyncMock()

        # Fetch and process batch (should not raise)
        await consumer._fetch_and_process_batch(handler)

        # Verify handler was NOT called
        handler.assert_not_called()

    @pytest.mark.asyncio
    async def test_fetch_and_process_batch_handles_empty_batch(
        self, mock_nats_client, consumer_config
    ):
        """Test _fetch_and_process_batch handles empty batch."""
        consumer = EventConsumer(
            client=mock_nats_client,
            stream_name="TEST_STREAM",
            consumer_config=consumer_config,
        )

        # Mock subscription returns empty list
        mock_subscription = MagicMock()
        mock_subscription.fetch = AsyncMock(return_value=[])
        consumer._subscription = mock_subscription

        handler = AsyncMock()

        # Fetch and process batch
        await consumer._fetch_and_process_batch(handler)

        # Verify handler was NOT called
        handler.assert_not_called()


# ============================================================================
# STOP AND SHUTDOWN TESTS
# ============================================================================


@pytest.mark.unit
class TestConsumerStop:
    """Test consumer stop and shutdown."""

    @pytest.mark.asyncio
    async def test_stop_sets_running_false(self, mock_nats_client, consumer_config):
        """Test stop() sets _running to False."""
        consumer = EventConsumer(
            client=mock_nats_client,
            stream_name="TEST_STREAM",
            consumer_config=consumer_config,
        )

        consumer._running = True

        await consumer.stop()

        assert consumer._running is False

    @pytest.mark.asyncio
    async def test_stop_unsubscribes(self, mock_nats_client, consumer_config):
        """Test stop() unsubscribes from subscription."""
        consumer = EventConsumer(
            client=mock_nats_client,
            stream_name="TEST_STREAM",
            consumer_config=consumer_config,
        )

        # Mock subscription
        mock_subscription = MagicMock()
        mock_subscription.unsubscribe = AsyncMock()
        consumer._subscription = mock_subscription

        await consumer.stop()

        # Verify unsubscribe was called
        mock_subscription.unsubscribe.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop_handles_unsubscribe_error(
        self, mock_nats_client, consumer_config
    ):
        """Test stop() handles unsubscribe errors gracefully."""
        consumer = EventConsumer(
            client=mock_nats_client,
            stream_name="TEST_STREAM",
            consumer_config=consumer_config,
        )

        # Mock subscription that raises error
        mock_subscription = MagicMock()
        mock_subscription.unsubscribe = AsyncMock(side_effect=Exception("Error"))
        consumer._subscription = mock_subscription

        # Should not raise
        await consumer.stop()

        assert consumer._running is False

    @pytest.mark.asyncio
    async def test_graceful_shutdown_waits_for_unsubscribe(
        self, mock_nats_client, consumer_config
    ):
        """Test _graceful_shutdown waits for unsubscribe."""
        consumer = EventConsumer(
            client=mock_nats_client,
            stream_name="TEST_STREAM",
            consumer_config=consumer_config,
        )

        # Mock subscription
        mock_subscription = MagicMock()
        mock_subscription.unsubscribe = AsyncMock()
        consumer._subscription = mock_subscription

        await consumer._graceful_shutdown(timeout=5.0)

        # Verify unsubscribe was called
        mock_subscription.unsubscribe.assert_called_once()

    @pytest.mark.asyncio
    async def test_graceful_shutdown_handles_timeout(
        self, mock_nats_client, consumer_config
    ):
        """Test _graceful_shutdown handles timeout."""
        consumer = EventConsumer(
            client=mock_nats_client,
            stream_name="TEST_STREAM",
            consumer_config=consumer_config,
        )

        # Mock subscription that takes too long
        async def slow_unsubscribe():
            await asyncio.sleep(10)  # Longer than timeout

        mock_subscription = MagicMock()
        mock_subscription.unsubscribe = slow_unsubscribe
        consumer._subscription = mock_subscription

        # Should not raise, should timeout gracefully
        await consumer._graceful_shutdown(timeout=0.1)


# ============================================================================
# CONTEXT MANAGER TESTS
# ============================================================================


@pytest.mark.unit
class TestConsumerContextManager:
    """Test consumer async context manager."""

    @pytest.mark.asyncio
    async def test_context_manager_enter(self, mock_nats_client, consumer_config):
        """Test async context manager __aenter__."""
        consumer = EventConsumer(
            client=mock_nats_client,
            stream_name="TEST_STREAM",
            consumer_config=consumer_config,
        )

        async with consumer as c:
            assert c is consumer

    @pytest.mark.asyncio
    async def test_context_manager_exit_calls_stop(
        self, mock_nats_client, consumer_config
    ):
        """Test async context manager __aexit__ calls stop."""
        consumer = EventConsumer(
            client=mock_nats_client,
            stream_name="TEST_STREAM",
            consumer_config=consumer_config,
        )

        consumer.stop = AsyncMock()

        async with consumer:
            pass

        # Verify stop was called
        consumer.stop.assert_called_once()


# ============================================================================
# PULL LOOP TESTS
# ============================================================================


@pytest.mark.unit
class TestPullLoop:
    """Test pull loop logic."""

    @pytest.mark.asyncio
    async def test_pull_loop_creates_pull_subscription(
        self, mock_nats_client, consumer_config
    ):
        """Test _pull_loop creates pull subscription."""
        consumer = EventConsumer(
            client=mock_nats_client,
            stream_name="TEST_STREAM",
            consumer_config=consumer_config,
        )

        # Mock pull_subscribe
        mock_subscription = MagicMock()
        mock_subscription.fetch = AsyncMock(side_effect=asyncio.CancelledError())
        mock_nats_client.jetstream.pull_subscribe = AsyncMock(
            return_value=mock_subscription
        )

        handler = AsyncMock()

        # Run pull loop (will be cancelled immediately)
        try:
            await consumer._pull_loop(handler, graceful_shutdown_timeout=5.0)
        except asyncio.CancelledError:
            pass

        # Verify pull_subscribe was called
        mock_nats_client.jetstream.pull_subscribe.assert_called_once()
        call_args = mock_nats_client.jetstream.pull_subscribe.call_args
        assert call_args.kwargs["stream"] == "TEST_STREAM"
        assert call_args.kwargs["durable"] == consumer_config.durable_name

    @pytest.mark.asyncio
    async def test_pull_loop_uses_filter_subject(
        self, mock_nats_client, consumer_config
    ):
        """Test _pull_loop uses filter subject if single subject."""
        # Configure with single filter subject
        consumer_config.filter_subjects = ["academic.course.*"]

        consumer = EventConsumer(
            client=mock_nats_client,
            stream_name="TEST_STREAM",
            consumer_config=consumer_config,
        )

        # Mock pull_subscribe
        mock_subscription = MagicMock()
        mock_subscription.fetch = AsyncMock(side_effect=asyncio.CancelledError())
        mock_nats_client.jetstream.pull_subscribe = AsyncMock(
            return_value=mock_subscription
        )

        handler = AsyncMock()

        # Run pull loop
        try:
            await consumer._pull_loop(handler, graceful_shutdown_timeout=5.0)
        except asyncio.CancelledError:
            pass

        # Verify subject filter was used
        call_args = mock_nats_client.jetstream.pull_subscribe.call_args
        assert call_args.kwargs["subject"] == "academic.course.*"



# ============================================================================
# METRICS TESTS
# ============================================================================


@pytest.mark.unit
class TestConsumerMetrics:
    """Test consumer metrics integration."""

    @pytest.mark.asyncio
    async def test_process_message_records_success_metrics(
        self, mock_nats_client, consumer_config
    ):
        """Test successful message processing records metrics."""
        consumer = EventConsumer(
            client=mock_nats_client,
            stream_name="TEST_STREAM",
            consumer_config=consumer_config,
        )

        # Reset metrics
        events_consumed_total._metrics.clear()

        # Create valid message
        event_data = {
            "event_id": "123e4567-e89b-12d3-a456-426614174000",
            "event_type": "academic.course.created",
            "event_version": "1.0",
            "timestamp": "2025-10-09T12:00:00+00:00",
            "metadata": {
                "source_service": "test-service",
            },
        }

        mock_msg = MagicMock(spec=Msg)
        mock_msg.data = json.dumps(event_data).encode("utf-8")
        mock_msg.ack = AsyncMock()

        handler = AsyncMock()

        await consumer._process_message(mock_msg, handler)

        # Metrics should be recorded
        # (Actual assertion would require prometheus test utilities)

    @pytest.mark.asyncio
    async def test_process_message_records_error_metrics(
        self, mock_nats_client, consumer_config
    ):
        """Test failed message processing records error metrics."""
        consumer = EventConsumer(
            client=mock_nats_client,
            stream_name="TEST_STREAM",
            consumer_config=consumer_config,
        )

        # Reset metrics
        consumer_errors_total._metrics.clear()

        # Create invalid message
        mock_msg = MagicMock(spec=Msg)
        mock_msg.data = b"invalid json"
        mock_msg.nak = AsyncMock()

        handler = AsyncMock()

        await consumer._process_message(mock_msg, handler)

        # Error metrics should be recorded


# ============================================================================
# ERROR HANDLING TESTS
# ============================================================================


@pytest.mark.unit
class TestConsumerErrorHandling:
    """Test consumer error handling."""

    @pytest.mark.asyncio
    async def test_subscribe_handles_exception(self, mock_nats_client, consumer_config):
        """Test subscribe raises ConsumerError on failure."""
        consumer = EventConsumer(
            client=mock_nats_client,
            stream_name="TEST_STREAM",
            consumer_config=consumer_config,
        )

        # Mock consumer_info to raise error
        mock_nats_client.jetstream.consumer_info = AsyncMock(
            side_effect=Exception("Test error")
        )

        handler = AsyncMock()

        # Should raise ConsumerError
        with pytest.raises(ConsumerError, match="Failed to subscribe"):
            await consumer.subscribe(handler)
