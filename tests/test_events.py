"""Unit tests for event schemas and validation.

Tests cover:
- Event creation and validation
- Serialization/deserialization
- Field validation (required, optional, constraints)
- EventType enum handling
- Timestamp handling (timezone-aware)
- Event metadata
"""

import json
from datetime import datetime, timezone
from uuid import UUID

import pytest
from pydantic import ValidationError

from vertector_nats.events import (
    AssignmentCreatedEvent,
    AssignmentDeletedEvent,
    AssignmentUpdatedEvent,
    BaseEvent,
    ChallengeAreaCreatedEvent,
    ClassScheduleCreatedEvent,
    CourseCreatedEvent,
    CourseDeletedEvent,
    CourseUpdatedEvent,
    EventMetadata,
    EventType,
    ExamCreatedEvent,
    LabSessionCreatedEvent,
    QuizCreatedEvent,
    StudyTodoCreatedEvent,
)


# ============================================================================
# EVENT METADATA TESTS
# ============================================================================


@pytest.mark.unit
class TestEventMetadata:
    """Test EventMetadata schema."""

    def test_create_minimal_metadata(self):
        """Test creating metadata with only required fields."""
        metadata = EventMetadata(source_service="test-service")

        assert metadata.source_service == "test-service"
        assert metadata.correlation_id is None
        assert metadata.causation_id is None
        assert metadata.user_id is None
        assert metadata.trace_context == {}

    def test_create_full_metadata(self):
        """Test creating metadata with all fields."""
        metadata = EventMetadata(
            source_service="test-service",
            correlation_id="corr-123",
            causation_id="cause-456",
            user_id="user-789",
            trace_context={"trace_id": "abc", "span_id": "def"},
        )

        assert metadata.source_service == "test-service"
        assert metadata.correlation_id == "corr-123"
        assert metadata.causation_id == "cause-456"
        assert metadata.user_id == "user-789"
        assert metadata.trace_context == {"trace_id": "abc", "span_id": "def"}

    def test_metadata_serialization(self):
        """Test metadata can be serialized to JSON."""
        metadata = EventMetadata(
            source_service="test-service",
            correlation_id="corr-123",
        )

        json_str = metadata.model_dump_json()
        data = json.loads(json_str)

        assert data["source_service"] == "test-service"
        assert data["correlation_id"] == "corr-123"

    def test_metadata_missing_required_field(self):
        """Test metadata validation fails without source_service."""
        with pytest.raises(ValidationError) as exc_info:
            EventMetadata()

        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert errors[0]["loc"] == ("source_service",)
        assert errors[0]["type"] == "missing"


# ============================================================================
# BASE EVENT TESTS
# ============================================================================


@pytest.mark.unit
class TestBaseEvent:
    """Test BaseEvent schema."""

    def test_create_base_event(self, event_metadata):
        """Test creating a base event."""
        event = BaseEvent(
            event_type="test.event",
            metadata=event_metadata,
        )

        assert isinstance(event.event_id, UUID)
        assert event.event_type == "test.event"
        assert event.event_version == "1.0"
        assert isinstance(event.timestamp, datetime)
        assert event.timestamp.tzinfo == timezone.utc
        assert event.metadata == event_metadata

    def test_event_id_is_unique(self, event_metadata):
        """Test that each event gets a unique ID."""
        event1 = BaseEvent(event_type="test.event", metadata=event_metadata)
        event2 = BaseEvent(event_type="test.event", metadata=event_metadata)

        assert event1.event_id != event2.event_id

    def test_timestamp_is_timezone_aware(self, event_metadata):
        """Test that timestamp is timezone-aware (UTC)."""
        event = BaseEvent(event_type="test.event", metadata=event_metadata)

        assert event.timestamp.tzinfo is not None
        assert event.timestamp.tzinfo == timezone.utc

    def test_base_event_serialization(self, event_metadata):
        """Test base event can be serialized to JSON."""
        event = BaseEvent(event_type="test.event", metadata=event_metadata)

        json_str = event.model_dump_json()
        data = json.loads(json_str)

        assert "event_id" in data
        assert "event_type" in data
        assert "event_version" in data
        assert "timestamp" in data
        assert "metadata" in data

    def test_base_event_deserialization(self, sample_event_data):
        """Test base event can be deserialized from JSON."""
        event = BaseEvent(**sample_event_data)

        assert str(event.event_id) == sample_event_data["event_id"]
        assert event.event_type == sample_event_data["event_type"]


