"""Configuration management for NATS JetStream client.

Pydantic-based configuration with environment variable support,
following the same patterns as vertector-scylladbstore.
"""

from typing import Literal, Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class StreamConfig(BaseSettings):
    """Configuration for a JetStream stream."""

    model_config = SettingsConfigDict(
        env_prefix="NATS_STREAM_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    name: str = Field(description="Stream name")
    subjects: list[str] = Field(description="List of subjects this stream captures")
    retention: Literal["limits", "interest", "workqueue"] = Field(
        default="workqueue",
        description="Message retention policy",
    )
    storage: Literal["file", "memory"] = Field(
        default="file",
        description="Storage backend for messages",
    )
    max_age_seconds: int = Field(
        default=604800,  # 7 days
        description="Maximum age of messages in seconds",
        ge=0,
    )
    max_bytes: int = Field(
        default=10 * 1024 * 1024 * 1024,  # 10GB
        description="Maximum size of the stream in bytes",
        ge=-1,
    )
    replicas: int = Field(
        default=1,
        description="Number of stream replicas for high availability",
        ge=1,
        le=5,
    )
    discard: Literal["old", "new"] = Field(
        default="old",
        description="Discard policy when limits are reached",
    )


class ConsumerConfig(BaseSettings):
    """Configuration for a JetStream consumer."""

    model_config = SettingsConfigDict(
        env_prefix="NATS_CONSUMER_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    durable_name: str = Field(description="Durable consumer name")
    ack_policy: Literal["explicit", "all", "none"] = Field(
        default="explicit",
        description="Acknowledgment policy",
    )
    ack_wait_seconds: int = Field(
        default=30,
        description="Time to wait for acknowledgment before redelivery",
        ge=1,
    )
    max_deliver: int = Field(
        default=3,
        description="Maximum number of delivery attempts",
        ge=-1,
    )
    filter_subjects: list[str] = Field(
        default_factory=list,
        description="Filter messages by subject patterns",
    )
    deliver_policy: Literal["all", "last", "new", "by_start_sequence", "by_start_time"] = Field(
        default="all",
        description="Where to start delivering messages from",
    )
    replay_policy: Literal["instant", "original"] = Field(
        default="instant",
        description="Replay messages at original speed or instantly",
    )


class NATSConfig(BaseSettings):
    """Main NATS client configuration.

    Load from environment variables with NATS_ prefix or from .env file.
    """

    model_config = SettingsConfigDict(
        env_prefix="NATS_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Connection settings
    servers: list[str] = Field(
        default=["nats://localhost:4222"],
        description="List of NATS server URLs",
    )
    client_name: str = Field(
        default="vertector-nats-client",
        description="Name of this NATS client",
    )
    max_reconnect_attempts: int = Field(
        default=10,
        description="Maximum number of reconnection attempts",
        ge=-1,
    )
    reconnect_wait_seconds: int = Field(
        default=2,
        description="Seconds to wait between reconnection attempts",
        ge=1,
    )

    # Authentication (optional)
    enable_auth: bool = Field(
        default=False,
        description="Enable username/password authentication",
    )
    username: Optional[str] = Field(
        default=None,
        description="Username for authentication",
    )
    password: Optional[str] = Field(
        default=None,
        description="Password for authentication",
    )
    token: Optional[str] = Field(
        default=None,
        description="Token for token-based authentication",
    )

    # TLS/SSL (optional)
    enable_tls: bool = Field(
        default=False,
        description="Enable TLS/SSL encryption",
    )
    tls_ca_cert_file: Optional[str] = Field(
        default=None,
        description="Path to CA certificate file",
    )
    tls_cert_file: Optional[str] = Field(
        default=None,
        description="Path to client certificate file",
    )
    tls_key_file: Optional[str] = Field(
        default=None,
        description="Path to client private key file",
    )

    # JetStream settings
    enable_jetstream: bool = Field(
        default=True,
        description="Enable JetStream",
    )
    jetstream_domain: Optional[str] = Field(
        default=None,
        description="JetStream domain name",
    )

    # Timeouts
    connect_timeout_seconds: int = Field(
        default=5,
        description="Connection timeout in seconds",
        ge=1,
    )
    request_timeout_seconds: int = Field(
        default=5,
        description="Request timeout in seconds",
        ge=1,
    )

    # Performance tuning
    max_payload_bytes: int = Field(
        default=1 * 1024 * 1024,  # 1MB
        description="Maximum payload size in bytes",
        ge=1024,
    )
    max_pending_messages: int = Field(
        default=65536,
        description="Maximum number of pending messages",
        ge=1,
    )

    # Observability
    enable_tracing: bool = Field(
        default=True,
        description="Enable OpenTelemetry tracing",
    )
    enable_metrics: bool = Field(
        default=True,
        description="Enable Prometheus metrics",
    )
    service_name: str = Field(
        default="vertector-nats",
        description="Service name for observability",
    )

    # Stream configurations
    academic_stream: StreamConfig = Field(
        default_factory=lambda: StreamConfig(
            name="ACADEMIC_EVENTS",
            subjects=[
                "academic.course.*",
                "academic.assignment.*",
                "academic.exam.*",
                "academic.quiz.*",
                "academic.lab.*",
                "academic.study.*",
                "academic.challenge.*",
                "academic.schedule.*",
            ],
            retention="interest",  # Changed from workqueue to allow multiple consumers
            storage="file",
            max_age_seconds=604800,  # 7 days
            replicas=1,
        ),
        description="Academic events stream configuration",
    )

    notes_stream: StreamConfig = Field(
        default_factory=lambda: StreamConfig(
            name="NOTES_EVENTS",
            subjects=["notes.*"],
            retention="interest",
            storage="file",
            max_age_seconds=2592000,  # 30 days
            replicas=1,
        ),
        description="Notes events stream configuration",
    )

    def get_streams(self) -> list[StreamConfig]:
        """Get all configured streams."""
        return [self.academic_stream, self.notes_stream]


def load_config_from_env() -> NATSConfig:
    """Load NATS configuration from environment variables.

    Returns:
        NATSConfig: Configured NATS settings

    Example:
        >>> config = load_config_from_env()
        >>> client = NATSClient(config)
    """
    return NATSConfig()
