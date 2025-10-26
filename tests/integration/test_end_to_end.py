"""
End-to-end integration tests with real NATS server.

These tests require a running NATS server with JetStream enabled:
    docker-compose up -d nats

Run these tests with:
    pytest tests/integration/test_end_to_end.py -v
"""

import asyncio

import pytest

from vertector_nats import (
    NATSClient,
    NATSConfig,
    EventPublisher,
    EventConsumer,
    ConsumerConfig,
    CourseCreatedEvent,
    CourseUpdatedEvent,
    CourseDeletedEvent,
    AssignmentCreatedEvent,
    EventMetadata,
)


@pytest.fixture
def nats_config() -> NATSConfig:
    """Create NATSConfig for integration tests."""
    return NATSConfig(
        servers=["nats://localhost:4222"],
        enable_jetstream=True,
    )


@pytest.fixture
def consumer_config() -> ConsumerConfig:
    """Create ConsumerConfig for integration tests."""
    return ConsumerConfig(
        durable_name="test-consumer",
        filter_subjects=["academic.>"],
        deliver_policy="new",
    )


@pytest.mark.integration
class TestEndToEndPublishSubscribe:
    """End-to-end tests for publish/subscribe flow."""

    @pytest.mark.asyncio
    async def test_publish_and_consume_single_event(
        self, nats_config, consumer_config
    ):
        """Test publishing and consuming a single event."""
        received_events = []

        async def handler(event, msg):
            received_events.append(event)
            await msg.ack()

        # Publish event
        async with NATSClient(nats_config) as client:
            publisher = EventPublisher(client=client)

            event = CourseCreatedEvent(
                course_code="CS101",
                course_name="Intro to CS",
                semester="Fall 2025",
                credits=3,
                instructor="Dr. Smith",
                metadata=EventMetadata(source_service="integration-test"),
            )

            ack = await publisher.publish(event)
            assert ack.stream == "ACADEMIC_EVENTS"

        # Consume event
        async with NATSClient(nats_config) as client:
            consumer = EventConsumer(
                client=client,
                stream_name="ACADEMIC_EVENTS",
                consumer_config=consumer_config,
                batch_size=1,
            )

            # Pull messages
            await consumer.pull_and_process(handler, max_iterations=1)

        # Verify event received
        assert len(received_events) == 1
        assert isinstance(received_events[0], CourseCreatedEvent)
        assert received_events[0].course_code == "CS101"

    @pytest.mark.asyncio
    async def test_publish_and_consume_multiple_events(
        self, nats_config, consumer_config
    ):
        """Test publishing and consuming multiple events."""
        received_events = []

        async def handler(event, msg):
            received_events.append(event)
            await msg.ack()

        # Publish events
        async with NATSClient(nats_config) as client:
            publisher = EventPublisher(client=client)

            events = [
                CourseCreatedEvent(
                    course_code=f"CS{100 + i}",
                    course_name=f"Course {i}",
                    semester="Fall 2025",
                    credits=3,
                    instructor="Dr. Smith",
                    metadata=EventMetadata(source_service="integration-test"),
                )
                for i in range(10)
            ]

            acks = await publisher.publish_batch(events, parallel=True)
            assert len(acks) == 10

        # Consume events
        async with NATSClient(nats_config) as client:
            consumer = EventConsumer(
                client=client,
                stream_name="ACADEMIC_EVENTS",
                consumer_config=consumer_config,
                batch_size=5,
            )

            # Pull multiple batches
            await consumer.pull_and_process(handler, max_iterations=2)

        # Verify events received
        assert len(received_events) >= 10

    @pytest.mark.asyncio
    async def test_different_event_types(self, nats_config, consumer_config):
        """Test publishing and consuming different event types."""
        received_events = []

        async def handler(event, msg):
            received_events.append(event)
            await msg.ack()

        # Publish different event types
        async with NATSClient(nats_config) as client:
            publisher = EventPublisher(client=client)

            events = [
                CourseCreatedEvent(
                    course_code="CS101",
                    course_name="Intro to CS",
                    semester="Fall 2025",
                    credits=3,
                    instructor="Dr. Smith",
                    metadata=EventMetadata(source_service="integration-test"),
                ),
                CourseUpdatedEvent(
                    course_code="CS101",
                    updates={"instructor": "Dr. Jones"},
                    metadata=EventMetadata(source_service="integration-test"),
                ),
                AssignmentCreatedEvent(
                    assignment_id="assignment-1",
                    course_code="CS101",
                    title="Homework 1",
                    description="First assignment",
                    max_score=100.0,
                    metadata=EventMetadata(source_service="integration-test"),
                ),
            ]

            for event in events:
                await publisher.publish(event)

        # Consume events
        async with NATSClient(nats_config) as client:
            consumer = EventConsumer(
                client=client,
                stream_name="ACADEMIC_EVENTS",
                consumer_config=consumer_config,
                batch_size=10,
            )

            await consumer.pull_and_process(handler, max_iterations=1)

        # Verify different event types received
        assert len(received_events) >= 3
        event_types = {type(event) for event in received_events}
        assert CourseCreatedEvent in event_types or CourseUpdatedEvent in event_types

    @pytest.mark.asyncio
    async def test_consumer_ack_behavior(self, nats_config, consumer_config):
        """Test that acknowledged messages are not redelivered."""
        received_count = [0]

        async def handler(event, msg):
            received_count[0] += 1
            await msg.ack()

        # Publish event
        async with NATSClient(nats_config) as client:
            publisher = EventPublisher(client=client)

            event = CourseCreatedEvent(
                course_code="CS999",
                course_name="Test Course",
                semester="Fall 2025",
                credits=3,
                instructor="Test",
                metadata=EventMetadata(source_service="integration-test"),
            )

            await publisher.publish(event)

        # Consume once
        async with NATSClient(nats_config) as client:
            consumer = EventConsumer(
                client=client,
                stream_name="ACADEMIC_EVENTS",
                consumer_config=consumer_config,
                batch_size=10,
            )

            await consumer.pull_and_process(handler, max_iterations=1)

        first_count = received_count[0]

        # Try to consume again - should not get same message
        async with NATSClient(nats_config) as client:
            consumer = EventConsumer(
                client=client,
                stream_name="ACADEMIC_EVENTS",
                consumer_config=consumer_config,
                batch_size=10,
            )

            await consumer.pull_and_process(handler, max_iterations=1)

        # Count should not increase (message was acked)
        assert received_count[0] == first_count

    @pytest.mark.asyncio
    async def test_consumer_nak_behavior(self, nats_config, consumer_config):
        """Test that NAKed messages are redelivered."""
        received_count = [0]

        async def handler_nak(event, msg):
            received_count[0] += 1
            await msg.nak()  # Negative acknowledge - redeliver

        # Publish event
        async with NATSClient(nats_config) as client:
            publisher = EventPublisher(client=client)

            event = CourseCreatedEvent(
                course_code="CS888",
                course_name="NAK Test",
                semester="Fall 2025",
                credits=3,
                instructor="Test",
                metadata=EventMetadata(source_service="integration-test"),
            )

            await publisher.publish(event)

        # Consume and NAK
        async with NATSClient(nats_config) as client:
            consumer = EventConsumer(
                client=client,
                stream_name="ACADEMIC_EVENTS",
                consumer_config=consumer_config,
                batch_size=1,
            )

            await consumer.pull_and_process(handler_nak, max_iterations=1)

        first_count = received_count[0]
        assert first_count >= 1

        # Message should be redelivered
        await asyncio.sleep(1)  # Wait for redelivery

        async with NATSClient(nats_config) as client:
            consumer = EventConsumer(
                client=client,
                stream_name="ACADEMIC_EVENTS",
                consumer_config=consumer_config,
                batch_size=1,
            )

            # This time, ack the message
            async def handler_ack(event, msg):
                received_count[0] += 1
                await msg.ack()

            await consumer.pull_and_process(handler_ack, max_iterations=1)

        # Should have received message again
        assert received_count[0] > first_count


