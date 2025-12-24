"""
GraphRAG-Aligned NATS Event Models

This file contains all event models aligned with the GraphRAG Note Service schema.

COPY THIS ENTIRE FILE to replace the events in:
/Users/en_tetteh/Documents/vertector-nats-jetstream/src/vertector_nats/events.py

Or integrate these models into the existing file structure.
"""

from datetime import datetime, date
from typing import List, Optional, Dict, Any, Literal
from uuid import UUID, uuid4
from pydantic import BaseModel, Field


# ============================================================================
# BASE MODELS
# ============================================================================

class EventMetadata(BaseModel):
    """Event metadata for distributed tracing and correlation."""

    source_service: str = Field(..., description="Service that generated the event")
    correlation_id: Optional[str] = Field(default=None, description="ID linking related events")
    causation_id: Optional[str] = Field(default=None, description="ID of the event that caused this")
    user_id: Optional[str] = Field(default=None, description="User who triggered the event")
    institution_id: Optional[str] = Field(default=None, description="Institution identifier for multi-tenant data isolation")
    trace_context: Dict[str, Any] = Field(default_factory=dict, description="OpenTelemetry trace context")


class BaseEvent(BaseModel):
    """Base class for all NATS JetStream events."""

    event_id: UUID = Field(default_factory=uuid4, description="Unique event identifier for idempotency")
    event_type: str = Field(..., description="Event type/subject")
    event_version: str = Field(default="1.0", description="Event schema version")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Event creation timestamp (UTC)")
    metadata: EventMetadata = Field(..., description="Event metadata")

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            date: lambda v: v.isoformat(),
            UUID: lambda v: str(v),
        }


# ============================================================================
# PROFILE EVENTS
# ============================================================================

class ProfileCreatedEvent(BaseEvent):
    """Event fired when a new student profile is created."""

    event_type: Literal["academic.profile.created"] = "academic.profile.created"
    student_id: str
    email: str
    first_name: str
    last_name: str
    institution_id: str  # Institution identifier for multi-tenancy
    major: Optional[str] = None
    minor: Optional[str] = None
    year: Optional[int] = None  # 1, 2, 3, 4, 5+ for undergrad/grad
    enrollment_status: str = "Active"  # "Active", "Graduated", "Withdrawn", "Leave of Absence"
    student_type: str = "Undergraduate"  # "Undergraduate", "Graduate", "PhD", "PostDoc"
    matriculation_date: datetime
    expected_graduation: Optional[datetime] = None
    cumulative_gpa: Optional[float] = None
    phone: Optional[str] = None
    emergency_contact: Optional[str] = None
    academic_advisor: Optional[str] = None
    profile_picture_url: Optional[str] = None


class ProfileUpdatedEvent(BaseEvent):
    """Event fired when a student profile is updated."""

    event_type: Literal["academic.profile.updated"] = "academic.profile.updated"
    student_id: str
    changes: Dict[str, Any]
    previous_values: Optional[Dict[str, Any]] = None


class ProfileEnrolledEvent(BaseEvent):
    """Event fired when a student enrolls in a course."""

    event_type: Literal["academic.profile.enrolled"] = "academic.profile.enrolled"
    student_id: str
    course_id: str
    enrollment_date: datetime
    grading_basis: str = "Letter"  # "Letter", "S/NC", "Audit", "Credit/No Credit"
    enrollment_status: str = "Active"  # "Active", "Waitlisted", "Dropped", "Completed"
    final_grade: Optional[float] = None
    letter_grade: Optional[str] = None


class ProfileUnenrolledEvent(BaseEvent):
    """Event fired when a student drops/unenrolls from a course."""

    event_type: Literal["academic.profile.unenrolled"] = "academic.profile.unenrolled"
    student_id: str
    course_id: str
    unenroll_date: datetime
    reason: Optional[str] = None  # "Dropped", "Failed", "Completed", "Withdrawn"
    final_grade: Optional[float] = None
    letter_grade: Optional[str] = None


# ============================================================================
# COURSE EVENTS
# ============================================================================

