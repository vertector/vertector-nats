#!/usr/bin/env python3
"""
Publish a complete test dataset with proper ordering:
1. First publish Course events (so they exist as relationship targets)
2. Then publish dependent events (Assignment, Exam, Quiz, Lab, etc.)
"""
import asyncio
from datetime import datetime, timedelta, UTC
from vertector_nats import (
    EventPublisher,
    NATSClient,
    NATSConfig,
    EventMetadata,
    CourseCreatedEvent,
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
        client_name="graphrag-complete-test-publisher",
    )

    # Connect to NATS
    async with NATSClient(config) as client:
        publisher = EventPublisher(client)
        print("Connected to NATS\n")

        print("=" * 80)
        print("STEP 1: Publishing Course Events (Relationship Targets)")
        print("=" * 80)

        # Course 1: CS101
        course1 = CourseCreatedEvent(
            course_id="CS101-Fall2025",
            code="CS",
            number="101",
            term="Fall 2025",
            title="Introduction to Computer Science",
            description="Foundational course covering programming fundamentals, data structures, algorithms, and computational thinking.",
            instructor_name="Dr. Sarah Johnson",
            instructor_email="sarah.johnson@university.edu",
            credits=4,
            learning_objectives=[
                "Understand programming fundamentals",
                "Master data structures and algorithms",
                "Develop computational thinking skills"
            ],
            metadata=EventMetadata(
                source_service="graphrag-test",
                user_id="student_456"
            )
        )
        await publisher.publish(course1)
        print(f"✓ Published Course: {course1.title}")

        # Course 2: MATH201
        course2 = CourseCreatedEvent(
            course_id="MATH201-Fall2025",
            code="MATH",
            number="201",
            term="Fall 2025",
            title="Calculus II",
            description="Continuation of calculus covering integration techniques, sequences, series, parametric equations, and polar coordinates.",
            instructor_name="Prof. Michael Chen",
            instructor_email="michael.chen@university.edu",
            credits=4,
            learning_objectives=[
                "Master integration techniques",
                "Understand sequences and series",
                "Apply parametric and polar equations"
            ],
            metadata=EventMetadata(
                source_service="graphrag-test",
                user_id="student_456"
            )
        )
        await publisher.publish(course2)
        print(f"✓ Published Course: {course2.title}")

        print("\n" + "=" * 80)
        print("STEP 2: Publishing Dependent Events (Will Create Relationships)")
        print("=" * 80 + "\n")

        # Assignment for CS101
        assignment = AssignmentCreatedEvent(
            assignment_id="ASSIGN-CS101-HW3",
            course_id="CS101-Fall2025",  # References course1
            title="Binary Search Trees Implementation",
            type="Programming",
            description="Implement a balanced binary search tree with insert, delete, and search operations. Include rotation methods for AVL balancing.",
            due_date=datetime.now(UTC) + timedelta(days=7),
            points_possible=100,
            weight=0.15,
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

        # Exam for MATH201
        exam = ExamCreatedEvent(
            exam_id="EXAM-MATH201-MIDTERM",
            course_id="MATH201-Fall2025",  # References course2
            title="Midterm Examination",
            exam_type="Midterm",
            date=datetime.now(UTC) + timedelta(days=14),
            duration_minutes=120,
            location="Hall A, Room 301",
            points_possible=150,
            weight=0.25,
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

        # Quiz for CS101
        quiz = QuizCreatedEvent(
            quiz_id="QUIZ-CS101-WEEK5",
            course_id="CS101-Fall2025",  # References course1
            title="Week 5 Quiz: Recursion and Complexity",
            quiz_number=5,
            date=datetime.now(UTC) + timedelta(days=3),
            duration_minutes=15,
            points_possible=20,
            weight=0.05,
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

        # Lab for MATH201
        lab = LabSessionCreatedEvent(
            lab_id="LAB-MATH201-003",
            course_id="MATH201-Fall2025",  # References course2
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

        # Study Todo for CS101
        todo = StudyTodoCreatedEvent(
            todo_id="TODO-STUDY-001",
            title="Review Recursion Concepts",
            course_id="CS101-Fall2025",  # References course1
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

        # Challenge for MATH201
        challenge = ChallengeAreaCreatedEvent(
            challenge_id="CHALLENGE-MATH-001",
            title="Integration by Parts",
            course_id="MATH201-Fall2025",  # References course2
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

        print("\n" + "=" * 80)
        print(f"✓ Successfully published 8 events total!")
        print("  • 2 Course events (relationship targets)")
        print("  • 6 Dependent events (will create relationships)")
        print("=" * 80)
        print("\nDisconnected from NATS")


if __name__ == "__main__":
    asyncio.run(main())
