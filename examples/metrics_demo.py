"""Demo: Publishing events and viewing metrics.

This demo shows how metrics are collected during publish operations.
"""

import asyncio
from datetime import datetime

from vertector_nats import (
    AssignmentCreatedEvent,
    CourseCreatedEvent,
    EventMetadata,
    EventPublisher,
    ExamCreatedEvent,
    NATSClient,
    NATSConfig,
)
from vertector_nats.metrics import get_metrics


async def main() -> None:
    """Publish events and display metrics."""

    print("\n" + "="*70)
    print("📊 NATS JETSTREAM METRICS DEMO")
    print("="*70)

    config = NATSConfig(
        servers=["nats://localhost:4222"],
        client_name="metrics-demo",
    )

    async with NATSClient(config) as client:
        publisher = EventPublisher(client)

        print("\n1️⃣  Publishing demo events...")
        print("-" * 70)

        # Publish multiple events of different types
        events = [
            CourseCreatedEvent(
                course_code="DEMO101",
                course_name="Demo Course",
                semester="Fall 2025",
                credits=3,
                instructor="Dr. Demo",
                metadata=EventMetadata(source_service="metrics-demo"),
            ),
            AssignmentCreatedEvent(
                assignment_id="demo_hw1",
                course_code="DEMO101",
                title="Demo Assignment",
                due_date=datetime(2025, 10, 15, 23, 59),
                status="not started",
                metadata=EventMetadata(source_service="metrics-demo"),
            ),
            ExamCreatedEvent(
                exam_id="demo_exam1",
                course_code="DEMO101",
                exam_name="Demo Exam",
                exam_type="midterm",
                exam_date=datetime(2025, 11, 1, 9, 0),
                metadata=EventMetadata(source_service="metrics-demo"),
            ),
        ]

        for i, event in enumerate(events, 1):
            ack = await publisher.publish(event)
            print(f"   {i}. ✓ Published {event.event_type} to seq {ack.seq}")

        # Publish a batch
        print("\n   Publishing batch of 3 more events...")
        more_events = [
            CourseCreatedEvent(
                course_code=f"BATCH{i}",
                course_name=f"Batch Course {i}",
                semester="Fall 2025",
                credits=3,
                instructor="Dr. Batch",
                metadata=EventMetadata(source_service="metrics-demo"),
            )
            for i in range(1, 4)
        ]

        acks = await publisher.publish_batch(more_events, parallel=True)
        print(f"   ✓ Published {len(acks)} events in batch")

        print("\n2️⃣  Metrics collected:")
        print("-" * 70)

        # Get and display metrics
        metrics_data, content_type = get_metrics()

        # Parse and display key metrics
        metrics_text = metrics_data.decode('utf-8')

        print("\n📈 Publishing Metrics:")
        for line in metrics_text.split('\n'):
            if 'nats_events_published_total' in line and not line.startswith('#'):
                print(f"   {line}")
            elif 'nats_publish_duration_seconds' in line and 'count' in line:
                print(f"   {line}")
            elif 'nats_event_payload_size_bytes' in line and 'count' in line:
                print(f"   {line}")

        print("\n📊 Full metrics available at /metrics endpoint")
        print(f"   Content-Type: {content_type}")
        print(f"   Total metrics size: {len(metrics_data)} bytes")

        print("\n3️⃣  Example Prometheus queries:")
        print("-" * 70)
        print("""
   # Publish success rate (last 5 minutes):
   rate(nats_events_published_total{status="success"}[5m])
   /
   rate(nats_events_published_total[5m])

   # Publish latency (p95):
   histogram_quantile(0.95,
     rate(nats_publish_duration_seconds_bucket[5m])
   )

   # Events by type:
   sum by (event_type) (nats_events_published_total)
        """)

    print("\n" + "="*70)
    print("✓ Metrics demo complete!")
    print("="*70 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