class CourseCreatedEvent(BaseEvent):
    """Event fired when a new course is created."""

    event_type: Literal["academic.course.created"] = "academic.course.created"
    course_id: str
    title: str
    code: str
    number: str
    term: str
    credits: int
    description: str
    instructor_name: str
    instructor_email: str
    institution_id: str  # Multi-tenant data isolation
    component_type: List[str] = []
    prerequisites: List[str] = []
    grading_options: List[str] = ["Letter"]
    syllabus_url: Optional[str] = None
    learning_objectives: List[str] = []
    final_exam_date: Optional[datetime] = None


class CourseUpdatedEvent(BaseEvent):
    """Event fired when a course is updated."""

    event_type: Literal["academic.course.updated"] = "academic.course.updated"
    course_id: str
    changes: Dict[str, Any]
    previous_values: Optional[Dict[str, Any]] = None


class CourseDeletedEvent(BaseEvent):
    """Event fired when a course is deleted."""

    event_type: Literal["academic.course.deleted"] = "academic.course.deleted"
    course_id: str
    soft_delete: bool = True
    deletion_reason: Optional[str] = None


# ============================================================================
# ASSIGNMENT EVENTS
# ============================================================================

class AssignmentCreatedEvent(BaseEvent):
    """Event fired when a new assignment is created."""

    event_type: Literal["academic.assignment.created"] = "academic.assignment.created"
    assignment_id: str
    title: str
    course_id: str
    student_id: Optional[str] = None  # Student this assignment belongs to (None if for whole class)
    type: str  # "Programming", "Problem Set", "Essay", "Project"
    description: str
    due_date: datetime
    points_possible: int
    points_earned: Optional[float] = None
    percentage_grade: Optional[float] = None
    weight: float  # Decimal 0-1
    submission_status: str = "Not Started"  # "Not Started", "In Progress", "Submitted", "Graded"
    submission_url: Optional[str] = None
    instructions_url: Optional[str] = None
    estimated_hours: Optional[int] = None
    late_penalty: Optional[str] = None
    rubric: Optional[List[Dict[str, Any]]] = None


class AssignmentUpdatedEvent(BaseEvent):
    """Event fired when an assignment is updated."""

    event_type: Literal["academic.assignment.updated"] = "academic.assignment.updated"
    assignment_id: str
    changes: Dict[str, Any]
    previous_values: Optional[Dict[str, Any]] = None


class AssignmentDeletedEvent(BaseEvent):
    """Event fired when an assignment is deleted."""

    event_type: Literal["academic.assignment.deleted"] = "academic.assignment.deleted"
    assignment_id: str
    soft_delete: bool = True
    deletion_reason: Optional[str] = None


# ============================================================================
# EXAM EVENTS
# ============================================================================

class ExamCreatedEvent(BaseEvent):
    """Event fired when a new exam is created."""

    event_type: Literal["academic.exam.created"] = "academic.exam.created"
    exam_id: str
    title: str
    course_id: str
    student_id: Optional[str] = None  # Student this exam record belongs to
    exam_type: str  # "Midterm", "Final", "Cumulative"
    date: datetime
    duration_minutes: int
    location: str
    points_possible: int
    points_earned: Optional[float] = None
    percentage_grade: Optional[float] = None
    weight: float
    topics_covered: List[str] = []
    format: str  # "Multiple Choice", "Essay", "Mixed"
    open_book: bool = False
    allowed_materials: List[str] = []
    preparation_notes: Optional[str] = None


class ExamUpdatedEvent(BaseEvent):
    """Event fired when an exam is updated."""

    event_type: Literal["academic.exam.updated"] = "academic.exam.updated"
    exam_id: str
    changes: Dict[str, Any]
    previous_values: Optional[Dict[str, Any]] = None


class ExamDeletedEvent(BaseEvent):
    """Event fired when an exam is deleted."""

    event_type: Literal["academic.exam.deleted"] = "academic.exam.deleted"
    exam_id: str
    soft_delete: bool = True
    deletion_reason: Optional[str] = None


# ============================================================================
# QUIZ EVENTS
# ============================================================================

