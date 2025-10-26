#!/usr/bin/env python3
"""
Publish a variety of academic events to demonstrate the full pipeline
"""
import asyncio
from datetime import datetime, timedelta, UTC
from vertector_nats import (
    EventPublisher,
    NATSClient,
    NATSConfig,
    EventMetadata,
    AssignmentCreatedEvent,
    ExamCreatedEvent,
    QuizCreatedEvent,
    LabSessionCreatedEvent,
    StudyTodoCreatedEvent,
    ChallengeAreaCreatedEvent,
)


async def main():
    # Create NATS configuration
    config = NATSConfig(
        servers=["nats://localhost:4222"],
        client_name="graphrag-test-publisher",
    )

    # Connect to NATS
    async with NATSClient(config) as client:
        publisher = EventPublisher(client)
        print("Connected to NATS\n")

        # 1. Create an Assignment
        assignment = AssignmentCreatedEvent(
            assignment_id="ASSIGN-CS101-HW3",
            course_id="CS101-Fall2025",
            title="Binary Search Trees Implementation",
            type="Programming",
            description="Implement a balanced binary search tree with insert, delete, and search operations. Include rotation methods for AVL balancing.",
            due_date=datetime.now(UTC) + timedelta(days=7),
            points_possible=100,
            weight=0.15,  # 15% of final grade
            submission_status="Not Started",
            estimated_hours=8,
            instructions_url="https://cs101.university.edu/assignments/hw3",
            metadata=EventMetadata(
                source_service="graphrag-test",
                user_id="student_456"
            )
        )
        await publisher.publish(assignment)
        print(f"✓ Published Assignment: {assignment.title}")

        # 2. Create an Exam
        exam = ExamCreatedEvent(
            exam_id="EXAM-MATH201-MIDTERM",
            course_id="MATH201-Fall2025",
            title="Midterm Examination",
            exam_type="Midterm",
            date=datetime.now(UTC) + timedelta(days=14),
            duration_minutes=120,
            location="Hall A, Room 301",
            points_possible=150,
            weight=0.25,  # 25% of final grade
            topics_covered=["Integration techniques", "Sequences and series", "Parametric equations"],
            format="Mixed",
            open_book=False,
            allowed_materials=["Scientific calculator", "One page of handwritten notes"],
            preparation_notes="Review chapters 7-9, practice problems from homework sets 3-5",
            metadata=EventMetadata(
                source_service="graphrag-test",
                user_id="student_456"
            )
        )
        await publisher.publish(exam)
        print(f"✓ Published Exam: {exam.title}")

        # 3. Create a Quiz
        quiz = QuizCreatedEvent(
            quiz_id="QUIZ-CS101-WEEK5",
            course_id="CS101-Fall2025",
            title="Week 5 Quiz: Recursion and Complexity",
            quiz_number=5,
            date=datetime.now(UTC) + timedelta(days=3),
            duration_minutes=15,
            points_possible=20,
            weight=0.05,  # 5% of final grade
            topics_covered=["Recursive algorithms", "Big-O notation", "Time complexity analysis"],
            format="Online",
            attempts_allowed=2,
            auto_graded=True,
            metadata=EventMetadata(
                source_service="graphrag-test",
                user_id="student_456"
            )
        )
        await publisher.publish(quiz)
        print(f"✓ Published Quiz: {quiz.title}")

        # 4. Create a Lab Session
        lab = LabSessionCreatedEvent(
            lab_id="LAB-MATH201-003",
            course_id="MATH201-Fall2025",
            title="Integration Lab Session",
            session_number=3,
            date=datetime.now(UTC) + timedelta(days=5),
            duration_minutes=90,
            location="Science Building, Lab 205",
            instructor_name="TA Sarah Johnson",
            experiment_title="Numerical Integration Methods",
            objectives=["Compare accuracy of trapezoidal rule", "Implement Simpson's rule", "Explore Monte Carlo integration"],
            equipment_needed=["Computer with MATLAB", "Lab worksheet"],
            safety_requirements=["N/A for computational lab"],
            submission_deadline=datetime.now(UTC) + timedelta(days=7),
            points_possible=25,
            metadata=EventMetadata(
                source_service="graphrag-test",
                user_id="student_456"
            )
        )
        await publisher.publish(lab)
        print(f"✓ Published Lab: {lab.title}")

        # 5. Create a Study Todo
        todo = StudyTodoCreatedEvent(
            todo_id="TODO-STUDY-001",
            title="Review Recursion Concepts",
            course_id="CS101-Fall2025",
            description="Go through lecture notes on recursion, complete practice problems from textbook chapter 4, watch supplementary video on recursive tree traversal",
            priority="High",
            status="Next Action",
            due_date=datetime.now(UTC) + timedelta(days=2),
            estimated_minutes=90,
            context=["@Computer", "@Home"],
            energy_required="Medium",
            metadata=EventMetadata(
                source_service="graphrag-test",
                user_id="student_456"
            )
        )
        await publisher.publish(todo)
        print(f"✓ Published Study Todo: {todo.title}")

        # 6. Create a Challenge Area
        challenge = ChallengeAreaCreatedEvent(
            challenge_id="CHALLENGE-MATH-001",
            title="Integration by Parts",
            course_id="MATH201-Fall2025",
            description="Struggling with choosing u and dv in integration by parts. Need more practice with LIATE rule and complex integrals.",
            severity="Moderate",
            detection_method="Self-Reported",
            status="Active",
            performance_trend=[72.0, 68.0, 75.0, 71.0],
            confidence_level=7,
            related_topics=["Integration techniques", "Calculus fundamentals", "LIATE rule"],
            improvement_notes="Practice 5 problems daily, review LIATE mnemonic",
            metadata=EventMetadata(
                source_service="graphrag-test",
                user_id="student_456"
            )
        )
        await publisher.publish(challenge)
        print(f"✓ Published Challenge: {challenge.title}")

        print(f"\n✓ Successfully published 6 different academic events!")
        print("Disconnected from NATS")


if __name__ == "__main__":
    asyncio.run(main())
