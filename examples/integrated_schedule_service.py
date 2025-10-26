"""Integrated Academic Schedule Service with ScyllaDB + NATS.

This demonstrates the complete workflow:
1. Accept course/assignment data
2. Persist to ScyllaDB store
3. Publish event to NATS JetStream
4. Other services consume the event
"""

import asyncio
from datetime import datetime
from pathlib import Path
from typing import Any

# Add parent directory to path to import vertector_nats
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from vertector_nats import (
    AssignmentCreatedEvent,
    CourseCreatedEvent,
    EventMetadata,
    EventPublisher,
    ExamCreatedEvent,
    NATSClient,
    NATSConfig,
    StudyTodoCreatedEvent,
)


class AcademicScheduleService:
    """Academic schedule management service with ScyllaDB + NATS."""

    def __init__(self, scylla_store, nats_publisher: EventPublisher):
        """Initialize with ScyllaDB store and NATS publisher.

        Args:
            scylla_store: AsyncScyllaDBStore instance
            nats_publisher: EventPublisher instance
        """
        self.store = scylla_store
        self.publisher = nats_publisher

    async def create_course(self, course_data: dict[str, Any], user_id: str) -> str:
        """Create a new course - persist to DB and publish event.

        Args:
            course_data: Course information
            user_id: ID of user creating the course

        Returns:
            course_code: The created course code
        """
        course_code = course_data["course_code"]

        print(f"\n📚 Creating course: {course_code}")

        # 1. Persist to ScyllaDB
        print(f"   → Saving to ScyllaDB...")
        await self.store.aput(
            namespace=("courses",),
            key=course_code,
            value=course_data,
        )
        print(f"   ✓ Saved to ScyllaDB: courses/{course_code}")

        # 2. Publish event to NATS
        print(f"   → Publishing event to NATS...")
        event = CourseCreatedEvent(
            course_code=course_data["course_code"],
            course_name=course_data["course_name"],
            semester=course_data["semester"],
            credits=course_data["credits"],
            instructor=course_data.get("instructor", "TBD"),
            difficulty_level=course_data.get("difficulty_level"),
            prerequisites=course_data.get("prerequisites", []),
            metadata=EventMetadata(
                source_service="schedule-service",
                user_id=user_id,
                correlation_id=f"course-create-{course_code}",
            ),
        )

        ack = await self.publisher.publish(event)
        print(f"   ✓ Published to NATS: stream={ack.stream}, seq={ack.seq}")

        return course_code

    async def create_assignment(
        self, assignment_data: dict[str, Any], user_id: str
    ) -> str:
        """Create a new assignment - persist to DB and publish event."""
        assignment_id = assignment_data["assignment_id"]
        course_code = assignment_data["course_code"]

        print(f"\n📝 Creating assignment: {assignment_id}")

        # 1. Persist to ScyllaDB (convert datetime to ISO format)
        print(f"   → Saving to ScyllaDB...")
        db_data = assignment_data.copy()
        if isinstance(db_data.get("due_date"), datetime):
            db_data["due_date"] = db_data["due_date"].isoformat()
        await self.store.aput(
            namespace=("assignments", course_code),
            key=assignment_id,
            value=db_data,
        )
        print(f"   ✓ Saved to ScyllaDB: assignments/{course_code}/{assignment_id}")

        # 2. Publish event to NATS
        print(f"   → Publishing event to NATS...")
        event = AssignmentCreatedEvent(
            assignment_id=assignment_id,
            course_code=course_code,
            title=assignment_data["title"],
            due_date=assignment_data["due_date"],
            status=assignment_data.get("status", "not started"),
            description=assignment_data.get("description"),
            estimated_hours=assignment_data.get("estimated_hours"),
            metadata=EventMetadata(
                source_service="schedule-service",
                user_id=user_id,
                correlation_id=f"assignment-create-{assignment_id}",
            ),
        )

        ack = await self.publisher.publish(event)
        print(f"   ✓ Published to NATS: stream={ack.stream}, seq={ack.seq}")

        return assignment_id

    async def create_exam(self, exam_data: dict[str, Any], user_id: str) -> str:
        """Create a new exam - persist to DB and publish event."""
        exam_id = exam_data["exam_id"]
        course_code = exam_data["course_code"]

        print(f"\n📝 Creating exam: {exam_id}")

        # 1. Persist to ScyllaDB (convert datetime to ISO format)
        print(f"   → Saving to ScyllaDB...")
        db_data = exam_data.copy()
        if isinstance(db_data.get("exam_date"), datetime):
            db_data["exam_date"] = db_data["exam_date"].isoformat()
        await self.store.aput(
            namespace=("exams", course_code),
            key=exam_id,
            value=db_data,
        )
        print(f"   ✓ Saved to ScyllaDB: exams/{course_code}/{exam_id}")

        # 2. Publish event to NATS
        print(f"   → Publishing event to NATS...")
        event = ExamCreatedEvent(
            exam_id=exam_id,
            course_code=course_code,
            exam_name=exam_data["exam_name"],
            exam_type=exam_data["exam_type"],
            exam_date=exam_data["exam_date"],
            duration_minutes=exam_data.get("duration_minutes"),
            total_points=exam_data.get("total_points"),
            topics_covered=exam_data.get("topics_covered", []),
            metadata=EventMetadata(
                source_service="schedule-service",
                user_id=user_id,
            ),
        )

        ack = await self.publisher.publish(event)
        print(f"   ✓ Published to NATS: stream={ack.stream}, seq={ack.seq}")

        return exam_id

    async def create_study_todo(
        self, todo_data: dict[str, Any], user_id: str
    ) -> str:
        """Create a study todo - persist to DB and publish event."""
        todo_id = todo_data["todo_id"]
        course_code = todo_data["course_code"]

        print(f"\n✅ Creating study todo: {todo_id}")

        # 1. Persist to ScyllaDB
        print(f"   → Saving to ScyllaDB...")
        await self.store.aput(
            namespace=("study_todos", course_code),
            key=todo_id,
            value=todo_data,
        )
        print(f"   ✓ Saved to ScyllaDB: study_todos/{course_code}/{todo_id}")

        # 2. Publish event to NATS
        print(f"   → Publishing event to NATS...")
        event = StudyTodoCreatedEvent(
            todo_id=todo_id,
            course_code=course_code,
            topic=todo_data["topic"],
            task=todo_data["task"],
            priority=todo_data.get("priority", 3),
            estimated_time=todo_data.get("estimated_time", 60),
            status=todo_data.get("status", "not started"),
            materials_needed=todo_data.get("materials_needed", []),
            metadata=EventMetadata(
                source_service="schedule-service",
                user_id=user_id,
            ),
        )

        ack = await self.publisher.publish(event)
        print(f"   ✓ Published to NATS: stream={ack.stream}, seq={ack.seq}")

        return todo_id


