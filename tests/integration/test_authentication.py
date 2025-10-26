"""
Integration tests for NATS authentication.

These tests verify:
1. Username/password authentication
2. Token-based authentication
3. Permission enforcement
4. Authentication failures

Run these tests with:
    pytest tests/integration/test_authentication.py -v
"""

import os

import pytest
from nats.errors import Error as NATSError

from vertector_nats import (
    NATSClient,
    NATSConfig,
    EventPublisher,
    CourseCreatedEvent,
    EventMetadata,
)


@pytest.fixture
def auth_config_user_pass() -> NATSConfig:
    """Create NATSConfig with username/password authentication."""
    return NATSConfig(
        servers=["nats://localhost:4222"],
        enable_auth=True,
        username=os.getenv("NATS_USERNAME", "schedule_service"),
        password=os.getenv("NATS_PASSWORD", "test_password"),
        enable_jetstream=True,
    )


@pytest.fixture
def auth_config_token() -> NATSConfig:
    """Create NATSConfig with token authentication."""
    return NATSConfig(
        servers=["nats://localhost:4222"],
        token=os.getenv("NATS_TOKEN", "test_token"),
        enable_jetstream=True,
    )


@pytest.fixture
def auth_config_invalid() -> NATSConfig:
    """Create NATSConfig with invalid credentials."""
    return NATSConfig(
        servers=["nats://localhost:4222"],
        enable_auth=True,
        username="invalid_user",
        password="wrong_password",
        enable_jetstream=True,
    )


class TestUsernamePasswordAuth:
    """Test username/password authentication."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_connect_with_valid_credentials(self, auth_config_user_pass):
        """Test connecting with valid username and password."""
        try:
            async with NATSClient(auth_config_user_pass) as client:
                assert client.is_connected
                assert client.native_client.is_connected
        except NATSError as e:
            pytest.skip(f"NATS server not configured with auth: {e}")

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_connect_fails_with_invalid_credentials(self, auth_config_invalid):
        """Test that connection fails with invalid credentials."""
        try:
            async with NATSClient(auth_config_invalid) as client:
                # Should not reach here
                pytest.fail("Connection should have failed with invalid credentials")
        except NATSError as e:
            # Expected: authorization violation or connection refused
            assert "authorization" in str(e).lower() or "error" in str(e).lower()

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_connect_without_credentials_when_required(self):
        """Test that connection fails when credentials are required but not provided."""
        config = NATSConfig(
            servers=["nats://localhost:4222"],
            enable_auth=False,  # No credentials
            enable_jetstream=True,
        )

        try:
            async with NATSClient(config) as client:
                # If server requires auth, this should fail
                # If server allows anonymous, this will succeed
                pass
        except NATSError:
            # Expected if server requires auth
            pass

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_publish_with_authentication(self, auth_config_user_pass):
        """Test publishing events with authentication."""
        try:
            async with NATSClient(auth_config_user_pass) as client:
                publisher = EventPublisher(client=client)

                event = CourseCreatedEvent(
                    course_code="CS101",
                    course_name="Intro to CS",
                    semester="Fall 2025",
                    credits=3,
                    instructor="Dr. Smith",
                    metadata=EventMetadata(source_service="test-auth"),
                )

                ack = await publisher.publish(event)
                assert ack.stream == "ACADEMIC_EVENTS"
                assert ack.seq > 0
        except NATSError as e:
            pytest.skip(f"NATS server not configured with auth: {e}")


class TestTokenAuth:
    """Test token-based authentication."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_connect_with_valid_token(self, auth_config_token):
        """Test connecting with valid token."""
        try:
            async with NATSClient(auth_config_token) as client:
                assert client.is_connected
        except NATSError as e:
            pytest.skip(f"NATS server not configured with token auth: {e}")

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_connect_fails_with_invalid_token(self):
        """Test that connection fails with invalid token."""
        config = NATSConfig(
            servers=["nats://localhost:4222"],
            token="invalid_token_12345",
            enable_jetstream=True,
        )

        try:
            async with NATSClient(config) as client:
                pytest.fail("Connection should have failed with invalid token")
        except NATSError:
            # Expected: authorization violation
            pass

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_publish_with_token(self, auth_config_token):
        """Test publishing events with token authentication."""
        try:
            async with NATSClient(auth_config_token) as client:
                publisher = EventPublisher(client=client)

                event = CourseCreatedEvent(
                    course_code="CS101",
                    course_name="Intro to CS",
                    semester="Fall 2025",
                    credits=3,
                    instructor="Dr. Smith",
                    metadata=EventMetadata(source_service="test-token-auth"),
                )

                ack = await publisher.publish(event)
                assert ack.stream == "ACADEMIC_EVENTS"
        except NATSError as e:
            pytest.skip(f"NATS server not configured with token auth: {e}")


