# GEMINI.md

This file provides context for Gemini to understand the `vertector-nats-jetstream` project.

## Project Overview

This project is a Python library that provides a production-ready client for [NATS JetStream](https://docs.nats.io/nats-concepts/jetstream). It is designed for event-driven microservice communication within an academic context, such as managing course schedules, assignments, and student data.

The library is built on top of the official `nats-py` library and provides a higher-level abstraction for publishing and consuming events. It includes features like:

*   **Type-safe events:** Event payloads are defined using Pydantic models, ensuring data consistency.
*   **Configuration management:** The client is configured using a `NATSConfig` object, which can be populated from environment variables or a `.env` file.
*   **Resilience:** The client includes automatic reconnection with exponential backoff.
*   **Observability:** The library has hooks for OpenTelemetry tracing and Prometheus metrics.
*   **Ease of use:** High-level `EventPublisher` and `EventConsumer` classes simplify the process of publishing and consuming events.

## Building and Running

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

### Running the NATS Server

A Docker Compose file is provided to run a NATS server with JetStream enabled:

```bash
docker-compose up -d nats
```

### Running Tests

The project has a comprehensive test suite using `pytest`.

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src/vertector_nats --cov-report=html
```

### Running Examples

The `examples/` directory contains example scripts for publishing and consuming events.

```bash
# Terminal 1: Start consumer
python examples/consumer_example.py

# Terminal 2: Publish events
python examples/publisher_example.py
```

## Development Conventions

*   **Code Style:** The project uses `black` for code formatting and `ruff` for linting and import sorting.
*   **Type Hinting:** The codebase is fully type-hinted and checked with `mypy`.
*   **Commit Messages:** Commit messages should follow the [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/) specification.
*   **Branching:** Feature branches should be created from the `main` branch.
*   **Pull Requests:** Pull requests should be used to merge changes into the `main` branch.