async def main() -> None:
    """Run integrated test with ScyllaDB + NATS."""

    print("=" * 70)
    print("🚀 Integrated ScyllaDB + NATS JetStream Test")
    print("=" * 70)

    # Import ScyllaDB store
    try:
        from vertector_scylladbstore import AsyncScyllaDBStore
    except ImportError:
        print("\n❌ Error: vertector-scylladbstore not installed")
        print("Please install it first:")
        print("  cd /Users/en_tetteh/Documents/databases")
        print("  uv pip install -e .")
        return

    # Initialize both ScyllaDB and NATS
    print("\n1️⃣  Initializing ScyllaDB Store...")
    try:
        async with AsyncScyllaDBStore.from_contact_points(
            contact_points=["127.0.0.1"],
            keyspace="test_keyspace",
            enable_circuit_breaker=False
        ) as scylla_store:

            await scylla_store.setup()
            print("   ✓ ScyllaDB connected and ready")

            # 2. Initialize NATS Client
            print("\n2️⃣  Initializing NATS Client...")
            nats_config = NATSConfig(
                servers=["nats://localhost:4222"],
                client_name="schedule-service",
            )

            nats_client = NATSClient(nats_config)
            await nats_client.connect()
            print("   ✓ NATS connected and JetStream streams created")

            # 3. Create integrated service
            print("\n3️⃣  Creating Academic Schedule Service...")
            publisher = EventPublisher(nats_client)
            service = AcademicScheduleService(scylla_store, publisher)
            print("   ✓ Service ready")

            # 4. Test creating academic entities
            print("\n4️⃣  Creating Academic Entities...")
            print("-" * 70)

            user_id = "student_123"

            # Create courses
            await service.create_course(
        {
            "course_code": "CS101",
            "course_name": "Introduction to Computer Science",
            "semester": "Fall 2025",
            "credits": 3,
            "instructor": "Dr. Jane Smith",
            "difficulty_level": 5,
            "prerequisites": ["MATH100"],
        },
        user_id=user_id,
    )

            await service.create_course(
                {
                    "course_code": "MATH201",
            "course_name": "Calculus II",
            "semester": "Fall 2025",
            "credits": 4,
            "instructor": "Prof. John Doe",
            "difficulty_level": 7,
            "prerequisites": ["MATH101"],
        },
                    user_id=user_id,
                )

            # Create assignment
            await service.create_assignment(
        {
            "assignment_id": "cs101_hw1",
            "course_code": "CS101",
            "title": "Homework 1: Variables and Data Types",
            "due_date": datetime(2025, 10, 15, 23, 59),
            "status": "not started",
            "description": "Complete problems 1-10 from textbook",
            "estimated_hours": 5,
        },
                user_id=user_id,
            )

            # Create exam
            await service.create_exam(
        {
            "exam_id": "cs101_midterm",
            "course_code": "CS101",
            "exam_name": "Midterm Exam",
            "exam_type": "midterm",
            "exam_date": datetime(2025, 11, 1, 9, 0),
            "duration_minutes": 120,
            "total_points": 200,
            "topics_covered": ["variables", "functions", "loops", "conditionals"],
        },
                user_id=user_id,
            )

            # Create study todo
            await service.create_study_todo(
        {
            "todo_id": "study_loops",
            "course_code": "CS101",
            "topic": "For Loops",
            "task": "Practice writing for loops with different ranges",
            "priority": 4,
            "estimated_time": 90,
            "status": "not started",
            "materials_needed": ["textbook", "laptop", "practice problems"],
        },
                user_id=user_id,
            )

            print("\n" + "-" * 70)

            # 5. Summary
            print("\n" + "=" * 70)
            print("✅ TEST COMPLETED SUCCESSFULLY!")
            print("=" * 70)
            print("\n📊 Summary:")
            print(f"   • Created 2 courses (persisted to ScyllaDB + events published)")
            print(f"   • Created 1 assignment (persisted to ScyllaDB + event published)")
            print(f"   • Created 1 exam (persisted to ScyllaDB + event published)")
            print(f"   • Created 1 study todo (persisted to ScyllaDB + event published)")
            print(f"\n   Total: 5 entities persisted and 5 events published")

            print("\n💡 Next Steps:")
            print("   1. Run the consumer to see the events:")
            print("      python examples/consumer_example.py")
            print("\n   2. Check NATS streams:")
            print("      curl http://localhost:8222/jsz | jq")
            print("\n   3. Query ScyllaDB data:")
            print("      Check the stored data in your ScyllaDB instance")

            # Cleanup
            print("\n🧹 Cleaning up...")
            await nats_client.close()
            print("   ✓ Connections closed")

            print("\n" + "=" * 70)

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        print("\nMake sure both services are running:")
        print("  ScyllaDB: cd /Users/en_tetteh/Documents/databases && docker-compose up -d scylla")
        print("  NATS: docker-compose up -d nats")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
