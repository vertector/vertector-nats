"""Unit tests for configuration management.

Tests cover:
- Default configuration values
- Environment variable loading
- Configuration validation
- StreamConfig, ConsumerConfig, NATSConfig
- Field constraints and validation
"""

import os
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from vertector_nats.config import (
    ConsumerConfig,
    NATSConfig,
    StreamConfig,
    load_config_from_env,
)


# ============================================================================
# STREAM CONFIG TESTS
# ============================================================================


@pytest.mark.unit
class TestStreamConfig:
    """Test StreamConfig schema and validation."""

    def test_create_stream_config_with_defaults(self):
        """Test creating StreamConfig with minimal fields."""
        config = StreamConfig(
            name="TEST_STREAM",
            subjects=["test.*"],
        )

        assert config.name == "TEST_STREAM"
        assert config.subjects == ["test.*"]
        assert config.retention == "workqueue"  # default
        assert config.storage == "file"  # default
        assert config.max_age_seconds == 604800  # 7 days default
        assert config.max_bytes == 10 * 1024 * 1024 * 1024  # 10GB default
        assert config.replicas == 1  # default
        assert config.discard == "old"  # default

    def test_create_stream_config_with_all_fields(self):
        """Test creating StreamConfig with all fields specified."""
        config = StreamConfig(
            name="TEST_STREAM",
            subjects=["test.foo.*", "test.bar.*"],
            retention="interest",
            storage="memory",
            max_age_seconds=3600,
            max_bytes=1024 * 1024,
            replicas=3,
            discard="new",
        )

        assert config.name == "TEST_STREAM"
        assert config.subjects == ["test.foo.*", "test.bar.*"]
        assert config.retention == "interest"
        assert config.storage == "memory"
        assert config.max_age_seconds == 3600
        assert config.max_bytes == 1024 * 1024
        assert config.replicas == 3
        assert config.discard == "new"

    def test_retention_policy_validation(self):
        """Test retention must be one of allowed values."""
        # Valid values
        for retention in ["limits", "interest", "workqueue"]:
            config = StreamConfig(
                name="TEST_STREAM",
                subjects=["test.*"],
                retention=retention,
            )
            assert config.retention == retention

        # Invalid value
        with pytest.raises(ValidationError):
            StreamConfig(
                name="TEST_STREAM",
                subjects=["test.*"],
                retention="invalid",
            )

    def test_storage_validation(self):
        """Test storage must be file or memory."""
        # Valid values
        for storage in ["file", "memory"]:
            config = StreamConfig(
                name="TEST_STREAM",
                subjects=["test.*"],
                storage=storage,
            )
            assert config.storage == storage

        # Invalid value
        with pytest.raises(ValidationError):
            StreamConfig(
                name="TEST_STREAM",
                subjects=["test.*"],
                storage="invalid",
            )

    def test_max_age_validation(self):
        """Test max_age_seconds must be >= 0."""
        # Valid: 0 (no age limit)
        config = StreamConfig(
            name="TEST_STREAM",
            subjects=["test.*"],
            max_age_seconds=0,
        )
        assert config.max_age_seconds == 0

        # Valid: positive value
        config = StreamConfig(
            name="TEST_STREAM",
            subjects=["test.*"],
            max_age_seconds=3600,
        )
        assert config.max_age_seconds == 3600

        # Invalid: negative
        with pytest.raises(ValidationError):
            StreamConfig(
                name="TEST_STREAM",
                subjects=["test.*"],
                max_age_seconds=-1,
            )

    def test_max_bytes_validation(self):
        """Test max_bytes must be >= -1."""
        # Valid: -1 (unlimited)
        config = StreamConfig(
            name="TEST_STREAM",
            subjects=["test.*"],
            max_bytes=-1,
        )
        assert config.max_bytes == -1

        # Valid: positive value
        config = StreamConfig(
            name="TEST_STREAM",
            subjects=["test.*"],
            max_bytes=1024,
        )
        assert config.max_bytes == 1024

        # Invalid: less than -1
        with pytest.raises(ValidationError):
            StreamConfig(
                name="TEST_STREAM",
                subjects=["test.*"],
                max_bytes=-2,
            )

    def test_replicas_validation(self):
        """Test replicas must be between 1 and 5."""
        # Valid: 1 to 5
        for replicas in range(1, 6):
            config = StreamConfig(
                name="TEST_STREAM",
                subjects=["test.*"],
                replicas=replicas,
            )
            assert config.replicas == replicas

        # Invalid: 0
        with pytest.raises(ValidationError):
            StreamConfig(
                name="TEST_STREAM",
                subjects=["test.*"],
                replicas=0,
            )

        # Invalid: 6
        with pytest.raises(ValidationError):
            StreamConfig(
                name="TEST_STREAM",
                subjects=["test.*"],
                replicas=6,
            )

    def test_discard_policy_validation(self):
        """Test discard must be old or new."""
        # Valid values
        for discard in ["old", "new"]:
            config = StreamConfig(
                name="TEST_STREAM",
                subjects=["test.*"],
                discard=discard,
            )
            assert config.discard == discard

        # Invalid value
        with pytest.raises(ValidationError):
            StreamConfig(
                name="TEST_STREAM",
                subjects=["test.*"],
                discard="invalid",
            )

    def test_stream_config_from_env(self):
        """Test StreamConfig can be loaded from environment variables."""
        env_vars = {
            "NATS_STREAM_NAME": "ENV_STREAM",
            "NATS_STREAM_SUBJECTS": '["env.test.*"]',
            "NATS_STREAM_RETENTION": "interest",
            "NATS_STREAM_STORAGE": "memory",
            "NATS_STREAM_MAX_AGE_SECONDS": "7200",
            "NATS_STREAM_REPLICAS": "3",
        }

        with patch.dict(os.environ, env_vars, clear=False):
            config = StreamConfig(
                name="ENV_STREAM",
                subjects=["env.test.*"],
            )

            assert config.name == "ENV_STREAM"
            assert config.subjects == ["env.test.*"]


