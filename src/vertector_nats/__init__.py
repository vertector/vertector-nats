"""Vertector NATS JetStream - Production-ready event-driven microservice communication."""

from vertector_nats.client import NATSClient
from vertector_nats.config import ConsumerConfig, NATSConfig, StreamConfig
from vertector_nats.consumer import EventConsumer, MessageHandler
from vertector_nats.events import (
    AssignmentCreatedEvent,
    AssignmentDeletedEvent,
    AssignmentUpdatedEvent,
    BaseEvent,
    ChallengeAreaCreatedEvent,
    ChallengeAreaDeletedEvent,
    ChallengeAreaUpdatedEvent,
    ClassScheduleCreatedEvent,
    ClassScheduleDeletedEvent,
    ClassScheduleUpdatedEvent,
    CourseCreatedEvent,
    CourseDeletedEvent,
    CourseUpdatedEvent,
    EventMetadata,
    ExamCreatedEvent,
    ExamDeletedEvent,
    ExamUpdatedEvent,
    LabSessionCreatedEvent,
    LabSessionDeletedEvent,
    LabSessionUpdatedEvent,
    ProfileCreatedEvent,
    ProfileEnrolledEvent,
    ProfileUnenrolledEvent,
    ProfileUpdatedEvent,
    QuizCreatedEvent,
    QuizDeletedEvent,
    QuizUpdatedEvent,
    StudyTodoCreatedEvent,
    StudyTodoDeletedEvent,
    StudyTodoUpdatedEvent,
)
from vertector_nats.publisher import EventPublisher

__version__ = "0.1.0"

__all__ = [
    # Core client
    "NATSClient",
    # Configuration
    "NATSConfig",
    "StreamConfig",
    "ConsumerConfig",
    # Events - Base
    "BaseEvent",
    "EventMetadata",
    # Events - Profile
    "ProfileCreatedEvent",
    "ProfileUpdatedEvent",
    "ProfileEnrolledEvent",
    "ProfileUnenrolledEvent",
    # Events - Course (CUD)
    "CourseCreatedEvent",
    "CourseUpdatedEvent",
    "CourseDeletedEvent",
    # Events - Assignment (CUD)
    "AssignmentCreatedEvent",
    "AssignmentUpdatedEvent",
    "AssignmentDeletedEvent",
    # Events - Exam (CUD)
    "ExamCreatedEvent",
    "ExamUpdatedEvent",
    "ExamDeletedEvent",
    # Events - Quiz (CUD)
    "QuizCreatedEvent",
    "QuizUpdatedEvent",
    "QuizDeletedEvent",
    # Events - Lab Session (CUD)
    "LabSessionCreatedEvent",
    "LabSessionUpdatedEvent",
    "LabSessionDeletedEvent",
    # Events - Study Todo (CUD)
    "StudyTodoCreatedEvent",
    "StudyTodoUpdatedEvent",
    "StudyTodoDeletedEvent",
    # Events - Challenge Area (CUD)
    "ChallengeAreaCreatedEvent",
    "ChallengeAreaUpdatedEvent",
    "ChallengeAreaDeletedEvent",
    # Events - Class Schedule (CUD)
    "ClassScheduleCreatedEvent",
    "ClassScheduleUpdatedEvent",
    "ClassScheduleDeletedEvent",
    # Publisher/Consumer
    "EventPublisher",
    "EventConsumer",
    "MessageHandler",
]
