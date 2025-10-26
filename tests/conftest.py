"""Pytest configuration and shared fixtures for NATS JetStream tests.

This module provides reusable fixtures for testing NATS components including:
- Mock NATS servers
- Test event instances
- Configuration objects
- Client/publisher/consumer instances
"""

import asyncio
from datetime import datetime, timezone
from typing import AsyncGenerator
from uuid import uuid4

import pytest
from nats.aio.client import Client as NATS
from nats.js import JetStreamContext

from vertector_nats.client import NATSClient
from vertector_nats.config import ConsumerConfig, NATSConfig, StreamConfig
from vertector_nats.consumer import EventConsumer
from vertector_nats.events import (
    AssignmentCreatedEvent,
    CourseCreatedEvent,
    EventMetadata,
    EventType,
)
from vertector_nats.metrics import reset_metrics
from vertector_nats.publisher import EventPublisher


# ============================================================================
# PYTEST CONFIGURATION
# ============================================================================


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests.

    This fixture ensures all async tests share the same event loop.
    """
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(autouse=True)
def reset_prometheus_metrics():
    """Reset Prometheus metrics before each test.

    This prevents metric pollution between tests and ensures
    each test starts with a clean slate.
    """
    yield
    reset_metrics()


# ============================================================================
# CONFIGURATION FIXTURES
# ============================================================================


@pytest.fixture
def nats_config() -> NATSConfig:
    """Create test NATS configuration.

    Returns:
        NATSConfig configured for testing
    """
    return NATSConfig(
        servers=["nats://localhost:4222"],
        client_name="test-client",
        enable_jetstream=True,
        enable_auth=False,
        enable_tls=False,
        max_reconnect_attempts=3,
        reconnect_wait_seconds=1,
    )


@pytest.fixture
def stream_config() -> StreamConfig:
    """Create test stream configuration.

    Returns:
        StreamConfig for test academic events stream
    """
    return StreamConfig(
        name="TEST_ACADEMIC_EVENTS",
        subjects=["academic.test.*"],
        retention="limits",
        storage="memory",
        max_age_seconds=3600,  # 1 hour for tests
        max_bytes=1024 * 1024,  # 1MB
        replicas=1,
    )


@pytest.fixture
def consumer_config() -> ConsumerConfig:
    """Create test consumer configuration.

    Returns:
        ConsumerConfig for test consumer
    """
    return ConsumerConfig(
        durable_name="test-consumer",
        filter_subjects=["academic.test.*"],
        ack_policy="explicit",
        ack_wait_seconds=30,
        max_deliver=3,
        deliver_policy="all",
    )


# ============================================================================
# EVENT FIXTURES
# ============================================================================


@pytest.fixture
def event_metadata() -> EventMetadata:
    """Create test event metadata.

    Returns:
        EventMetadata with test values
    """
    return EventMetadata(
        source_service="test-service",
        correlation_id="test-correlation-123",
        user_id="test-user-456",
    )


@pytest.fixture
def course_created_event(event_metadata: EventMetadata) -> CourseCreatedEvent:
    """Create a test CourseCreatedEvent.

    Args:
        event_metadata: Event metadata fixture

    Returns:
        CourseCreatedEvent for testing
    """
    return CourseCreatedEvent(
        course_code="TEST101",
        course_name="Test Course",
        semester="Fall 2025",
        credits=3,
        instructor="Dr. Test",
        difficulty_level=5,
        metadata=event_metadata,
    )


@pytest.fixture
def assignment_created_event(event_metadata: EventMetadata) -> AssignmentCreatedEvent:
    """Create a test AssignmentCreatedEvent.

    Args:
        event_metadata: Event metadata fixture

    Returns:
        AssignmentCreatedEvent for testing
    """
    return AssignmentCreatedEvent(
        assignment_id="test-assignment-123",
        course_code="TEST101",
        title="Test Assignment",
        due_date=datetime.now(timezone.utc),
        status="not started",
        estimated_hours=5,
        metadata=event_metadata,
    )


# ============================================================================
# CLIENT FIXTURES (requires running NATS server)
# ============================================================================


@pytest.fixture
async def nats_client(
    nats_config: NATSConfig,
    stream_config: StreamConfig,
) -> AsyncGenerator[NATSClient, None]:
    """Create and connect a NATS client for testing.

    Note: This requires a running NATS server with JetStream enabled.
    Skip tests using this fixture if NATS is not available.

    Args:
        nats_config: NATS configuration fixture
        stream_config: Stream configuration fixture

    Yields:
        Connected NATSClient instance
    """
    # Add test stream to config
    nats_config.streams = [stream_config]

    client = NATSClient(nats_config)

    try:
        await client.connect()
        yield client
    except Exception as e:
        pytest.skip(f"NATS server not available: {e}")
    finally:
        await client.close()


@pytest.fixture
async def publisher(nats_client: NATSClient) -> EventPublisher:
    """Create EventPublisher for testing.

    Args:
        nats_client: Connected NATS client fixture

    Returns:
        EventPublisher instance
    """
    return EventPublisher(
        client=nats_client,
        default_timeout=5.0,
        max_retries=3,
        retry_backoff_base=2.0,
    )


@pytest.fixture
async def consumer(
    nats_client: NATSClient,
    consumer_config: ConsumerConfig,
) -> EventConsumer:
    """Create EventConsumer for testing.

    Args:
        nats_client: Connected NATS client fixture
        consumer_config: Consumer configuration fixture

    Returns:
        EventConsumer instance
    """
    return EventConsumer(
        client=nats_client,
        stream_name="TEST_ACADEMIC_EVENTS",
        consumer_config=consumer_config,
        batch_size=10,
        fetch_timeout=5.0,
    )


# ============================================================================
# MOCK FIXTURES (no NATS server required)
# ============================================================================


@pytest.fixture
def mock_nats_client(mocker):
    """Create a mock NATSClient for unit testing without NATS server.

    Args:
        mocker: pytest-mock fixture

    Returns:
        Mock NATSClient instance
    """
    mock_client = mocker.MagicMock(spec=NATSClient)
    mock_client.config = NATSConfig()
    mock_client._is_connected = True

    # Mock JetStream context
    mock_js = mocker.MagicMock(spec=JetStreamContext)
    mock_client.jetstream = mock_js

    return mock_client


@pytest.fixture
def mock_nats_connection(mocker):
    """Create a mock NATS connection for unit testing.

    Args:
        mocker: pytest-mock fixture

    Returns:
        Mock NATS connection instance
    """
    mock_nc = mocker.MagicMock(spec=NATS)
    mock_nc.is_closed = False
    mock_nc.connected_url = "nats://localhost:4222"

    return mock_nc


# ============================================================================
# UTILITY FIXTURES
# ============================================================================


@pytest.fixture
def sample_event_data() -> dict:
    """Create sample event data dictionary.

    Returns:
        Dictionary representing a serialized event
    """
    return {
        "event_id": str(uuid4()),
        "event_type": EventType.COURSE_CREATED,
        "event_version": "1.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "metadata": {
            "source_service": "test-service",
            "correlation_id": "test-123",
        },
        "course_code": "TEST101",
        "course_name": "Test Course",
        "semester": "Fall 2025",
        "credits": 3,
        "instructor": "Dr. Test",
    }


@pytest.fixture
def large_event_payload() -> str:
    """Create a large event payload for testing size limits.

    Returns:
        JSON string larger than typical max payload
    """
    # Create a payload larger than 1MB (default NATS max)
    large_data = "x" * (1024 * 1024 + 1000)  # 1MB + 1KB
    return large_data


# ============================================================================
# PYTEST MARKERS
# ============================================================================


def pytest_configure(config):
    """Configure custom pytest markers.

    Args:
        config: Pytest config object
    """
    config.addinivalue_line(
        "markers",
        "integration: mark test as integration test (requires NATS server)"
    )
    config.addinivalue_line(
        "markers",
        "unit: mark test as unit test (no external dependencies)"
    )
    config.addinivalue_line(
        "markers",
        "slow: mark test as slow running"
    )
