# Vertector NATS JetStream

Production-ready NATS JetStream client for event-driven microservice communication in academic systems. Built specifically for the academic schedule management and note-taking services ecosystem.

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Features

### Core Functionality
- ✅ **Event-Driven Architecture** - Decouple services with NATS JetStream messaging
- ✅ **Type-Safe Events** - Pydantic models for all academic entities (CRUD operations)
- ✅ **Pull-Based Consumers** - Scalable horizontal consumption patterns
- ✅ **Batch Publishing** - High-performance parallel event publishing
- ✅ **Automatic Reconnection** - Resilient connection management with exponential backoff

### Production-Ready Features
- 🔒 **Security** - TLS/SSL support, token/username authentication
- 📊 **Observability** - Structured logging, OpenTelemetry hooks ready
- 🛡️ **Resilience** - Retry logic, acknowledgment policies, graceful shutdown
- ⚡ **Performance** - Async/await throughout, configurable batching
- ✅ **Testing** - Comprehensive examples and integration patterns

## Quick Start

### Installation

```bash
# Using uv (recommended)
cd /Users/en_tetteh/Documents/vertector-nats-jetstream
uv pip install -e .

# For development
uv pip install -e ".[dev]"

# For examples
uv pip install -e ".[examples]"
```

### Start NATS Server

```bash
# Start NATS with JetStream enabled
docker-compose up -d nats

# Check NATS is running
docker-compose logs -f nats

# Verify health
curl http://localhost:8222/healthz
```

### Publishing Events

```python
from datetime import datetime
from vertector_nats import (
    NATSClient,
    NATSConfig,
    EventPublisher,
    CourseCreatedEvent,
    EventMetadata,
)

# Configure and connect
config = NATSConfig(servers=["nats://localhost:4222"])

async with NATSClient(config) as client:
    publisher = EventPublisher(client)

    # Create and publish event
    event = CourseCreatedEvent(
        course_code="CS101",
        course_name="Intro to Computer Science",
        semester="Fall 2025",
        credits=3,
        instructor="Dr. Smith",
        metadata=EventMetadata(
            source_service="schedule-service",
            user_id="student_123"
        )
    )

    ack = await publisher.publish(event)
    print(f"Published to stream {ack.stream}, seq {ack.seq}")
```

### Consuming Events

```python
from vertector_nats import (
    NATSClient,
    NATSConfig,
    EventConsumer,
    ConsumerConfig,
    BaseEvent,
)
from nats.aio.msg import Msg

async def handle_event(event: BaseEvent, msg: Msg):
    """Process incoming events"""
    print(f"Received: {event.event_type}")

    if event.event_type == "academic.course.created":
        # Handle course creation in note-taking service
        await create_course_notebook(event.course_code)

    await msg.ack()  # Acknowledge successful processing

# Configure consumer
config = NATSConfig(servers=["nats://localhost:4222"])

async with NATSClient(config) as client:
    consumer_config = ConsumerConfig(
        durable_name="notes-service-consumer",
        filter_subjects=["academic.course.*", "academic.assignment.*"],
        ack_policy="explicit",
        max_deliver=3,  # Retry up to 3 times
    )

    consumer = EventConsumer(
        client=client,
        stream_name="ACADEMIC_EVENTS",
        consumer_config=consumer_config,
        batch_size=10,
    )

    # Start consuming (runs indefinitely)
    await consumer.subscribe(handle_event)
```

## Architecture

### System Overview

```
┌──────────────────────────────────────────────────────────────┐
│         Academic Schedule Management Service                 │
│              (Publishes Events)                              │
└────────────────────────┬─────────────────────────────────────┘
                         │ Publishes events
                         ▼
┌──────────────────────────────────────────────────────────────┐
│                  NATS JetStream                              │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ ACADEMIC_EVENTS Stream                                 │ │
│  │                                                        │ │
│  │ Subjects:                                              │ │
│  │   • academic.course.*                                  │ │
│  │   • academic.assignment.*                              │ │
│  │   • academic.exam.*                                    │ │
│  │   • academic.quiz.*                                    │ │
│  │   • academic.lab.*                                     │ │
│  │   • academic.study.*                                   │ │
│  │   • academic.challenge.*                               │ │
│  │   • academic.schedule.*                                │ │
│  │                                                        │ │
│  │ Retention: WorkQueue (consume once)                    │ │
│  │ Storage: File (durable)                                │ │
│  │ Max Age: 7 days                                        │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ NOTES_EVENTS Stream                                    │ │
│  │ Subjects: notes.*                                      │ │
│  │ Retention: Interest (keep until consumed)              │ │
│  └────────────────────────────────────────────────────────┘ │
└────────────────────────┬─────────────────────────────────────┘
                         │ Subscribes to events
                         ▼
┌──────────────────────────────────────────────────────────────┐
│            Note-Taking Service                               │
│              (Consumes Events)                               │
│                                                              │
│  Consumers:                                                  │
│   • notes-service-consumer (academic.*)                      │
│   • search-indexer-consumer (notes.*)                        │
└──────────────────────────────────────────────────────────────┘
```

