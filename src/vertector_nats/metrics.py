"""Prometheus metrics for NATS JetStream operations.

This module provides comprehensive metrics collection for monitoring
NATS JetStream publishers and consumers in production.

Metrics Categories:
- Publisher metrics (publish rate, duration, errors, payload size)
- Consumer metrics (consume rate, duration, lag, processing)
- Connection metrics (status, reconnections)
- Stream metrics (metadata)

Example:
    >>> from vertector_nats.metrics import events_published_total
    >>> from vertector_nats.metrics import get_metrics
    >>>
    >>> # Increment counter
    >>> events_published_total.labels(
    ...     event_type="academic.course.created",
    ...     stream="ACADEMIC_EVENTS",
    ...     status="success"
    ... ).inc()
    >>>
    >>> # Export metrics
    >>> metrics, content_type = get_metrics()
"""

from typing import Tuple

from prometheus_client import Counter, Gauge, Histogram, Info
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

# ============================================================================
# PUBLISHER METRICS
# ============================================================================

events_published_total = Counter(
    "nats_events_published_total",
    "Total number of events published to NATS JetStream",
    ["event_type", "stream", "status"],  # status: success|failure
)

publish_duration_seconds = Histogram(
    "nats_publish_duration_seconds",
    "Time taken to publish event to NATS JetStream",
    ["event_type"],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
)

publish_errors_total = Counter(
    "nats_publish_errors_total",
    "Total number of publish errors by error type",
    ["event_type", "error_type"],
)

publish_retries_total = Counter(
    "nats_publish_retries_total",
    "Total number of publish retry attempts",
    ["event_type", "attempt"],
)

payload_size_bytes = Histogram(
    "nats_event_payload_size_bytes",
    "Size of event payloads in bytes",
    ["event_type"],
    buckets=(100, 500, 1000, 5000, 10000, 50000, 100000, 500000, 1000000),
)

# ============================================================================
# CONSUMER METRICS
# ============================================================================

events_consumed_total = Counter(
    "nats_events_consumed_total",
    "Total number of events consumed from NATS JetStream",
    ["event_type", "consumer", "status"],  # status: ack|nak|error
)

consume_duration_seconds = Histogram(
    "nats_consume_duration_seconds",
    "Time taken to process consumed event",
    ["event_type", "consumer"],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
)

consumer_lag_messages = Gauge(
    "nats_consumer_lag_messages",
    "Number of pending messages waiting to be consumed",
    ["stream", "consumer"],
)

consumer_processing_messages = Gauge(
    "nats_consumer_processing_messages",
    "Number of messages currently being processed by consumer",
    ["consumer"],
)

consumer_errors_total = Counter(
    "nats_consumer_errors_total",
    "Total number of consumer errors",
    ["consumer", "error_type"],
)

# ============================================================================
# CONNECTION METRICS
# ============================================================================

connection_status = Gauge(
    "nats_connection_status",
    "NATS connection status (1=connected, 0=disconnected)",
    ["client_name"],
)

reconnection_attempts_total = Counter(
    "nats_reconnection_attempts_total",
    "Total number of reconnection attempts",
    ["client_name", "status"],  # status: success|failure
)

connection_duration_seconds = Gauge(
    "nats_connection_duration_seconds",
    "Duration of current NATS connection in seconds",
    ["client_name"],
)

# ============================================================================
# STREAM METRICS
# ============================================================================

stream_messages_total = Gauge(
    "nats_stream_messages_total",
    "Total number of messages in stream",
    ["stream"],
)

stream_bytes_total = Gauge(
    "nats_stream_bytes_total",
    "Total size of messages in stream (bytes)",
    ["stream"],
)

stream_info = Info(
    "nats_stream_info",
    "Information about configured NATS streams",
)

# ============================================================================
# BUILD INFO
# ============================================================================

nats_client_info = Info(
    "nats_client_build_info",
    "NATS client build and version information",
)

# Initialize build info
nats_client_info.info(
    {
        "version": "0.1.0",
        "python_version": "3.12",
        "nats_py_version": "2.11.0",
        "pydantic_version": "2.0+",
    }
)

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def get_metrics() -> Tuple[bytes, str]:
    """Get Prometheus metrics in exposition format.

    Returns:
        Tuple of (metrics_data, content_type) ready for HTTP response

    Example:
        >>> metrics, content_type = get_metrics()
        >>> # In Flask:
        >>> return Response(metrics, mimetype=content_type)
        >>> # In FastAPI:
        >>> return Response(metrics, media_type=content_type)
        >>> # In aiohttp:
        >>> return web.Response(body=metrics, content_type=content_type)
    """
    return generate_latest(), CONTENT_TYPE_LATEST


