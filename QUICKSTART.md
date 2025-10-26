# Quick Start Guide

Get up and running with Vertector NATS JetStream in 5 minutes.

## Prerequisites

- Python 3.12+
- Docker and Docker Compose
- `uv` package manager (or `pip`)

## Step 1: Start NATS Server

```bash
cd /Users/en_tetteh/Documents/vertector-nats-jetstream

# Start NATS with JetStream
docker-compose up -d nats

# Verify it's running
curl http://localhost:8222/healthz
# Should return: ok
```

## Step 2: Install Package

```bash
# Install the package (development mode)
uv pip install -e ".[examples]"
```

## Step 3: Try the Examples

### Terminal 1: Start Consumer

```bash
# This will listen for academic events
python examples/consumer_example.py
```

You should see:
```
🚀 Note-taking service consumer started
📡 Listening for events on stream: ACADEMIC_EVENTS
🔍 Filtering subjects: ['academic.course.*', 'academic.assignment.*', ...]

Waiting for events... (Press Ctrl+C to stop)
```

### Terminal 2: Publish Events

```bash
# In a new terminal, publish sample events
python examples/publisher_example.py
```

You should see events being published and consumed in real-time!

## Step 4: Integrate into Your Services

### In Academic Schedule Service (Publisher)

```python
from vertector_nats import (
    NATSClient,
    NATSConfig,
    EventPublisher,
    CourseCreatedEvent,
    EventMetadata,
)

# Initialize once (e.g., in FastAPI startup)
config = NATSConfig()
nats_client = NATSClient(config)
await nats_client.connect()
publisher = EventPublisher(nats_client)

# Publish events when data changes
async def create_course(course_data: dict):
    # 1. Save to ScyllaDB
    await scylla_store.aput(...)

    # 2. Publish event
    event = CourseCreatedEvent(
        course_code=course_data["course_code"],
        course_name=course_data["name"],
        semester=course_data["semester"],
        credits=course_data["credits"],
        instructor=course_data["instructor"],
        metadata=EventMetadata(
            source_service="schedule-service",
            user_id=current_user.id
        )
    )
    await publisher.publish(event)
```

### In Note-Taking Service (Consumer)

```python
from vertector_nats import (
    NATSClient,
    EventConsumer,
    ConsumerConfig,
    BaseEvent,
)
from nats.aio.msg import Msg

# Handler function
async def handle_academic_event(event: BaseEvent, msg: Msg):
    if event.event_type == "academic.course.created":
        # Create notebook for new course
        await create_course_notebook(event.course_code)

    elif event.event_type == "academic.assignment.created":
        # Link assignment to lecture notes
        await link_assignment_notes(
            event.course_code,
            event.assignment_id
        )

    await msg.ack()  # Acknowledge success

# Start consumer (e.g., in background task)
config = NATSConfig()
nats_client = NATSClient(config)
await nats_client.connect()

consumer_config = ConsumerConfig(
    durable_name="notes-service-consumer",
    filter_subjects=["academic.*"],
)

consumer = EventConsumer(
    client=nats_client,
    stream_name="ACADEMIC_EVENTS",
    consumer_config=consumer_config,
)

await consumer.subscribe(handle_academic_event)
```

## Step 5: Verify Everything Works

### Check NATS Streams

```bash
# Install NATS CLI (optional)
brew install nats-io/nats-tools/nats

# View streams
nats stream ls

# View stream details
nats stream info ACADEMIC_EVENTS
```

### Monitor Messages

```bash
# View NATS server stats
curl http://localhost:8222/varz | jq

# View JetStream stats
curl http://localhost:8222/jsz | jq
```

## Common Issues

### "Connection refused"
- Make sure NATS is running: `docker-compose ps nats`
- Check ports: `docker-compose logs nats`

### "Stream not found"
- The client automatically creates streams on first connection
- Ensure `enable_jetstream=True` in config

### Messages not being consumed
- Check consumer is running
- Verify subject filters match event types
- Check `nats consumer ls ACADEMIC_EVENTS`

## Next Steps

1. Read the full [README.md](README.md)
2. Review event schemas in `src/vertector_nats/events.py`
3. Customize configuration in `.env`
4. Integrate with your existing services

## Monitoring (Optional)

Start full monitoring stack:

```bash
# Start Prometheus + Grafana
docker-compose --profile monitoring up -d

# Access Grafana
open http://localhost:3000
# Login: admin/admin
```

---

Happy eventing! 🚀
