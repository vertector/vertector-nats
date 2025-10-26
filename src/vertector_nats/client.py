"""Core NATS JetStream client implementation.

Provides connection management, stream setup, and context management
for NATS JetStream operations.
"""

import asyncio
import logging
from typing import Optional

import nats
from nats.aio.client import Client as NATS
from nats.errors import Error as NATSError
from nats.js import JetStreamContext
from nats.js.api import StreamConfig as JSStreamConfig
from nats.js.errors import BadRequestError, NotFoundError

from vertector_nats.config import NATSConfig, StreamConfig

logger = logging.getLogger(__name__)


class NATSClient:
    """Production-ready NATS JetStream client.

    Features:
    - Automatic reconnection with exponential backoff
    - Stream initialization and validation
    - Context manager support for resource cleanup
    - Comprehensive error handling
    - Connection state management

    Example:
        >>> config = NATSConfig()
        >>> async with NATSClient(config) as client:
        ...     js = client.jetstream
        ...     await js.publish("academic.course.created", b"data")
    """

    def __init__(self, config: NATSConfig) -> None:
        """Initialize NATS client with configuration.

        Args:
            config: NATS configuration object
        """
        self.config = config
        self._nc: Optional[NATS] = None
        self._js: Optional[JetStreamContext] = None
        self._is_connected = False
        self._reconnect_lock = asyncio.Lock()

        logger.info(
            f"Initialized NATS client for servers: {config.servers}",
            extra={"servers": config.servers, "client_name": config.client_name},
        )

    async def connect(self) -> None:
        """Connect to NATS server and enable JetStream.

        Raises:
            NATSError: If connection fails after all retry attempts
        """
        async with self._reconnect_lock:
            if self._is_connected and self._nc and not self._nc.is_closed:
                logger.warning("Already connected to NATS")
                return

            try:
                logger.info(f"Connecting to NATS servers: {self.config.servers}")

                # Build connection options
                options = {
                    "servers": self.config.servers,
                    "name": self.config.client_name,
                    "max_reconnect_attempts": self.config.max_reconnect_attempts,
                    "reconnect_time_wait": self.config.reconnect_wait_seconds,
                    # Callbacks
                    "disconnected_cb": self._disconnected_cb,
                    "reconnected_cb": self._reconnected_cb,
                    "error_cb": self._error_cb,
                    "closed_cb": self._closed_cb,
                }

                # Add authentication if enabled
                if self.config.enable_auth:
                    if self.config.token:
                        options["token"] = self.config.token
                    elif self.config.username and self.config.password:
                        options["user"] = self.config.username
                        options["password"] = self.config.password

                # Add TLS if enabled
                if self.config.enable_tls:
                    tls_context = self._create_tls_context()
                    if tls_context:
                        options["tls"] = tls_context

                # Connect to NATS
                self._nc = await nats.connect(**options)
                self._is_connected = True

                logger.info(
                    f"Successfully connected to NATS: {self._nc.connected_url}",
                    extra={"connected_url": str(self._nc.connected_url)},
                )

                # Enable JetStream if configured
                if self.config.enable_jetstream:
                    await self._setup_jetstream()

            except Exception as e:
                logger.error(f"Failed to connect to NATS: {e}", exc_info=True)
                raise NATSError(f"NATS connection failed: {e}") from e

    async def _setup_jetstream(self) -> None:
        """Initialize JetStream context and create streams."""
        if not self._nc:
            raise RuntimeError("Not connected to NATS")

        try:
            # Create JetStream context
            jetstream_options = {}
            if self.config.jetstream_domain:
                jetstream_options["domain"] = self.config.jetstream_domain

            self._js = self._nc.jetstream(**jetstream_options)

            logger.info("JetStream context created successfully")

            # Create/update streams
            await self._create_streams()

        except Exception as e:
            logger.error(f"Failed to setup JetStream: {e}", exc_info=True)
            raise

    async def _create_streams(self) -> None:
        """Create or update JetStream streams from configuration."""
        if not self._js:
            raise RuntimeError("JetStream not initialized")

        streams = self.config.get_streams()

        for stream_config in streams:
            try:
                await self._create_or_update_stream(stream_config)
            except Exception as e:
                logger.error(
                    f"Failed to create/update stream {stream_config.name}: {e}",
                    exc_info=True,
                )
                # Continue with other streams even if one fails
                continue

    async def _create_or_update_stream(self, stream_config: StreamConfig) -> None:
        """Create or update a single stream.

        Args:
            stream_config: Stream configuration
        """
        if not self._js:
            raise RuntimeError("JetStream not initialized")

        js_config = JSStreamConfig(
            name=stream_config.name,
            subjects=stream_config.subjects,
            retention=stream_config.retention,
            storage=stream_config.storage,
            max_age=stream_config.max_age_seconds,
            max_bytes=stream_config.max_bytes,
            num_replicas=stream_config.replicas,
            discard=stream_config.discard,
        )

        try:
            # Try to get existing stream info
            await self._js.stream_info(stream_config.name)

            # Stream exists, update it
            await self._js.update_stream(config=js_config)

            logger.info(
                f"Updated existing stream: {stream_config.name}",
                extra={"stream": stream_config.name, "subjects": stream_config.subjects},
            )

        except NotFoundError:
            # Stream doesn't exist, create it
            await self._js.add_stream(config=js_config)

            logger.info(
                f"Created new stream: {stream_config.name}",
                extra={"stream": stream_config.name, "subjects": stream_config.subjects},
            )

        except BadRequestError as e:
            logger.warning(
                f"Stream {stream_config.name} already exists with different config: {e}"
            )

    def _create_tls_context(self) -> Optional[object]:
        """Create SSL/TLS context from configuration.

        Returns:
            SSL context if TLS is configured, None otherwise
        """
        if not self.config.enable_tls:
            return None

        import ssl

        ssl_context = ssl.create_default_context(
            purpose=ssl.Purpose.SERVER_AUTH,
            cafile=self.config.tls_ca_cert_file,
        )

        if self.config.tls_cert_file and self.config.tls_key_file:
            ssl_context.load_cert_chain(
                certfile=self.config.tls_cert_file,
                keyfile=self.config.tls_key_file,
            )

        return ssl_context

    async def close(self) -> None:
        """Close NATS connection and cleanup resources."""
        if self._nc and not self._nc.is_closed:
            try:
                await self._nc.drain()
                await self._nc.close()
                logger.info("NATS connection closed successfully")
            except Exception as e:
                logger.error(f"Error closing NATS connection: {e}", exc_info=True)
            finally:
                self._is_connected = False
                self._js = None

    @property
    def jetstream(self) -> JetStreamContext:
        """Get JetStream context.

        Returns:
            JetStreamContext for publishing and subscribing

        Raises:
            RuntimeError: If not connected or JetStream not enabled
        """
        if not self._is_connected or not self._js:
            raise RuntimeError("Not connected to NATS or JetStream not enabled")
        return self._js

    @property
    def nats(self) -> NATS:
        """Get underlying NATS connection.

        Returns:
            NATS connection object

        Raises:
            RuntimeError: If not connected
        """
        if not self._is_connected or not self._nc:
            raise RuntimeError("Not connected to NATS")
        return self._nc

    @property
    def is_connected(self) -> bool:
        """Check if client is connected to NATS.

        Returns:
            True if connected, False otherwise
        """
        return self._is_connected and self._nc is not None and not self._nc.is_closed

    # Connection callbacks

    async def _disconnected_cb(self) -> None:
        """Callback when disconnected from NATS server."""
        logger.warning("Disconnected from NATS server")
        self._is_connected = False

    async def _reconnected_cb(self) -> None:
        """Callback when reconnected to NATS server."""
        logger.info("Reconnected to NATS server")
        self._is_connected = True

    async def _error_cb(self, error: Exception) -> None:
        """Callback when an error occurs.

        Args:
            error: The error that occurred
        """
        logger.error(f"NATS error: {error}", exc_info=True)

    async def _closed_cb(self) -> None:
        """Callback when connection is closed."""
        logger.info("NATS connection closed")
        self._is_connected = False

    # Context manager support

    async def __aenter__(self) -> "NATSClient":
        """Enter async context manager."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:  # type: ignore
        """Exit async context manager."""
        await self.close()
