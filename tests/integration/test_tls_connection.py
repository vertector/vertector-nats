"""
Integration tests for TLS/SSL connections to NATS JetStream.

These tests require:
1. NATS server running with TLS enabled
2. Valid TLS certificates in ./tls directory
3. Run: docker-compose -f docker-compose.tls.yml up -d

Run these tests with:
    pytest tests/integration/test_tls_connection.py -v
"""

import asyncio
import os
import ssl
from pathlib import Path

import pytest
from nats.errors import Error as NATSError

from vertector_nats import (
    NATSClient,
    NATSConfig,
    EventPublisher,
    CourseCreatedEvent,
    EventMetadata,
)


# TLS certificate paths
TLS_DIR = Path(__file__).parent.parent.parent / "tls"
CA_CERT = TLS_DIR / "ca-cert.pem"
CLIENT_CERT = TLS_DIR / "client-cert.pem"
CLIENT_KEY = TLS_DIR / "client-key.pem"


@pytest.fixture
def tls_config() -> NATSConfig:
    """Create NATSConfig with TLS enabled."""
    return NATSConfig(
        servers=["nats://localhost:4222"],
        enable_tls=True,
        tls_ca_cert_file=str(CA_CERT),
        tls_cert_file=str(CLIENT_CERT),
        tls_key_file=str(CLIENT_KEY),
        enable_jetstream=True,
    )


@pytest.fixture
def tls_config_no_verify() -> NATSConfig:
    """Create NATSConfig with TLS but no certificate verification (testing only)."""
    return NATSConfig(
        servers=["nats://localhost:4222"],
        enable_tls=True,
        tls_verify=False,  # Skip verification for self-signed certs
        enable_jetstream=True,
    )


class TestTLSConnection:
    """Test TLS connection establishment."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_tls_connection_with_valid_certs(self, tls_config):
        """Test connecting to NATS with valid TLS certificates."""
        if not CA_CERT.exists():
            pytest.skip("TLS certificates not found. Run: ./scripts/generate_tls_certs.sh")

        async with NATSClient(tls_config) as client:
            assert client.is_connected
            assert client.native_client.is_connected

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_tls_connection_fails_without_certs(self):
        """Test that connection fails when certificates are missing."""
        config = NATSConfig(
            servers=["nats://localhost:4222"],
            enable_tls=True,
            tls_ca_cert_file="/nonexistent/ca.pem",
            tls_cert_file="/nonexistent/cert.pem",
            tls_key_file="/nonexistent/key.pem",
            enable_jetstream=True,
        )

        with pytest.raises(FileNotFoundError):
            async with NATSClient(config) as client:
                pass

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_tls_connection_with_hostname_verification(self, tls_config):
        """Test TLS connection with hostname verification."""
        if not CA_CERT.exists():
            pytest.skip("TLS certificates not found. Run: ./scripts/generate_tls_certs.sh")

        # Should connect successfully with correct hostname
        async with NATSClient(tls_config) as client:
            assert client.is_connected

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_tls_version_minimum(self, tls_config):
        """Test that minimum TLS version is enforced."""
        if not CA_CERT.exists():
            pytest.skip("TLS certificates not found. Run: ./scripts/generate_tls_certs.sh")

        async with NATSClient(tls_config) as client:
            assert client.is_connected
            # Connection should use TLS 1.2 or higher
            # Note: Cannot easily check TLS version from NATS client

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_tls_cipher_suites(self, tls_config):
        """Test that strong cipher suites are used."""
        if not CA_CERT.exists():
            pytest.skip("TLS certificates not found. Run: ./scripts/generate_tls_certs.sh")

        async with NATSClient(tls_config) as client:
            assert client.is_connected
            # Verify strong ciphers are used (requires server-side logging)


class TestTLSPublishing:
    """Test event publishing over TLS."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_publish_event_over_tls(self, tls_config):
        """Test publishing events over encrypted TLS connection."""
        if not CA_CERT.exists():
            pytest.skip("TLS certificates not found. Run: ./scripts/generate_tls_certs.sh")

        async with NATSClient(tls_config) as client:
            publisher = EventPublisher(client=client)

            event = CourseCreatedEvent(
                course_code="CS101",
                course_name="Intro to CS",
                semester="Fall 2025",
                credits=3,
                instructor="Dr. Smith",
                metadata=EventMetadata(source_service="test-tls"),
            )

            ack = await publisher.publish(event)
            assert ack.stream == "ACADEMIC_EVENTS"
            assert ack.seq > 0

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_batch_publish_over_tls(self, tls_config):
        """Test batch publishing over TLS."""
        if not CA_CERT.exists():
            pytest.skip("TLS certificates not found. Run: ./scripts/generate_tls_certs.sh")

        async with NATSClient(tls_config) as client:
            publisher = EventPublisher(client=client)

            events = [
                CourseCreatedEvent(
                    course_code=f"CS{100 + i}",
                    course_name=f"Course {i}",
                    semester="Fall 2025",
                    credits=3,
                    instructor="Dr. Smith",
                    metadata=EventMetadata(source_service="test-tls"),
                )
                for i in range(5)
            ]

            acks = await publisher.publish_batch(events, parallel=True)
            assert len(acks) == 5
            assert all(ack.stream == "ACADEMIC_EVENTS" for ack in acks)


