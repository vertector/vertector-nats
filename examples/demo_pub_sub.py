"""Demo: Publish and consume events simultaneously.

This demo shows the complete publish-subscribe flow.
"""

import asyncio
from datetime import datetime

from nats.aio.msg import Msg

from vertector_nats import (
    AssignmentCreatedEvent,
    BaseEvent,
    ConsumerConfig,
    CourseCreatedEvent,
    EventConsumer,
    EventMetadata,
    EventPublisher,
    ExamCreatedEvent,
    NATSClient,
    NATSConfig,
)


async def handle_event(event: BaseEvent, msg: Msg) -> None:
    """Handle incoming events."""
    try:
        print(f"\n{'='*60}")
        print(f"📨 CONSUMED: {event.event_type}")
        print(f"   Event ID: {event.event_id}")

        # Get event-specific details
        event_type_str = str(event.event_type.value) if hasattr(event.event_type, 'value') else str(event.event_type)

        if "course" in event_type_str:
            print(f"   📚 Course: {getattr(event, 'course_code', 'N/A')} - {getattr(event, 'course_name', 'N/A')}")
        elif "assignment" in event_type_str:
            print(f"   📄 Assignment: {getattr(event, 'title', 'N/A')}")
        elif "exam" in event_type_str:
            print(f"   📝 Exam: {getattr(event, 'exam_name', 'N/A')}")

        await msg.ack()
        print("   ✓ Acknowledged")

    except Exception as e:
        print(f"   ✗ Error: {e}")
        await msg.nak()


async def publish_demo_events(client: NATSClient) -> None:
    """Publish demo events."""
    publisher = EventPublisher(client)

    print("\n" + "="*60)
    print("📤 PUBLISHING DEMO EVENTS")
    print("="*60)

    events = [
        CourseCreatedEvent(
            course_code="CS101",
            course_name="Introduction to Computer Science",
            semester="Fall 2025",
            credits=3,
            instructor="Dr. Jane Smith",
            metadata=EventMetadata(source_service="demo-publisher"),
        ),
        AssignmentCreatedEvent(
            assignment_id="hw1",
            course_code="CS101",
            title="Homework 1: Python Basics",
            due_date=datetime(2025, 10, 15, 23, 59),
            status="not started",
            metadata=EventMetadata(source_service="demo-publisher"),
        ),
        ExamCreatedEvent(
            exam_id="midterm1",
            course_code="CS101",
            exam_name="Midterm Exam",
            exam_type="midterm",
            exam_date=datetime(2025, 11, 1, 9, 0),
            metadata=EventMetadata(source_service="demo-publisher"),
        ),
    ]

    for i, event in enumerate(events, 1):
        print(f"\n{i}. Publishing: {event.event_type}")
        ack = await publisher.publish(event)
        print(f"   ✓ Published to stream {ack.stream}, seq {ack.seq}")
        await asyncio.sleep(0.5)  # Small delay to see events clearly

    print(f"\n✓ Published {len(events)} events")


async def consume_demo_events(client: NATSClient) -> None:
    """Consume demo events for 5 seconds."""
    consumer_config = ConsumerConfig(
        durable_name="demo-consumer",
        filter_subjects=["academic.*"],
        ack_policy="explicit",
    )

    consumer = EventConsumer(
        client=client,
        stream_name="ACADEMIC_EVENTS",
        consumer_config=consumer_config,
        batch_size=10,
        fetch_timeout=2.0,
    )

    print("\n" + "="*60)
    print("📥 CONSUMING EVENTS")
    print("="*60)
    print("Listening for 5 seconds...\n")

    # Start consuming in background
    consume_task = asyncio.create_task(consumer.subscribe(handle_event))

    # Let it run for 5 seconds
    await asyncio.sleep(5)

    # Stop consumer
    await consumer.stop()

    try:
        await asyncio.wait_for(consume_task, timeout=2.0)
    except (asyncio.TimeoutError, asyncio.CancelledError):
        pass

    print("\n✓ Consumer stopped")


async def main() -> None:
    """Run the demo."""
    config = NATSConfig(
        servers=["nats://localhost:4222"],
        client_name="demo-client",
    )

    print("\n" + "="*60)
    print("🚀 NATS JETSTREAM PUBLISH-SUBSCRIBE DEMO")
    print("="*60)

    async with NATSClient(config) as client:
        # First publish events
        await publish_demo_events(client)

        # Small delay
        await asyncio.sleep(1)

        # Then consume them
        await consume_demo_events(client)

    print("\n" + "="*60)
    print("✓ Demo complete!")
    print("="*60 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