# ============================================================================
# COURSE EVENT TESTS
# ============================================================================


@pytest.mark.unit
class TestCourseEvents:
    """Test Course event schemas."""

    def test_create_course_created_event(self, event_metadata):
        """Test creating a CourseCreatedEvent with required fields."""
        event = CourseCreatedEvent(
            course_code="CS101",
            course_name="Intro to CS",
            semester="Fall 2025",
            credits=3,
            instructor="Dr. Smith",
            metadata=event_metadata,
        )

        assert event.event_type == EventType.COURSE_CREATED
        assert event.course_code == "CS101"
        assert event.course_name == "Intro to CS"
        assert event.semester == "Fall 2025"
        assert event.credits == 3
        assert event.instructor == "Dr. Smith"
        assert event.difficulty_level is None
        assert event.current_grade is None

    def test_course_created_with_optional_fields(self, event_metadata):
        """Test creating CourseCreatedEvent with optional fields."""
        event = CourseCreatedEvent(
            course_code="CS101",
            course_name="Intro to CS",
            semester="Fall 2025",
            credits=3,
            instructor="Dr. Smith",
            difficulty_level=7,
            current_grade="A",
            is_challenging=True,
            prerequisites=["MATH101"],
            corequisites=["LAB101"],
            metadata=event_metadata,
        )

        assert event.difficulty_level == 7
        assert event.current_grade == "A"
        assert event.is_challenging is True
        assert event.prerequisites == ["MATH101"]
        assert event.corequisites == ["LAB101"]

    def test_course_credits_validation(self, event_metadata):
        """Test credits must be between 0 and 20."""
        # Valid: 0 credits
        event = CourseCreatedEvent(
            course_code="CS101",
            course_name="Intro to CS",
            semester="Fall 2025",
            credits=0,
            instructor="Dr. Smith",
            metadata=event_metadata,
        )
        assert event.credits == 0

        # Valid: 20 credits
        event = CourseCreatedEvent(
            course_code="CS101",
            course_name="Intro to CS",
            semester="Fall 2025",
            credits=20,
            instructor="Dr. Smith",
            metadata=event_metadata,
        )
        assert event.credits == 20

        # Invalid: negative credits
        with pytest.raises(ValidationError):
            CourseCreatedEvent(
                course_code="CS101",
                course_name="Intro to CS",
                semester="Fall 2025",
                credits=-1,
                instructor="Dr. Smith",
                metadata=event_metadata,
            )

        # Invalid: too many credits
        with pytest.raises(ValidationError):
            CourseCreatedEvent(
                course_code="CS101",
                course_name="Intro to CS",
                semester="Fall 2025",
                credits=21,
                instructor="Dr. Smith",
                metadata=event_metadata,
            )

    def test_difficulty_level_validation(self, event_metadata):
        """Test difficulty_level must be between 1 and 10."""
        # Valid: 1
        event = CourseCreatedEvent(
            course_code="CS101",
            course_name="Intro to CS",
            semester="Fall 2025",
            credits=3,
            instructor="Dr. Smith",
            difficulty_level=1,
            metadata=event_metadata,
        )
        assert event.difficulty_level == 1

        # Valid: 10
        event = CourseCreatedEvent(
            course_code="CS101",
            course_name="Intro to CS",
            semester="Fall 2025",
            credits=3,
            instructor="Dr. Smith",
            difficulty_level=10,
            metadata=event_metadata,
        )
        assert event.difficulty_level == 10

        # Invalid: 0
        with pytest.raises(ValidationError):
            CourseCreatedEvent(
                course_code="CS101",
                course_name="Intro to CS",
                semester="Fall 2025",
                credits=3,
                instructor="Dr. Smith",
                difficulty_level=0,
                metadata=event_metadata,
            )

        # Invalid: 11
        with pytest.raises(ValidationError):
            CourseCreatedEvent(
                course_code="CS101",
                course_name="Intro to CS",
                semester="Fall 2025",
                credits=3,
                instructor="Dr. Smith",
                difficulty_level=11,
                metadata=event_metadata,
            )

    def test_course_updated_event(self, event_metadata):
        """Test CourseUpdatedEvent with changes tracking."""
        event = CourseUpdatedEvent(
            course_code="CS101",
            changes={"instructor": "Dr. Jones", "credits": 4},
            previous_values={"instructor": "Dr. Smith", "credits": 3},
            metadata=event_metadata,
        )

        assert event.event_type == EventType.COURSE_UPDATED
        assert event.course_code == "CS101"
        assert event.changes == {"instructor": "Dr. Jones", "credits": 4}
        assert event.previous_values == {"instructor": "Dr. Smith", "credits": 3}

    def test_course_deleted_event(self, event_metadata):
        """Test CourseDeletedEvent with soft/hard delete."""
        # Soft delete (default)
        event = CourseDeletedEvent(
            course_code="CS101",
            metadata=event_metadata,
        )

        assert event.event_type == EventType.COURSE_DELETED
        assert event.course_code == "CS101"
        assert event.soft_delete is True

        # Hard delete
        event = CourseDeletedEvent(
            course_code="CS101",
            soft_delete=False,
            metadata=event_metadata,
        )

        assert event.soft_delete is False

    def test_course_event_serialization(self, course_created_event):
        """Test course event can be serialized and deserialized."""
        # Serialize
        json_str = course_created_event.model_dump_json()
        data = json.loads(json_str)

        # Verify JSON structure
        assert data["event_type"] == "academic.course.created"
        assert data["course_code"] == "TEST101"
        assert data["course_name"] == "Test Course"

        # Deserialize
        event = CourseCreatedEvent(**data)
        assert event.course_code == course_created_event.course_code
        assert event.course_name == course_created_event.course_name


