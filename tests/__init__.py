"""Test suite for vertector-nats-jetstream.

This package contains unit and integration tests for the NATS JetStream implementation.

Test Structure:
- test_events.py - Event schema validation and serialization tests
- test_config.py - Configuration loading and validation tests
- test_publisher.py - Publisher unit and integration tests
- test_consumer.py - Consumer unit and integration tests
- test_client.py - Client connection and stream management tests
- test_metrics.py - Prometheus metrics tests
- conftest.py - Shared fixtures and test configuration

Running Tests:
    # Run all tests
    pytest

    # Run with coverage
    pytest --cov=vertector_nats --cov-report=html

    # Run only unit tests (no NATS server required)
    pytest -m unit

    # Run only integration tests (requires NATS server)
    pytest -m integration

    # Run specific test file
    pytest tests/test_events.py
"""