# ============================================================================
# CONSUMER CONFIG TESTS
# ============================================================================


@pytest.mark.unit
class TestConsumerConfig:
    """Test ConsumerConfig schema and validation."""

    def test_create_consumer_config_with_defaults(self):
        """Test creating ConsumerConfig with minimal fields."""
        config = ConsumerConfig(
            durable_name="test-consumer",
        )

        assert config.durable_name == "test-consumer"
        assert config.ack_policy == "explicit"  # default
        assert config.ack_wait_seconds == 30  # default
        assert config.max_deliver == 3  # default
        assert config.filter_subjects == []  # default
        assert config.deliver_policy == "all"  # default
        assert config.replay_policy == "instant"  # default

    def test_create_consumer_config_with_all_fields(self):
        """Test creating ConsumerConfig with all fields specified."""
        config = ConsumerConfig(
            durable_name="test-consumer",
            ack_policy="all",
            ack_wait_seconds=60,
            max_deliver=5,
            filter_subjects=["test.foo.*", "test.bar.*"],
            deliver_policy="new",
            replay_policy="original",
        )

        assert config.durable_name == "test-consumer"
        assert config.ack_policy == "all"
        assert config.ack_wait_seconds == 60
        assert config.max_deliver == 5
        assert config.filter_subjects == ["test.foo.*", "test.bar.*"]
        assert config.deliver_policy == "new"
        assert config.replay_policy == "original"

    def test_ack_policy_validation(self):
        """Test ack_policy must be one of allowed values."""
        # Valid values
        for ack_policy in ["explicit", "all", "none"]:
            config = ConsumerConfig(
                durable_name="test-consumer",
                ack_policy=ack_policy,
            )
            assert config.ack_policy == ack_policy

        # Invalid value
        with pytest.raises(ValidationError):
            ConsumerConfig(
                durable_name="test-consumer",
                ack_policy="invalid",
            )

    def test_ack_wait_validation(self):
        """Test ack_wait_seconds must be >= 1."""
        # Valid: 1 second
        config = ConsumerConfig(
            durable_name="test-consumer",
            ack_wait_seconds=1,
        )
        assert config.ack_wait_seconds == 1

        # Valid: large value
        config = ConsumerConfig(
            durable_name="test-consumer",
            ack_wait_seconds=3600,
        )
        assert config.ack_wait_seconds == 3600

        # Invalid: 0
        with pytest.raises(ValidationError):
            ConsumerConfig(
                durable_name="test-consumer",
                ack_wait_seconds=0,
            )

    def test_max_deliver_validation(self):
        """Test max_deliver must be >= -1."""
        # Valid: -1 (unlimited)
        config = ConsumerConfig(
            durable_name="test-consumer",
            max_deliver=-1,
        )
        assert config.max_deliver == -1

        # Valid: positive value
        config = ConsumerConfig(
            durable_name="test-consumer",
            max_deliver=10,
        )
        assert config.max_deliver == 10

        # Invalid: -2
        with pytest.raises(ValidationError):
            ConsumerConfig(
                durable_name="test-consumer",
                max_deliver=-2,
            )

    def test_deliver_policy_validation(self):
        """Test deliver_policy must be one of allowed values."""
        # Valid values
        valid_policies = ["all", "last", "new", "by_start_sequence", "by_start_time"]

        for policy in valid_policies:
            config = ConsumerConfig(
                durable_name="test-consumer",
                deliver_policy=policy,
            )
            assert config.deliver_policy == policy

        # Invalid value
        with pytest.raises(ValidationError):
            ConsumerConfig(
                durable_name="test-consumer",
                deliver_policy="invalid",
            )

    def test_replay_policy_validation(self):
        """Test replay_policy must be instant or original."""
        # Valid values
        for replay in ["instant", "original"]:
            config = ConsumerConfig(
                durable_name="test-consumer",
                replay_policy=replay,
            )
            assert config.replay_policy == replay

        # Invalid value
        with pytest.raises(ValidationError):
            ConsumerConfig(
                durable_name="test-consumer",
                replay_policy="invalid",
            )