# ============================================================================
# ASSIGNMENT EVENT TESTS
# ============================================================================


@pytest.mark.unit
class TestAssignmentEvents:
    """Test Assignment event schemas."""

    def test_create_assignment_created_event(self, event_metadata):
        """Test creating AssignmentCreatedEvent."""
        due_date = datetime.now(timezone.utc)

        event = AssignmentCreatedEvent(
            assignment_id="a123",
            course_code="CS101",
            title="Homework 1",
            due_date=due_date,
            metadata=event_metadata,
        )

        assert event.event_type == EventType.ASSIGNMENT_CREATED
        assert event.assignment_id == "a123"
        assert event.course_code == "CS101"
        assert event.title == "Homework 1"
        assert event.due_date == due_date
        assert event.status == "not started"

    def test_assignment_status_validation(self, event_metadata):
        """Test assignment status must be one of allowed values."""
        due_date = datetime.now(timezone.utc)

        # Valid: not started
        event = AssignmentCreatedEvent(
            assignment_id="a123",
            course_code="CS101",
            title="Homework 1",
            due_date=due_date,
            status="not started",
            metadata=event_metadata,
        )
        assert event.status == "not started"

        # Valid: in progress
        event = AssignmentCreatedEvent(
            assignment_id="a123",
            course_code="CS101",
            title="Homework 1",
            due_date=due_date,
            status="in progress",
            metadata=event_metadata,
        )
        assert event.status == "in progress"

        # Valid: completed
        event = AssignmentCreatedEvent(
            assignment_id="a123",
            course_code="CS101",
            title="Homework 1",
            due_date=due_date,
            status="completed",
            metadata=event_metadata,
        )
        assert event.status == "completed"

        # Invalid status
        with pytest.raises(ValidationError):
            AssignmentCreatedEvent(
                assignment_id="a123",
                course_code="CS101",
                title="Homework 1",
                due_date=due_date,
                status="invalid_status",
                metadata=event_metadata,
            )

    def test_assignment_hours_validation(self, event_metadata):
        """Test estimated_hours validation."""
        due_date = datetime.now(timezone.utc)

        # Valid: 1 hour
        event = AssignmentCreatedEvent(
            assignment_id="a123",
            course_code="CS101",
            title="Homework 1",
            due_date=due_date,
            estimated_hours=1,
            metadata=event_metadata,
        )
        assert event.estimated_hours == 1

        # Valid: 200 hours
        event = AssignmentCreatedEvent(
            assignment_id="a123",
            course_code="CS101",
            title="Homework 1",
            due_date=due_date,
            estimated_hours=200,
            metadata=event_metadata,
        )
        assert event.estimated_hours == 200

        # Invalid: 0 hours
        with pytest.raises(ValidationError):
            AssignmentCreatedEvent(
                assignment_id="a123",
                course_code="CS101",
                title="Homework 1",
                due_date=due_date,
                estimated_hours=0,
                metadata=event_metadata,
            )

        # Invalid: 201 hours
        with pytest.raises(ValidationError):
            AssignmentCreatedEvent(
                assignment_id="a123",
                course_code="CS101",
                title="Homework 1",
                due_date=due_date,
                estimated_hours=201,
                metadata=event_metadata,
            )

    def test_assignment_updated_event(self, event_metadata):
        """Test AssignmentUpdatedEvent."""
        event = AssignmentUpdatedEvent(
            assignment_id="a123",
            course_code="CS101",
            changes={"status": "completed", "total_points": 95},
            previous_values={"status": "in progress", "total_points": 0},
            metadata=event_metadata,
        )

        assert event.event_type == EventType.ASSIGNMENT_UPDATED
        assert event.assignment_id == "a123"
        assert event.changes["status"] == "completed"

    def test_assignment_deleted_event(self, event_metadata):
        """Test AssignmentDeletedEvent."""
        event = AssignmentDeletedEvent(
            assignment_id="a123",
            course_code="CS101",
            metadata=event_metadata,
        )

        assert event.event_type == EventType.ASSIGNMENT_DELETED
        assert event.assignment_id == "a123"
        assert event.soft_delete is True