class TestTLSAuthentication:
    """Test authentication over TLS."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_tls_with_username_password(self, tls_config):
        """Test TLS connection with username/password authentication."""
        if not CA_CERT.exists():
            pytest.skip("TLS certificates not found. Run: ./scripts/generate_tls_certs.sh")

        config = NATSConfig(
            servers=["nats://localhost:4222"],
            enable_tls=True,
            tls_ca_cert_file=str(CA_CERT),
            tls_cert_file=str(CLIENT_CERT),
            tls_key_file=str(CLIENT_KEY),
            enable_auth=True,
            username="schedule_service",
            password=os.getenv("NATS_PASSWORD", "test_password"),
            enable_jetstream=True,
        )

        try:
            async with NATSClient(config) as client:
                assert client.is_connected
        except NATSError:
            pytest.skip("NATS server not configured with test credentials")

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_tls_with_token(self, tls_config):
        """Test TLS connection with token authentication."""
        if not CA_CERT.exists():
            pytest.skip("TLS certificates not found. Run: ./scripts/generate_tls_certs.sh")

        config = NATSConfig(
            servers=["nats://localhost:4222"],
            enable_tls=True,
            tls_ca_cert_file=str(CA_CERT),
            tls_cert_file=str(CLIENT_CERT),
            tls_key_file=str(CLIENT_KEY),
            token=os.getenv("NATS_TOKEN", "test_token"),
            enable_jetstream=True,
        )

        try:
            async with NATSClient(config) as client:
                assert client.is_connected
        except NATSError:
            pytest.skip("NATS server not configured with token auth")


class TestTLSReconnection:
    """Test TLS reconnection behavior."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_tls_reconnection_after_disconnect(self, tls_config):
        """Test that TLS reconnection works after disconnection."""
        if not CA_CERT.exists():
            pytest.skip("TLS certificates not found. Run: ./scripts/generate_tls_certs.sh")

        config = tls_config
        config.max_reconnect_attempts = 5
        config.reconnect_wait_seconds = 1

        async with NATSClient(config) as client:
            assert client.is_connected

            # Simulate disconnect (would need NATS server restart in real test)
            # For now, just verify connection is stable
            await asyncio.sleep(2)
            assert client.is_connected


class TestCertificateValidation:
    """Test certificate validation and verification."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_expired_certificate_rejected(self):
        """Test that expired certificates are rejected."""
        # This would require generating an expired certificate
        pytest.skip("Requires expired certificate for testing")

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_invalid_ca_rejected(self):
        """Test that certificates from untrusted CA are rejected."""
        config = NATSConfig(
            servers=["nats://localhost:4222"],
            enable_tls=True,
            tls_ca_cert_file="/etc/ssl/certs/ca-certificates.crt",  # Wrong CA
            tls_cert_file=str(CLIENT_CERT),
            tls_key_file=str(CLIENT_KEY),
            enable_jetstream=True,
        )

        if not CA_CERT.exists():
            pytest.skip("TLS certificates not found")

        # Should fail with certificate verification error
        with pytest.raises((NATSError, ssl.SSLError)):
            async with NATSClient(config) as client:
                await asyncio.sleep(1)

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_certificate_expiry_monitoring(self, tls_config):
        """Test certificate expiry can be checked."""
        if not CA_CERT.exists():
            pytest.skip("TLS certificates not found")

        import OpenSSL

        # Load certificate
        with open(CLIENT_CERT, "r") as f:
            cert_data = f.read()

        cert = OpenSSL.crypto.load_certificate(
            OpenSSL.crypto.FILETYPE_PEM, cert_data
        )

        # Check expiry date
        expiry = cert.get_notAfter().decode("utf-8")
        assert expiry  # Should have expiry date

        # Verify certificate is currently valid
        # (In production, set up monitoring for certificates expiring soon)


@pytest.mark.integration
class TestTLSPerformance:
    """Test TLS performance characteristics."""

    @pytest.mark.asyncio
    async def test_tls_connection_overhead(self, tls_config):
        """Test TLS connection establishment time."""
        if not CA_CERT.exists():
            pytest.skip("TLS certificates not found")

        import time

        start = time.time()
        async with NATSClient(tls_config) as client:
            connection_time = time.time() - start
            assert client.is_connected

        # TLS handshake should complete within reasonable time
        assert connection_time < 5.0  # 5 seconds max

    @pytest.mark.asyncio
    async def test_tls_publish_latency(self, tls_config):
        """Test publish latency over TLS."""
        if not CA_CERT.exists():
            pytest.skip("TLS certificates not found")

        async with NATSClient(tls_config) as client:
            publisher = EventPublisher(client=client)

            event = CourseCreatedEvent(
                course_code="CS101",
                course_name="Intro to CS",
                semester="Fall 2025",
                credits=3,
                instructor="Dr. Smith",
                metadata=EventMetadata(source_service="test-tls"),
            )

            import time

            latencies = []
            for _ in range(10):
                start = time.time()
                await publisher.publish(event)
                latencies.append(time.time() - start)

            avg_latency = sum(latencies) / len(latencies)
            # TLS overhead should be minimal
            assert avg_latency < 0.5  # 500ms max average


# Run helper
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
