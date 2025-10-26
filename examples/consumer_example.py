"""Example: Consuming academic events from NATS JetStream.

This example demonstrates how to integrate NATS event consumption
into your note-taking service.
"""

import asyncio

from nats.aio.msg import Msg

from vertector_nats import (
    BaseEvent,
    ConsumerConfig,
    EventConsumer,
    NATSClient,
    NATSConfig,
)


async def handle_academic_event(event: BaseEvent, msg: Msg) -> None:
    """Handle incoming academic events.

    Args:
        event: Deserialized event object
        msg: Raw NATS message (for ack/nak)
    """
    try:
        print(f"\n{'='*60}")
        print(f"📨 Received Event: {event.event_type}")
        print(f"   Event ID: {event.event_id}")
        print(f"   Timestamp: {event.timestamp}")
        print(f"   Source: {event.metadata.source_service}")

        # Convert event_type to string for comparison (handles both Enum and str)
        event_type_str = str(event.event_type.value) if hasattr(event.event_type, 'value') else str(event.event_type)

        # Route events to appropriate handlers based on type
        if event_type_str.startswith("academic.course."):
            await handle_course_event(event)

        elif event_type_str.startswith("academic.assignment."):
            await handle_assignment_event(event)

        elif event_type_str.startswith("academic.exam."):
            await handle_exam_event(event)

        elif event_type_str.startswith("academic.study."):
            await handle_study_event(event)

        else:
            print(f"   ⚠️  Unhandled event type: {event_type_str}")

        # Acknowledge successful processing
        await msg.ack()
        print("   ✓ Event processed successfully")

    except Exception as e:
        print(f"   ✗ Error processing event: {e}")
        # Negative acknowledgment (will be redelivered)
        await msg.nak()


async def handle_course_event(event: BaseEvent) -> None:
    """Handle course-related events."""
    event_type_str = str(event.event_type.value) if hasattr(event.event_type, 'value') else str(event.event_type)

    if event_type_str == "academic.course.created":
        print(f"   📚 New course created: {getattr(event, 'course_code', 'N/A')}")
        print(f"      Course: {getattr(event, 'course_name', 'N/A')}")
        print(f"      Instructor: {getattr(event, 'instructor', 'N/A')}")

        # In note-taking service, you might:
        # - Create a course notebook
        # - Set up note templates
        # - Initialize course-specific tags
        print("      → Creating course notebook...")

    elif event_type_str == "academic.course.updated":
        print(f"   📝 Course updated: {getattr(event, 'course_code', 'N/A')}")
        # Update notebook metadata

    elif event_type_str == "academic.course.deleted":
        print(f"   🗑️  Course deleted: {getattr(event, 'course_code', 'N/A')}")
        # Archive or delete associated notes


async def handle_assignment_event(event: BaseEvent) -> None:
    """Handle assignment-related events."""
    event_type_str = str(event.event_type.value) if hasattr(event.event_type, 'value') else str(event.event_type)

    if event_type_str == "academic.assignment.created":
        print(f"   📄 New assignment: {getattr(event, 'title', 'N/A')}")
        print(f"      Course: {getattr(event, 'course_code', 'N/A')}")
        print(f"      Due: {getattr(event, 'due_date', 'N/A')}")

        # In note-taking service:
        # - Create assignment note section
        # - Link to lecture notes
        # - Set up reminders
        print("      → Linking assignment to lecture notes...")

    elif event_type_str == "academic.assignment.updated":
        print(f"   ✏️  Assignment updated: {getattr(event, 'assignment_id', 'N/A')}")

    elif event_type_str == "academic.assignment.deleted":
        print(f"   🗑️  Assignment deleted: {getattr(event, 'assignment_id', 'N/A')}")


async def handle_exam_event(event: BaseEvent) -> None:
    """Handle exam-related events."""
    event_type_str = str(event.event_type.value) if hasattr(event.event_type, 'value') else str(event.event_type)

    if event_type_str == "academic.exam.created":
        print(f"   📝 New exam: {getattr(event, 'exam_name', 'N/A')}")
        print(f"      Type: {getattr(event, 'exam_type', 'N/A')}")
        print(f"      Date: {getattr(event, 'exam_date', 'N/A')}")

        # In note-taking service:
        # - Create exam prep section
        # - Aggregate relevant notes
        # - Generate study guide
        print("      → Creating exam prep section...")


async def handle_study_event(event: BaseEvent) -> None:
    """Handle study todo events."""
    event_type_str = str(event.event_type.value) if hasattr(event.event_type, 'value') else str(event.event_type)

    if event_type_str == "academic.study.created":
        print(f"   ✅ New study task: {getattr(event, 'topic', 'N/A')}")
        print(f"      Priority: {getattr(event, 'priority', 'N/A')}/5")

        # Link study tasks to notes
        print("      → Linking to related notes...")


async def main() -> None:
    """Start consuming events from NATS JetStream."""

    # Load configuration
    config = NATSConfig(
        servers=["nats://localhost:4222"],
        client_name="notes-service-consumer",
    )

    # Create NATS client and connect
    async with NATSClient(config) as client:
        # Configure consumer
        # NOTE: With "interest" retention, we can use filters for multiple independent consumers
        consumer_config = ConsumerConfig(
            durable_name="notes-service-consumer",
            filter_subjects=[
                "academic.course.*",
                "academic.assignment.*",
                "academic.exam.*",
                "academic.study.*",
            ],
            ack_policy="explicit",
            max_deliver=3,  # Retry failed messages up to 3 times
        )

        # Create consumer
        consumer = EventConsumer(
            client=client,
            stream_name="ACADEMIC_EVENTS",
            consumer_config=consumer_config,
            batch_size=10,
            fetch_timeout=5.0,
        )

        print("🚀 Note-taking service consumer started")
        print(f"📡 Listening for events on stream: ACADEMIC_EVENTS")
        print(f"💼 Consumer: {consumer_config.durable_name}")
        print(f"🔍 Filtering subjects: {consumer_config.filter_subjects}")
        print("\nWaiting for events... (Press Ctrl+C to stop)\n")

        try:
            # Start consuming (runs indefinitely)
            await consumer.subscribe(handle_academic_event)

        except KeyboardInterrupt:
            print("\n\n⏹️  Shutting down consumer...")
            await consumer.stop()
            print("✓ Consumer stopped successfully")


if __name__ == "__main__":
    asyncio.run(main())