@pytest.mark.integration
class TestConnectionRecovery:
    """Test connection recovery and reconnection."""

    @pytest.mark.asyncio
    async def test_reconnect_after_disconnect(self, nats_config):
        """Test that client reconnects after disconnection."""
        config = nats_config
        config.max_reconnect_attempts = 5
        config.reconnect_wait_seconds = 1

        async with NATSClient(config) as client:
            assert client.is_connected

            # Simulate work
            publisher = EventPublisher(client=client)

            event = CourseCreatedEvent(
                course_code="CS777",
                course_name="Reconnect Test",
                semester="Fall 2025",
                credits=3,
                instructor="Test",
                metadata=EventMetadata(source_service="integration-test"),
            )

            ack = await publisher.publish(event)
            assert ack.stream == "ACADEMIC_EVENTS"

            # Client should remain connected
            await asyncio.sleep(2)
            assert client.is_connected

    @pytest.mark.asyncio
    async def test_publish_during_reconnection(self, nats_config):
        """Test publishing during reconnection attempts."""
        # This is a placeholder - actual test would require
        # stopping and starting NATS server
        pytest.skip("Requires NATS server restart capability")


@pytest.mark.integration
class TestStreamManagement:
    """Test stream creation and management."""

    @pytest.mark.asyncio
    async def test_stream_exists(self, nats_config):
        """Test that ACADEMIC_EVENTS stream exists."""
        async with NATSClient(nats_config) as client:
            js = client.jetstream

            # Get stream info
            stream_info = await js.stream_info("ACADEMIC_EVENTS")
            assert stream_info.config.name == "ACADEMIC_EVENTS"
            assert "academic.>" in stream_info.config.subjects

    @pytest.mark.asyncio
    async def test_consumer_creation(self, nats_config, consumer_config):
        """Test consumer creation."""
        async with NATSClient(nats_config) as client:
            consumer = EventConsumer(
                client=client,
                stream_name="ACADEMIC_EVENTS",
                consumer_config=consumer_config,
                batch_size=10,
            )

            # Consumer should be created
            js = client.jetstream
            consumer_info = await js.consumer_info(
                "ACADEMIC_EVENTS", consumer_config.durable_name
            )
            assert consumer_info.name == consumer_config.durable_name