# ============================================================================
# EXAM EVENT TESTS
# ============================================================================


@pytest.mark.unit
class TestExamEvents:
    """Test Exam event schemas."""

    def test_create_exam_created_event(self, event_metadata):
        """Test creating ExamCreatedEvent."""
        exam_date = datetime.now(timezone.utc)

        event = ExamCreatedEvent(
            exam_id="e123",
            course_code="CS101",
            exam_name="Midterm Exam",
            exam_type="midterm",
            exam_date=exam_date,
            metadata=event_metadata,
        )

        assert event.event_type == EventType.EXAM_CREATED
        assert event.exam_id == "e123"
        assert event.exam_type == "midterm"

    def test_exam_type_validation(self, event_metadata):
        """Test exam_type must be one of allowed values."""
        exam_date = datetime.now(timezone.utc)

        # Valid types
        for exam_type in ["quiz", "midterm", "final", "other"]:
            event = ExamCreatedEvent(
                exam_id="e123",
                course_code="CS101",
                exam_name="Test Exam",
                exam_type=exam_type,
                exam_date=exam_date,
                metadata=event_metadata,
            )
            assert event.exam_type == exam_type

        # Invalid type
        with pytest.raises(ValidationError):
            ExamCreatedEvent(
                exam_id="e123",
                course_code="CS101",
                exam_name="Test Exam",
                exam_type="invalid_type",
                exam_date=exam_date,
                metadata=event_metadata,
            )

    def test_exam_duration_validation(self, event_metadata):
        """Test duration_minutes validation."""
        exam_date = datetime.now(timezone.utc)

        # Valid: 1 minute
        event = ExamCreatedEvent(
            exam_id="e123",
            course_code="CS101",
            exam_name="Test Exam",
            exam_type="quiz",
            exam_date=exam_date,
            duration_minutes=1,
            metadata=event_metadata,
        )
        assert event.duration_minutes == 1

        # Valid: 480 minutes (8 hours)
        event = ExamCreatedEvent(
            exam_id="e123",
            course_code="CS101",
            exam_name="Test Exam",
            exam_type="final",
            exam_date=exam_date,
            duration_minutes=480,
            metadata=event_metadata,
        )
        assert event.duration_minutes == 480

        # Invalid: 0 minutes
        with pytest.raises(ValidationError):
            ExamCreatedEvent(
                exam_id="e123",
                course_code="CS101",
                exam_name="Test Exam",
                exam_type="quiz",
                exam_date=exam_date,
                duration_minutes=0,
                metadata=event_metadata,
            )


# ============================================================================
# STUDY TODO EVENT TESTS
# ============================================================================