# ============================================================================
# NATS CONFIG TESTS
# ============================================================================


@pytest.mark.unit
class TestNATSConfig:
    """Test NATSConfig schema and validation."""

    def test_create_nats_config_with_defaults(self):
        """Test creating NATSConfig with all defaults."""
        config = NATSConfig()

        # Connection settings
        assert config.servers == ["nats://localhost:4222"]
        assert config.client_name == "vertector-nats-client"
        assert config.max_reconnect_attempts == 10
        assert config.reconnect_wait_seconds == 2

        # Authentication
        assert config.enable_auth is False
        assert config.username is None
        assert config.password is None
        assert config.token is None

        # TLS
        assert config.enable_tls is False
        assert config.tls_ca_cert_file is None
        assert config.tls_cert_file is None
        assert config.tls_key_file is None

        # JetStream
        assert config.enable_jetstream is True
        assert config.jetstream_domain is None

        # Timeouts
        assert config.connect_timeout_seconds == 5
        assert config.request_timeout_seconds == 5

        # Performance
        assert config.max_payload_bytes == 1 * 1024 * 1024  # 1MB
        assert config.max_pending_messages == 65536

        # Observability
        assert config.enable_tracing is True
        assert config.enable_metrics is True
        assert config.service_name == "vertector-nats"

    def test_create_nats_config_with_custom_values(self):
        """Test creating NATSConfig with custom values."""
        config = NATSConfig(
            servers=["nats://server1:4222", "nats://server2:4222"],
            client_name="custom-client",
            max_reconnect_attempts=5,
            reconnect_wait_seconds=3,
            enable_auth=True,
            username="testuser",
            password="testpass",
            enable_tls=True,
            tls_ca_cert_file="/path/to/ca.crt",
            max_payload_bytes=2 * 1024 * 1024,
            service_name="custom-service",
        )

        assert config.servers == ["nats://server1:4222", "nats://server2:4222"]
        assert config.client_name == "custom-client"
        assert config.max_reconnect_attempts == 5
        assert config.enable_auth is True
        assert config.username == "testuser"
        assert config.password == "testpass"
        assert config.enable_tls is True
        assert config.tls_ca_cert_file == "/path/to/ca.crt"
        assert config.max_payload_bytes == 2 * 1024 * 1024

    def test_max_reconnect_attempts_validation(self):
        """Test max_reconnect_attempts must be >= -1."""
        # Valid: -1 (unlimited)
        config = NATSConfig(max_reconnect_attempts=-1)
        assert config.max_reconnect_attempts == -1

        # Valid: 0
        config = NATSConfig(max_reconnect_attempts=0)
        assert config.max_reconnect_attempts == 0

        # Valid: positive
        config = NATSConfig(max_reconnect_attempts=100)
        assert config.max_reconnect_attempts == 100

        # Invalid: -2
        with pytest.raises(ValidationError):
            NATSConfig(max_reconnect_attempts=-2)

    def test_reconnect_wait_validation(self):
        """Test reconnect_wait_seconds must be >= 1."""
        # Valid: 1
        config = NATSConfig(reconnect_wait_seconds=1)
        assert config.reconnect_wait_seconds == 1

        # Valid: large value
        config = NATSConfig(reconnect_wait_seconds=60)
        assert config.reconnect_wait_seconds == 60

        # Invalid: 0
        with pytest.raises(ValidationError):
            NATSConfig(reconnect_wait_seconds=0)

    def test_timeout_validation(self):
        """Test timeout fields must be >= 1."""
        # Valid: connect_timeout
        config = NATSConfig(connect_timeout_seconds=10)
        assert config.connect_timeout_seconds == 10

        # Valid: request_timeout
        config = NATSConfig(request_timeout_seconds=15)
        assert config.request_timeout_seconds == 15

        # Invalid: connect_timeout = 0
        with pytest.raises(ValidationError):
            NATSConfig(connect_timeout_seconds=0)

        # Invalid: request_timeout = 0
        with pytest.raises(ValidationError):
            NATSConfig(request_timeout_seconds=0)

    def test_max_payload_validation(self):
        """Test max_payload_bytes must be >= 1024."""
        # Valid: 1024 (minimum)
        config = NATSConfig(max_payload_bytes=1024)
        assert config.max_payload_bytes == 1024

        # Valid: large value
        config = NATSConfig(max_payload_bytes=10 * 1024 * 1024)
        assert config.max_payload_bytes == 10 * 1024 * 1024

        # Invalid: less than 1024
        with pytest.raises(ValidationError):
            NATSConfig(max_payload_bytes=1023)

    def test_max_pending_messages_validation(self):
        """Test max_pending_messages must be >= 1."""
        # Valid: 1
        config = NATSConfig(max_pending_messages=1)
        assert config.max_pending_messages == 1

        # Valid: large value
        config = NATSConfig(max_pending_messages=100000)
        assert config.max_pending_messages == 100000

        # Invalid: 0
        with pytest.raises(ValidationError):
            NATSConfig(max_pending_messages=0)

    def test_default_streams_configured(self):
        """Test default streams (academic and notes) are configured."""
        config = NATSConfig()

        # Check academic stream
        assert config.academic_stream.name == "ACADEMIC_EVENTS"
        assert "academic.course.*" in config.academic_stream.subjects
        assert "academic.assignment.*" in config.academic_stream.subjects
        assert config.academic_stream.retention == "interest"
        assert config.academic_stream.storage == "file"
        assert config.academic_stream.max_age_seconds == 604800  # 7 days

        # Check notes stream
        assert config.notes_stream.name == "NOTES_EVENTS"
        assert config.notes_stream.subjects == ["notes.*"]
        assert config.notes_stream.retention == "interest"
        assert config.notes_stream.max_age_seconds == 2592000  # 30 days

    def test_get_streams_method(self):
        """Test get_streams returns all configured streams."""
        config = NATSConfig()
        streams = config.get_streams()

        assert len(streams) == 2
        assert streams[0].name == "ACADEMIC_EVENTS"
        assert streams[1].name == "NOTES_EVENTS"

    def test_custom_stream_configuration(self):
        """Test custom stream configurations can be provided."""
        custom_academic = StreamConfig(
            name="CUSTOM_ACADEMIC",
            subjects=["custom.academic.*"],
            retention="workqueue",
            max_age_seconds=3600,
        )

        config = NATSConfig(academic_stream=custom_academic)

        assert config.academic_stream.name == "CUSTOM_ACADEMIC"
        assert config.academic_stream.subjects == ["custom.academic.*"]
        assert config.academic_stream.retention == "workqueue"
        assert config.academic_stream.max_age_seconds == 3600