class QuizCreatedEvent(BaseEvent):
    """Event fired when a new quiz is created."""

    event_type: Literal["academic.quiz.created"] = "academic.quiz.created"
    quiz_id: str
    title: str
    course_id: str
    student_id: Optional[str] = None  # Student this quiz record belongs to
    quiz_number: int
    date: datetime
    duration_minutes: int
    points_possible: int
    points_earned: Optional[float] = None
    percentage_grade: Optional[float] = None
    weight: float
    topics_covered: List[str] = []
    format: str = "Online"  # "Online" or "In-Class"
    attempts_allowed: int = 1
    auto_graded: bool = True


class QuizUpdatedEvent(BaseEvent):
    """Event fired when a quiz is updated."""

    event_type: Literal["academic.quiz.updated"] = "academic.quiz.updated"
    quiz_id: str
    changes: Dict[str, Any]
    previous_values: Optional[Dict[str, Any]] = None


class QuizDeletedEvent(BaseEvent):
    """Event fired when a quiz is deleted."""

    event_type: Literal["academic.quiz.deleted"] = "academic.quiz.deleted"
    quiz_id: str
    soft_delete: bool = True
    deletion_reason: Optional[str] = None


# ============================================================================
# LAB SESSION EVENTS
# ============================================================================

class LabSessionCreatedEvent(BaseEvent):
    """Event fired when a new lab session is created."""

    event_type: Literal["academic.lab.created"] = "academic.lab.created"
    lab_id: str
    title: str
    course_id: str
    student_id: Optional[str] = None  # Student this lab record belongs to
    session_number: int
    date: datetime
    duration_minutes: int
    location: str
    instructor_name: str
    experiment_title: str
    objectives: List[str] = []
    pre_lab_reading: Optional[str] = None
    pre_lab_assignment_due: Optional[datetime] = None
    equipment_needed: List[str] = []
    safety_requirements: List[str] = []
    submission_deadline: Optional[datetime] = None
    points_possible: Optional[int] = None
    points_earned: Optional[float] = None


class LabSessionUpdatedEvent(BaseEvent):
    """Event fired when a lab session is updated."""

    event_type: Literal["academic.lab.updated"] = "academic.lab.updated"
    lab_id: str
    changes: Dict[str, Any]
    previous_values: Optional[Dict[str, Any]] = None


class LabSessionDeletedEvent(BaseEvent):
    """Event fired when a lab session is deleted."""

    event_type: Literal["academic.lab.deleted"] = "academic.lab.deleted"
    lab_id: str
    soft_delete: bool = True
    deletion_reason: Optional[str] = None


# ============================================================================
# STUDY TODO EVENTS
# ============================================================================

class StudyTodoCreatedEvent(BaseEvent):
    """Event fired when a new study todo is created."""

    event_type: Literal["academic.study.created"] = "academic.study.created"
    todo_id: str
    title: str
    student_id: str  # Student this todo belongs to
    course_id: Optional[str] = None  # Course this todo is related to (can be None for general todos)
    description: str
    priority: str  # "High", "Medium", "Low"
    status: str = "Next Action"  # "Next Action", "Waiting For", "Someday/Maybe", "Completed"
    due_date: Optional[datetime] = None
    estimated_minutes: int
    actual_minutes: Optional[int] = None
    context: List[str] = []  # ["@Library", "@Computer"]
    energy_required: str = "Medium"  # "High", "Medium", "Low"
    created_date: datetime = Field(default_factory=datetime.utcnow)
    completed_date: Optional[datetime] = None
    recurrence: str = "None"  # "Daily", "Weekly", "None"
    ai_generated: bool = False
    source: str = "User"  # "User", "AI-Assignment", "AI-Challenge"


class StudyTodoUpdatedEvent(BaseEvent):
    """Event fired when a study todo is updated."""

    event_type: Literal["academic.study.updated"] = "academic.study.updated"
    todo_id: str
    changes: Dict[str, Any]
    previous_values: Optional[Dict[str, Any]] = None


class StudyTodoDeletedEvent(BaseEvent):
    """Event fired when a study todo is deleted."""

    event_type: Literal["academic.study.deleted"] = "academic.study.deleted"
    todo_id: str
    soft_delete: bool = True
    deletion_reason: Optional[str] = None


# ============================================================================
# CHALLENGE AREA EVENTS
# ============================================================================