@pytest.mark.unit
class TestStudyTodoEvents:
    """Test StudyTodo event schemas."""

    def test_create_study_todo_created_event(self, event_metadata):
        """Test creating StudyTodoCreatedEvent."""
        event = StudyTodoCreatedEvent(
            todo_id="t123",
            course_code="CS101",
            topic="Data Structures",
            task="Review binary trees",
            priority=3,
            estimated_time=60,
            metadata=event_metadata,
        )

        assert event.event_type == EventType.STUDY_TODO_CREATED
        assert event.todo_id == "t123"
        assert event.priority == 3
        assert event.estimated_time == 60
        assert event.status == "not started"

    def test_priority_validation(self, event_metadata):
        """Test priority must be between 1 and 5."""
        # Valid: 1-5
        for priority in range(1, 6):
            event = StudyTodoCreatedEvent(
                todo_id="t123",
                course_code="CS101",
                topic="Test",
                task="Test task",
                priority=priority,
                estimated_time=30,
                metadata=event_metadata,
            )
            assert event.priority == priority

        # Invalid: 0
        with pytest.raises(ValidationError):
            StudyTodoCreatedEvent(
                todo_id="t123",
                course_code="CS101",
                topic="Test",
                task="Test task",
                priority=0,
                estimated_time=30,
                metadata=event_metadata,
            )

        # Invalid: 6
        with pytest.raises(ValidationError):
            StudyTodoCreatedEvent(
                todo_id="t123",
                course_code="CS101",
                topic="Test",
                task="Test task",
                priority=6,
                estimated_time=30,
                metadata=event_metadata,
            )

    def test_estimated_time_validation(self, event_metadata):
        """Test estimated_time must be between 5 and 480 minutes."""
        # Valid: 5 minutes
        event = StudyTodoCreatedEvent(
            todo_id="t123",
            course_code="CS101",
            topic="Test",
            task="Test task",
            priority=3,
            estimated_time=5,
            metadata=event_metadata,
        )
        assert event.estimated_time == 5

        # Valid: 480 minutes
        event = StudyTodoCreatedEvent(
            todo_id="t123",
            course_code="CS101",
            topic="Test",
            task="Test task",
            priority=3,
            estimated_time=480,
            metadata=event_metadata,
        )
        assert event.estimated_time == 480

        # Invalid: 4 minutes
        with pytest.raises(ValidationError):
            StudyTodoCreatedEvent(
                todo_id="t123",
                course_code="CS101",
                topic="Test",
                task="Test task",
                priority=3,
                estimated_time=4,
                metadata=event_metadata,
            )


# ============================================================================
# CHALLENGE AREA EVENT TESTS
# ============================================================================


@pytest.mark.unit
class TestChallengeAreaEvents:
    """Test ChallengeArea event schemas."""

    def test_create_challenge_area_created_event(self, event_metadata):
        """Test creating ChallengeAreaCreatedEvent."""
        event = ChallengeAreaCreatedEvent(
            challenge_id="c123",
            course_code="CS101",
            subject="Algorithms",
            topic="Dynamic Programming",
            difficulty_level=8,
            priority_level="high",
            metadata=event_metadata,
        )

        assert event.event_type == EventType.CHALLENGE_CREATED
        assert event.challenge_id == "c123"
        assert event.difficulty_level == 8
        assert event.priority_level == "high"

    def test_priority_level_validation(self, event_metadata):
        """Test priority_level must be low, medium, or high."""
        # Valid values
        for priority in ["low", "medium", "high"]:
            event = ChallengeAreaCreatedEvent(
                challenge_id="c123",
                course_code="CS101",
                subject="Test",
                topic="Test topic",
                difficulty_level=5,
                priority_level=priority,
                metadata=event_metadata,
            )
            assert event.priority_level == priority

        # Invalid value
        with pytest.raises(ValidationError):
            ChallengeAreaCreatedEvent(
                challenge_id="c123",
                course_code="CS101",
                subject="Test",
                topic="Test topic",
                difficulty_level=5,
                priority_level="critical",
                metadata=event_metadata,
            )


# ============================================================================
# CLASS SCHEDULE EVENT TESTS
# ============================================================================