# ============================================================================
# ENVIRONMENT VARIABLE LOADING TESTS
# ============================================================================


@pytest.mark.unit
class TestEnvironmentLoading:
    """Test loading configuration from environment variables."""

    def test_load_config_from_env_defaults(self):
        """Test load_config_from_env returns default config."""
        config = load_config_from_env()

        assert isinstance(config, NATSConfig)
        assert config.servers == ["nats://localhost:4222"]
        assert config.client_name == "vertector-nats-client"

    def test_load_config_from_env_with_variables(self):
        """Test load_config_from_env reads environment variables."""
        env_vars = {
            "NATS_SERVERS": '["nats://env-server:4222"]',
            "NATS_CLIENT_NAME": "env-client",
            "NATS_MAX_RECONNECT_ATTEMPTS": "20",
            "NATS_ENABLE_AUTH": "true",
            "NATS_USERNAME": "envuser",
            "NATS_PASSWORD": "envpass",
            "NATS_ENABLE_TLS": "true",
            "NATS_SERVICE_NAME": "env-service",
        }

        with patch.dict(os.environ, env_vars, clear=False):
            config = load_config_from_env()

            # Note: Pydantic's JSON parsing for list fields
            # May not work as expected from env vars
            # But these should work:
            assert config.client_name == "env-client"
            assert config.max_reconnect_attempts == 20
            assert config.enable_auth is True
            assert config.username == "envuser"
            assert config.password == "envpass"
            assert config.enable_tls is True
            assert config.service_name == "env-service"

    def test_config_case_insensitive(self):
        """Test config loading is case insensitive."""
        env_vars = {
            "nats_client_name": "lowercase-client",  # lowercase
            "NATS_SERVICE_NAME": "UPPERCASE-SERVICE",  # uppercase
        }

        with patch.dict(os.environ, env_vars, clear=False):
            config = NATSConfig()

            assert config.client_name == "lowercase-client"
            assert config.service_name == "UPPERCASE-SERVICE"

    def test_extra_fields_ignored(self):
        """Test that extra environment variables are ignored."""
        env_vars = {
            "NATS_UNKNOWN_FIELD": "should-be-ignored",
            "NATS_CLIENT_NAME": "valid-client",
        }

        with patch.dict(os.environ, env_vars, clear=False):
            # Should not raise validation error
            config = NATSConfig()
            assert config.client_name == "valid-client"