### Event Types

All academic entities support full CRUD operations:

#### Course Events
- `academic.course.created` - New course created
- `academic.course.read` - Course retrieved (audit)
- `academic.course.updated` - Course modified
- `academic.course.deleted` - Course removed

#### Assignment Events
- `academic.assignment.created`
- `academic.assignment.read`
- `academic.assignment.updated`
- `academic.assignment.deleted`

#### Exam Events
- `academic.exam.created`
- `academic.exam.read`
- `academic.exam.updated`
- `academic.exam.deleted`

#### Quiz Events
- `academic.quiz.created`
- `academic.quiz.read`
- `academic.quiz.updated`
- `academic.quiz.deleted`

#### Lab Session Events
- `academic.lab.created`
- `academic.lab.read`
- `academic.lab.updated`
- `academic.lab.deleted`

#### Study Todo Events
- `academic.study.created`
- `academic.study.read`
- `academic.study.updated`
- `academic.study.deleted`

#### Challenge Area Events
- `academic.challenge.created`
- `academic.challenge.read`
- `academic.challenge.updated`
- `academic.challenge.deleted`

#### Class Schedule Events
- `academic.schedule.created`
- `academic.schedule.read`
- `academic.schedule.updated`
- `academic.schedule.deleted`

## Configuration

### Environment Variables

Create a `.env` file based on `.env.example`:

```bash
# NATS Server Configuration
NATS_SERVERS=nats://localhost:4222
NATS_CLIENT_NAME=vertector-service
NATS_MAX_RECONNECT_ATTEMPTS=10
NATS_RECONNECT_WAIT_SECONDS=2

# Authentication (optional)
NATS_ENABLE_AUTH=false
NATS_USERNAME=
NATS_PASSWORD=
NATS_TOKEN=

# TLS (optional)
NATS_ENABLE_TLS=false
NATS_TLS_CA_CERT_FILE=
NATS_TLS_CERT_FILE=
NATS_TLS_KEY_FILE=

# JetStream
NATS_ENABLE_JETSTREAM=true

# Observability
NATS_ENABLE_TRACING=true
NATS_ENABLE_METRICS=true
```

### Programmatic Configuration

```python
from vertector_nats import NATSConfig, StreamConfig

config = NATSConfig(
    servers=["nats://nats1:4222", "nats://nats2:4222"],
    client_name="my-service",
    enable_auth=True,
    username="app_user",
    password="secret",
    enable_tls=True,
    tls_ca_cert_file="/etc/ssl/ca.pem",
)
```

## Examples

See the `examples/` directory for complete working examples:

- **`publisher_example.py`** - Publishing course, assignment, and exam events
- **`consumer_example.py`** - Consuming events in note-taking service

Run examples:

```bash
# Terminal 1: Start consumer
python examples/consumer_example.py

# Terminal 2: Publish events
python examples/publisher_example.py
```

## Integration with ScyllaDB Store

Combine with your existing ScyllaDB store for complete event-driven architecture:

```python
from vertector_scylladbstore import AsyncScyllaDBStore
from vertector_nats import NATSClient, EventPublisher, CourseCreatedEvent

# Initialize both stores
async with AsyncScyllaDBStore.from_contact_points(...) as scylla_store, \
           NATSClient(nats_config) as nats_client:

    publisher = EventPublisher(nats_client)

    # 1. Save to ScyllaDB
    await scylla_store.aput(
        namespace=("courses",),
        key=course_code,
        value=course_data
    )

    # 2. Publish event for other services
    event = CourseCreatedEvent(
        course_code=course_code,
        course_name=course_data["name"],
        ...
    )
    await publisher.publish(event)
```

