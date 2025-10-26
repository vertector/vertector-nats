"""Example: Publishing academic events to NATS JetStream.

This example demonstrates how to integrate NATS event publishing
into your academic schedule management service.
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


async def main() -> None:
    """Publish sample academic events."""

    # Load configuration from environment or use defaults
    config = NATSConfig(
        servers=["nats://localhost:4222"],
        client_name="schedule-service-publisher",
    )

    # Create NATS client and connect
    async with NATSClient(config) as client:
        # Create event publisher
        publisher = EventPublisher(client)

        # Example 1: Publish a single course created event
        print("Publishing course created event...")

        course_event = CourseCreatedEvent(
            course_id="CS101-Fall2025",
            title="Introduction to Computer Science",
            code="CS",
            number="101",
            term="Fall 2025",
            credits=3,
            description="Introduction to programming and computer science fundamentals",
            instructor_name="Dr. Jane Smith",
            instructor_email="jsmith@university.edu",
            component_type=["LEC", "LAB"],
            prerequisites=["MATH100-Summer2025"],
            grading_options=["Letter", "S/NC"],
            learning_objectives=[
                "Understand basic programming concepts",
                "Write simple programs in Python"
            ],
            metadata=EventMetadata(
                source_service="schedule-service",
                user_id="student_123",
                correlation_id="req_abc123",
            ),
        )

        ack = await publisher.publish(course_event)
        print(f"✓ Published to stream {ack.stream}, sequence {ack.seq}")

        # Example 2: Publish an assignment created event
        print("\nPublishing assignment created event...")

        assignment_event = AssignmentCreatedEvent(
            assignment_id="CS101-A1",
            title="Homework 1: Variables and Data Types",
            course_id="CS101-Fall2025",
            type="Programming",
            description="Complete problems 1-10 from textbook. Focus on understanding variable types and basic operations.",
            due_date=datetime(2025, 10, 15, 23, 59),
            points_possible=100,
            weight=0.10,  # 10% of final grade
            submission_status="Not Started",
            estimated_hours=5,
            instructions_url="https://cs101.university.edu/assignments/hw1",
            metadata=EventMetadata(
                source_service="schedule-service",
                user_id="student_123",
            ),
        )

        ack = await publisher.publish(assignment_event)
        print(f"✓ Published to stream {ack.stream}, sequence {ack.seq}")

        # Example 3: Batch publish multiple events
        print("\nPublishing batch of events...")

        events = [
            ExamCreatedEvent(
                exam_id="CS101-MIDTERM",
                title="Midterm Exam",
                course_id="CS101-Fall2025",
                exam_type="Midterm",
                date=datetime(2025, 11, 1, 9, 0),
                duration_minutes=120,
                location="Building A, Room 101",
                points_possible=200,
                weight=0.25,  # 25% of final grade
                topics_covered=["variables", "functions", "loops", "data structures"],
                format="Mixed",
                open_book=False,
                allowed_materials=["Calculator"],
                metadata=EventMetadata(source_service="schedule-service"),
            ),
            CourseCreatedEvent(
                course_id="MATH201-Fall2025",
                title="Calculus II",
                code="MATH",
                number="201",
                term="Fall 2025",
                credits=4,
                description="Continuation of calculus covering integration techniques, series, and multivariable calculus",
                instructor_name="Prof. John Doe",
                instructor_email="jdoe@university.edu",
                component_type=["LEC", "DIS"],
                prerequisites=["MATH101-Summer2025"],
                grading_options=["Letter"],
                learning_objectives=[
                    "Master integration techniques",
                    "Understand infinite series",
                    "Apply calculus to real-world problems"
                ],
                metadata=EventMetadata(source_service="schedule-service"),
            ),
        ]

        acks = await publisher.publish_batch(events, parallel=True)
        print(f"✓ Published {len(acks)} events in batch")

        print("\n✓ All events published successfully!")


if __name__ == "__main__":
    asyncio.run(main())