@pytest.mark.unit
class TestClassScheduleEvents:
    """Test ClassSchedule event schemas."""

    def test_create_class_schedule_created_event(self, event_metadata):
        """Test creating ClassScheduleCreatedEvent."""
        event = ClassScheduleCreatedEvent(
            schedule_id="s123",
            course_code="CS101",
            day_of_week="Monday",
            start_time="09:00",
            end_time="10:30",
            semester="Fall 2025",
            metadata=event_metadata,
        )

        assert event.event_type == EventType.CLASS_SCHEDULE_CREATED
        assert event.schedule_id == "s123"
        assert event.day_of_week == "Monday"
        assert event.recurring is True

    def test_day_of_week_validation(self, event_metadata):
        """Test day_of_week must be valid weekday."""
        # Valid days
        valid_days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

        for day in valid_days:
            event = ClassScheduleCreatedEvent(
                schedule_id="s123",
                course_code="CS101",
                day_of_week=day,
                start_time="09:00",
                end_time="10:30",
                semester="Fall 2025",
                metadata=event_metadata,
            )
            assert event.day_of_week == day

        # Invalid day
        with pytest.raises(ValidationError):
            ClassScheduleCreatedEvent(
                schedule_id="s123",
                course_code="CS101",
                day_of_week="Funday",
                start_time="09:00",
                end_time="10:30",
                semester="Fall 2025",
                metadata=event_metadata,
            )


# ============================================================================
# EVENT TYPE ENUM TESTS
# ============================================================================


@pytest.mark.unit
class TestEventTypeEnum:
    """Test EventType enum."""

    def test_event_type_values(self):
        """Test EventType enum has correct values."""
        assert EventType.COURSE_CREATED.value == "academic.course.created"
        assert EventType.COURSE_UPDATED.value == "academic.course.updated"
        assert EventType.COURSE_DELETED.value == "academic.course.deleted"

        assert EventType.ASSIGNMENT_CREATED.value == "academic.assignment.created"
        assert EventType.EXAM_CREATED.value == "academic.exam.created"
        assert EventType.QUIZ_CREATED.value == "academic.quiz.created"

    def test_event_type_string_conversion(self):
        """Test EventType can be converted to string."""
        event_type = EventType.COURSE_CREATED

        assert str(event_type.value) == "academic.course.created"

    def test_event_type_in_event(self, event_metadata):
        """Test EventType is correctly set in events."""
        event = CourseCreatedEvent(
            course_code="CS101",
            course_name="Intro to CS",
            semester="Fall 2025",
            credits=3,
            instructor="Dr. Smith",
            metadata=event_metadata,
        )

        assert event.event_type == EventType.COURSE_CREATED
        assert event.event_type.value == "academic.course.created"


# ============================================================================
# SERIALIZATION TESTS
# ============================================================================


@pytest.mark.unit
class TestEventSerialization:
    """Test event serialization and deserialization."""

    def test_uuid_serialization(self, course_created_event):
        """Test UUID is serialized to string."""
        json_str = course_created_event.model_dump_json()
        data = json.loads(json_str)

        assert isinstance(data["event_id"], str)
        # Verify it's a valid UUID string
        UUID(data["event_id"])

    def test_datetime_serialization(self, course_created_event):
        """Test datetime is serialized to ISO format."""
        json_str = course_created_event.model_dump_json()
        data = json.loads(json_str)

        assert isinstance(data["timestamp"], str)
        # Verify it can be parsed back
        timestamp = datetime.fromisoformat(data["timestamp"].replace("Z", "+00:00"))
        assert timestamp.tzinfo is not None

    def test_enum_serialization(self, course_created_event):
        """Test EventType enum is serialized to value."""
        json_str = course_created_event.model_dump_json()
        data = json.loads(json_str)

        assert data["event_type"] == "academic.course.created"

    def test_full_round_trip(self, course_created_event):
        """Test event can be serialized and deserialized."""
        # Serialize to JSON
        json_str = course_created_event.model_dump_json()

        # Deserialize back
        data = json.loads(json_str)
        event = CourseCreatedEvent(**data)

        # Verify all fields match
        assert event.course_code == course_created_event.course_code
        assert event.course_name == course_created_event.course_name
        assert event.semester == course_created_event.semester
        assert event.credits == course_created_event.credits
        assert event.instructor == course_created_event.instructor
        assert str(event.event_id) == str(course_created_event.event_id)

    def test_model_dump_includes_all_fields(self, course_created_event):
        """Test model_dump includes all fields."""
        data = course_created_event.model_dump()

        assert "event_id" in data
        assert "event_type" in data
        assert "event_version" in data
        assert "timestamp" in data
        assert "metadata" in data
        assert "course_code" in data
        assert "course_name" in data
        assert "semester" in data
        assert "credits" in data
        assert "instructor" in data