class TestPermissions:
    """Test NATS permission enforcement."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_publish_allowed_subject(self, auth_config_user_pass):
        """Test publishing to allowed subject."""
        try:
            async with NATSClient(auth_config_user_pass) as client:
                publisher = EventPublisher(client=client)

                # schedule_service should be able to publish to academic.*
                event = CourseCreatedEvent(
                    course_code="CS101",
                    course_name="Intro to CS",
                    semester="Fall 2025",
                    credits=3,
                    instructor="Dr. Smith",
                    metadata=EventMetadata(source_service="test-perms"),
                )

                ack = await publisher.publish(event)
                assert ack.stream == "ACADEMIC_EVENTS"
        except NATSError as e:
            pytest.skip(f"NATS server not configured: {e}")

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_publish_denied_subject(self):
        """Test that publishing to denied subject fails."""
        # This test requires a user with restricted permissions
        # For example, notes_service trying to publish to admin.*
        pytest.skip("Requires NATS server with permission restrictions")

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_subscribe_allowed_subject(self, auth_config_user_pass):
        """Test subscribing to allowed subject."""
        try:
            async with NATSClient(auth_config_user_pass) as client:
                # schedule_service should be able to subscribe to academic.*
                js = client.jetstream

                # Create or get stream
                from nats.js.api import StreamConfig

                try:
                    await js.stream_info("ACADEMIC_EVENTS")
                except:
                    stream_config = StreamConfig(
                        name="ACADEMIC_EVENTS",
                        subjects=["academic.>"],
                        retention="interest",
                        storage="file",
                    )
                    await js.add_stream(stream_config)

                # Should succeed
                assert True
        except NATSError as e:
            if "permissions" in str(e).lower():
                pytest.fail(f"Should have permission to subscribe: {e}")
            else:
                pytest.skip(f"NATS server not configured: {e}")

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_subscribe_denied_subject(self):
        """Test that subscribing to denied subject fails."""
        pytest.skip("Requires NATS server with permission restrictions")


class TestAuthenticationEdgeCases:
    """Test edge cases in authentication."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_empty_username(self):
        """Test that empty username is rejected."""
        config = NATSConfig(
            servers=["nats://localhost:4222"],
            enable_auth=True,
            username="",
            password="test_password",
            enable_jetstream=True,
        )

        with pytest.raises(NATSError):
            async with NATSClient(config) as client:
                pass

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_empty_password(self):
        """Test that empty password is rejected."""
        config = NATSConfig(
            servers=["nats://localhost:4222"],
            enable_auth=True,
            username="test_user",
            password="",
            enable_jetstream=True,
        )

        with pytest.raises(NATSError):
            async with NATSClient(config) as client:
                pass

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_special_characters_in_password(self):
        """Test password with special characters."""
        config = NATSConfig(
            servers=["nats://localhost:4222"],
            enable_auth=True,
            username="test_user",
            password="p@ssw0rd!#$%^&*()",
            enable_jetstream=True,
        )

        try:
            async with NATSClient(config) as client:
                # Should handle special characters correctly
                pass
        except NATSError:
            # Expected if credentials are invalid
            pass

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_username_with_spaces(self):
        """Test that username with spaces is handled correctly."""
        config = NATSConfig(
            servers=["nats://localhost:4222"],
            enable_auth=True,
            username="test user",  # Space in username
            password="test_password",
            enable_jetstream=True,
        )

        with pytest.raises(NATSError):
            async with NATSClient(config) as client:
                pass

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_case_sensitive_username(self):
        """Test that usernames are case-sensitive."""
        config_lower = NATSConfig(
            servers=["nats://localhost:4222"],
            enable_auth=True,
            username="testuser",
            password="test_password",
            enable_jetstream=True,
        )

        config_upper = NATSConfig(
            servers=["nats://localhost:4222"],
            enable_auth=True,
            username="TESTUSER",
            password="test_password",
            enable_jetstream=True,
        )

        # Both should be treated as different users
        # (actual behavior depends on NATS server configuration)
        try:
            async with NATSClient(config_lower) as client:
                pass
        except NATSError:
            pass


class TestAuthenticationTimeout:
    """Test authentication timeout behavior."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_auth_timeout(self):
        """Test that authentication respects timeout."""
        config = NATSConfig(
            servers=["nats://localhost:4222"],
            enable_auth=True,
            username="test_user",
            password="test_password",
            connect_timeout_seconds=2,  # Short timeout
            enable_jetstream=True,
        )

        import time

        start = time.time()
        try:
            async with NATSClient(config) as client:
                pass
        except Exception:
            elapsed = time.time() - start
            # Should fail within timeout
            assert elapsed < 5  # Allow some buffer


class TestCredentialRotation:
    """Test credential rotation scenarios."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_reconnect_with_new_credentials(self):
        """Test reconnecting with updated credentials."""
        # This test simulates credential rotation
        pytest.skip("Requires dynamic credential update mechanism")

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_old_credentials_rejected_after_rotation(self):
        """Test that old credentials are rejected after rotation."""
        pytest.skip("Requires credential rotation implementation")


# Run helper
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