## Monitoring

### NATS Server Metrics

Access NATS monitoring dashboard:
```bash
# HTTP monitoring endpoint
curl http://localhost:8222/varz

# Prometheus metrics
curl http://localhost:8222/varz?format=prometheus
```

### Optional Monitoring Stack

Start Prometheus and Grafana for full observability:

```bash
# Start with monitoring profile
docker-compose --profile monitoring up -d

# Access Grafana
open http://localhost:3000
# Login: admin/admin
```

## Best Practices

### 1. Event Publishing

```python
# ✅ Good: Include correlation IDs for tracing
event = CourseCreatedEvent(
    ...,
    metadata=EventMetadata(
        source_service="schedule-service",
        correlation_id=request_id,  # From incoming request
        user_id=current_user_id,
    )
)

# ✅ Good: Use batch publishing for multiple events
events = [event1, event2, event3]
await publisher.publish_batch(events, parallel=True)

# ❌ Bad: Publishing without metadata
event = CourseCreatedEvent(course_code="CS101", ...)  # Missing metadata
```

### 2. Event Consumption

```python
# ✅ Good: Always acknowledge or negative-acknowledge
async def handler(event: BaseEvent, msg: Msg):
    try:
        await process_event(event)
        await msg.ack()  # Success
    except RetryableError:
        await msg.nak()  # Retry
    except PermanentError as e:
        await msg.term()  # Don't retry, log error
        logger.error(f"Permanent failure: {e}")

# ✅ Good: Idempotent handlers (use event_id)
processed_event_ids = set()

async def idempotent_handler(event: BaseEvent, msg: Msg):
    if event.event_id in processed_event_ids:
        await msg.ack()  # Already processed
        return

    await process_event(event)
    processed_event_ids.add(event.event_id)
    await msg.ack()
```

### 3. Error Handling

```python
# ✅ Good: Configure retries and max deliver
consumer_config = ConsumerConfig(
    durable_name="my-consumer",
    max_deliver=3,  # Try 3 times
    ack_wait_seconds=30,  # 30s to process
)

# ✅ Good: Use exponential backoff in publisher
publisher = EventPublisher(
    client,
    max_retries=3,
    retry_backoff_base=2.0,  # 1s, 2s, 4s
)
```

## Development

### Setup

```bash
# Clone and navigate
cd /Users/en_tetteh/Documents/vertector-nats-jetstream

# Install with dev dependencies
uv pip install -e ".[dev]"

# Start NATS server
docker-compose up -d nats
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src/vertector_nats --cov-report=html

# Run specific test markers
pytest -m unit        # Unit tests only
pytest -m integration # Integration tests
```

### Code Quality

```bash
# Format code
black src/ tests/ examples/

# Sort imports
ruff check src/ tests/ examples/ --fix

# Type checking
mypy src/
```

## Troubleshooting

### Connection Issues

```bash
# Check NATS is running
docker-compose ps nats

# View NATS logs
docker-compose logs -f nats

# Test connection
curl http://localhost:8222/healthz
```

### Consumer Not Receiving Messages

1. Verify stream exists:
   ```bash
   nats stream ls
   nats stream info ACADEMIC_EVENTS
   ```

2. Check consumer configuration:
   ```bash
   nats consumer ls ACADEMIC_EVENTS
   nats consumer info ACADEMIC_EVENTS notes-service-consumer
   ```

3. Verify subject filters match published events

### Message Redelivery Loop

- Check handler is calling `msg.ack()` on success
- Verify `max_deliver` isn't too low for processing time
- Increase `ack_wait_seconds` if processing takes longer

## Roadmap

- [ ] v0.2: Dead letter queue support
- [ ] v0.3: Request-reply pattern helpers
- [ ] v0.4: Enhanced observability (Prometheus metrics)
- [ ] v0.5: Schema registry integration
- [ ] v1.0: Production deployment guide

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Support

- 📧 Email: dev@vertector.com
- 🐛 Issues: [GitHub Issues](https://github.com/vertector/vertector-nats-jetstream/issues)

---

**Built for academic excellence** 📚