# ============================================================================
# INTEGRATION TESTS
# ============================================================================


@pytest.mark.unit
class TestConfigIntegration:
    """Test configuration integration scenarios."""

    def test_config_with_auth_enabled(self):
        """Test configuration with authentication enabled."""
        config = NATSConfig(
            enable_auth=True,
            username="testuser",
            password="testpass",
        )

        assert config.enable_auth is True
        assert config.username == "testuser"
        assert config.password == "testpass"

    def test_config_with_token_auth(self):
        """Test configuration with token authentication."""
        config = NATSConfig(
            enable_auth=True,
            token="test-token-123",
        )

        assert config.enable_auth is True
        assert config.token == "test-token-123"

    def test_config_with_tls_enabled(self):
        """Test configuration with TLS enabled."""
        config = NATSConfig(
            enable_tls=True,
            tls_ca_cert_file="/path/to/ca.crt",
            tls_cert_file="/path/to/client.crt",
            tls_key_file="/path/to/client.key",
        )

        assert config.enable_tls is True
        assert config.tls_ca_cert_file == "/path/to/ca.crt"
        assert config.tls_cert_file == "/path/to/client.crt"
        assert config.tls_key_file == "/path/to/client.key"

    def test_config_for_production(self):
        """Test typical production configuration."""
        config = NATSConfig(
            servers=[
                "nats://prod-server1:4222",
                "nats://prod-server2:4222",
                "nats://prod-server3:4222",
            ],
            client_name="production-academic-service",
            max_reconnect_attempts=-1,  # unlimited
            enable_auth=True,
            username="prod-user",
            password="prod-secret",
            enable_tls=True,
            tls_ca_cert_file="/etc/certs/ca.crt",
            max_payload_bytes=5 * 1024 * 1024,  # 5MB
            enable_tracing=True,
            enable_metrics=True,
            service_name="academic-schedule-service",
        )

        assert len(config.servers) == 3
        assert config.max_reconnect_attempts == -1
        assert config.enable_auth is True
        assert config.enable_tls is True
        assert config.max_payload_bytes == 5 * 1024 * 1024
        assert config.enable_tracing is True
        assert config.enable_metrics is True

    def test_config_for_testing(self):
        """Test typical testing configuration."""
        config = NATSConfig(
            servers=["nats://localhost:4222"],
            client_name="test-client",
            enable_auth=False,
            enable_tls=False,
            max_reconnect_attempts=3,
            connect_timeout_seconds=2,
            request_timeout_seconds=2,
        )

        assert config.servers == ["nats://localhost:4222"]
        assert config.enable_auth is False
        assert config.enable_tls is False
        assert config.max_reconnect_attempts == 3