class ChallengeAreaCreatedEvent(BaseEvent):
    """Event fired when a new challenge area is identified."""

    event_type: Literal["academic.challenge.created"] = "academic.challenge.created"
    challenge_id: str
    title: str
    student_id: str  # Student facing this challenge
    course_id: Optional[str] = None  # Course where challenge identified (can be None for general challenges)
    description: str
    severity: str  # "Critical", "Moderate", "Minor"
    identified_date: datetime = Field(default_factory=datetime.utcnow)
    detection_method: str  # "AI-Performance", "Self-Reported", "Instructor-Flagged"
    status: str = "Active"  # "Active", "Improving", "Resolved"
    resolution_date: Optional[datetime] = None
    performance_trend: List[float] = []  # Recent grades
    confidence_level: int  # 1-10
    related_topics: List[str] = []
    improvement_notes: Optional[str] = None


class ChallengeAreaUpdatedEvent(BaseEvent):
    """Event fired when a challenge area is updated."""

    event_type: Literal["academic.challenge.updated"] = "academic.challenge.updated"
    challenge_id: str
    changes: Dict[str, Any]
    previous_values: Optional[Dict[str, Any]] = None


class ChallengeAreaDeletedEvent(BaseEvent):
    """Event fired when a challenge area is deleted."""

    event_type: Literal["academic.challenge.deleted"] = "academic.challenge.deleted"
    challenge_id: str
    soft_delete: bool = True
    deletion_reason: Optional[str] = None


# ============================================================================
# CLASS SCHEDULE EVENTS
# ============================================================================

class ClassScheduleCreatedEvent(BaseEvent):
    """Event fired when a new class schedule is created."""

    event_type: Literal["academic.schedule.created"] = "academic.schedule.created"
    schedule_id: str
    course_id: str
    institution_id: str  # Multi-tenant data isolation
    days_of_week: List[str]  # ["Monday", "Wednesday", "Friday"]
    start_time: str  # "11:30:00" (HH:MM:SS)
    end_time: str  # "13:00:00" (HH:MM:SS)
    building: str
    room: str
    campus: str = "Main Campus"
    format: str  # "F2F", "Online", "Hybrid"
    meeting_url: Optional[str] = None
    instructor_office_hours: List[str] = []  # ["Wednesday 14:00-16:00 Gates 288"]
    section_number: str
    enrollment_capacity: int
    term_start_date: date
    term_end_date: date


class ClassScheduleUpdatedEvent(BaseEvent):
    """Event fired when a class schedule is updated."""

    event_type: Literal["academic.schedule.updated"] = "academic.schedule.updated"
    schedule_id: str
    changes: Dict[str, Any]
    previous_values: Optional[Dict[str, Any]] = None


class ClassScheduleDeletedEvent(BaseEvent):
    """Event fired when a class schedule is deleted."""

    event_type: Literal["academic.schedule.deleted"] = "academic.schedule.deleted"
    schedule_id: str
    soft_delete: bool = True
    deletion_reason: Optional[str] = None


# ============================================================================
# UTILITY FUNCTIONS FOR CONVERSION
# ============================================================================

def convert_priority_to_graphrag(nats_priority: int) -> str:
    """
    Convert NATS priority (1-5) to GraphRAG priority string.

    Args:
        nats_priority: Integer 1-5 from old NATS schema

    Returns:
        "High", "Medium", or "Low"
    """
    if nats_priority <= 2:
        return "High"
    elif nats_priority == 3:
        return "Medium"
    else:  # 4-5
        return "Low"


def convert_difficulty_to_severity(difficulty_level: int) -> str:
    """
    Convert NATS difficulty (1-10) to GraphRAG severity string.

    Args:
        difficulty_level: Integer 1-10 from old NATS schema

    Returns:
        "Critical", "Moderate", or "Minor"
    """
    if difficulty_level >= 8:
        return "Critical"
    elif difficulty_level >= 4:
        return "Moderate"
    else:  # 1-3
        return "Minor"


def convert_weight_percentage_to_decimal(weight_percentage: Optional[float]) -> float:
    """
    Convert weight percentage (0-100) to decimal (0-1).

    Args:
        weight_percentage: Percentage 0-100 from old NATS schema

    Returns:
        Decimal 0-1 for GraphRAG
    """
    if weight_percentage is None:
        return 0.0
    return weight_percentage / 100.0