def reset_metrics() -> None:
    """Reset all metrics to zero.

    Warning:
        This should only be used in testing. Never call this in production!

    Example:
        >>> # In pytest fixture
        >>> @pytest.fixture(autouse=True)
        ... def reset_prometheus_metrics():
        ...     yield
        ...     reset_metrics()
    """
    # Reset counters
    for collector in [
        events_published_total,
        publish_errors_total,
        publish_retries_total,
        events_consumed_total,
        consumer_errors_total,
        reconnection_attempts_total,
    ]:
        collector._metrics.clear()

    # Reset gauges
    for collector in [
        consumer_lag_messages,
        consumer_processing_messages,
        connection_status,
        connection_duration_seconds,
        stream_messages_total,
        stream_bytes_total,
    ]:
        collector._metrics.clear()

    # Reset histograms
    for collector in [
        publish_duration_seconds,
        consume_duration_seconds,
        payload_size_bytes,
    ]:
        collector._metrics.clear()


def get_metric_names() -> dict[str, list[str]]:
    """Get all registered metric names by category.

    Returns:
        Dictionary mapping category to list of metric names

    Example:
        >>> names = get_metric_names()
        >>> print(names["publisher"])
        ['nats_events_published_total', 'nats_publish_duration_seconds', ...]
    """
    return {
        "publisher": [
            "nats_events_published_total",
            "nats_publish_duration_seconds",
            "nats_publish_errors_total",
            "nats_publish_retries_total",
            "nats_event_payload_size_bytes",
        ],
        "consumer": [
            "nats_events_consumed_total",
            "nats_consume_duration_seconds",
            "nats_consumer_lag_messages",
            "nats_consumer_processing_messages",
            "nats_consumer_errors_total",
        ],
        "connection": [
            "nats_connection_status",
            "nats_reconnection_attempts_total",
            "nats_connection_duration_seconds",
        ],
        "stream": [
            "nats_stream_messages_total",
            "nats_stream_bytes_total",
            "nats_stream_info",
        ],
        "build": ["nats_client_build_info"],
    }


# ============================================================================
# CONTEXT MANAGERS FOR TIMING
# ============================================================================


class PublishTimer:
    """Context manager for timing publish operations with automatic metrics.

    Example:
        >>> async with PublishTimer(event_type="academic.course.created"):
        ...     await js.publish(...)
    """

    def __init__(self, event_type: str):
        """Initialize timer.

        Args:
            event_type: Type of event being published
        """
        self.event_type = event_type
        self.timer = publish_duration_seconds.labels(event_type=event_type).time()

    def __enter__(self):
        """Enter context."""
        self.timer.__enter__()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):  # type: ignore
        """Exit context."""
        self.timer.__exit__(exc_type, exc_val, exc_tb)

    async def __aenter__(self):
        """Enter async context."""
        self.timer.__enter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):  # type: ignore
        """Exit async context."""
        self.timer.__exit__(exc_type, exc_val, exc_tb)


class ConsumeTimer:
    """Context manager for timing consume operations with automatic metrics.

    Example:
        >>> async with ConsumeTimer(event_type="academic.course.created", consumer="notes-service"):
        ...     await handler(event, msg)
    """

    def __init__(self, event_type: str, consumer: str):
        """Initialize timer.

        Args:
            event_type: Type of event being consumed
            consumer: Name of the consumer
        """
        self.event_type = event_type
        self.consumer = consumer
        self.timer = consume_duration_seconds.labels(
            event_type=event_type, consumer=consumer
        ).time()

    def __enter__(self):
        """Enter context."""
        self.timer.__enter__()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):  # type: ignore
        """Exit context."""
        self.timer.__exit__(exc_type, exc_val, exc_tb)

    async def __aenter__(self):
        """Enter async context."""
        self.timer.__enter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):  # type: ignore
        """Exit async context."""
        self.timer.__exit__(exc_type, exc_val, exc_tb)