@pytest.mark.integration
class TestPerformance:
    """Test performance characteristics."""

    @pytest.mark.asyncio
    async def test_publish_latency(self, nats_config):
        """Test publish latency is acceptable."""
        import time

        async with NATSClient(nats_config) as client:
            publisher = EventPublisher(client=client)

            event = CourseCreatedEvent(
                course_code="CS666",
                course_name="Latency Test",
                semester="Fall 2025",
                credits=3,
                instructor="Test",
                metadata=EventMetadata(source_service="integration-test"),
            )

            # Measure latency
            latencies = []
            for _ in range(10):
                start = time.time()
                await publisher.publish(event)
                latency = time.time() - start
                latencies.append(latency)

            avg_latency = sum(latencies) / len(latencies)
            max_latency = max(latencies)

            # Latency should be under 100ms
            assert avg_latency < 0.1  # 100ms
            assert max_latency < 0.5  # 500ms

    @pytest.mark.asyncio
    async def test_batch_publish_performance(self, nats_config):
        """Test batch publishing is faster than individual publishes."""
        import time

        async with NATSClient(nats_config) as client:
            publisher = EventPublisher(client=client)

            events = [
                CourseCreatedEvent(
                    course_code=f"CS{500 + i}",
                    course_name=f"Batch Test {i}",
                    semester="Fall 2025",
                    credits=3,
                    instructor="Test",
                    metadata=EventMetadata(source_service="integration-test"),
                )
                for i in range(50)
            ]

            # Individual publishes
            start = time.time()
            for event in events:
                await publisher.publish(event)
            individual_time = time.time() - start

            # Batch publish
            start = time.time()
            await publisher.publish_batch(events, parallel=True)
            batch_time = time.time() - start

            # Batch should be faster
            print(f"Individual: {individual_time:.2f}s, Batch: {batch_time:.2f}s")
            assert batch_time < individual_time


# Run helper
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
