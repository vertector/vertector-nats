#!/usr/bin/env python3
"""
Delete the old consumer so it can be recreated with the new filter
"""
import asyncio
from nats.aio.client import Client as NATS
from nats.js import JetStreamContext


async def main():
    nc = NATS()

    # Connect to NATS
    await nc.connect(servers=["nats://localhost:4222"])
    print("✓ Connected to NATS")

    # Get JetStream context
    js = nc.jetstream()

    # Delete the consumer
    stream_name = "ACADEMIC_EVENTS"
    consumer_name = "graphrag-note-service-consumer-v2"

    try:
        await js.delete_consumer(stream_name, consumer_name)
        print(f"✓ Deleted consumer: {consumer_name} from stream: {stream_name}")
    except Exception as e:
        print(f"Error deleting consumer: {e}")

    # Close connection
    await nc.close()
    print("✓ Disconnected from NATS")


if __name__ == "__main__":
    asyncio.run(main())
