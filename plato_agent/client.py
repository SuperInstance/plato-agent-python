"""Async TCP client for Plato room connections."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, AsyncIterator

from .protocol import (
    AckResponse,
    AlarmCleared,
    AlarmNotification,
    ErrorResponse,
    HistoryData,
    ProtocolError,
    TickData,
    format_command,
    parse_response,
)

logger = logging.getLogger(__name__)


class PlatoClient:
    """Async TCP client for connecting to a Plato room.

    Usage:
        client = PlatoClient()
        await client.connect("localhost", 7001)
        tick = await client.tick()
        async for t in client.stream():
            print(t)
        await client.disconnect()

    Attributes:
        host: Room host address.
        port: Room port.
        connected: Whether the client is currently connected.
    """

    def __init__(self) -> None:
        self.host: str = ""
        self.port: int = 0
        self.connected: bool = False
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._subscribed: bool = False
        self._lock = asyncio.Lock()

    async def connect(self, host: str, port: int) -> None:
        """Establish a TCP connection to a room.

        Args:
            host: Room host address.
            port: Room port number.

        Raises:
            ConnectionError: If connection fails.
        """
        self.host = host
        self.port = port
        try:
            self._reader, self._writer = await asyncio.open_connection(host, port)
            self.connected = True
            logger.info("Connected to %s:%d", host, port)
        except OSError as e:
            raise ConnectionError(f"Failed to connect to {host}:{port}: {e}") from e

    async def disconnect(self) -> None:
        """Close the connection to the room."""
        if self._writer is not None:
            try:
                self._writer.close()
                await self._writer.wait_closed()
            except Exception:
                pass
        self.connected = False
        self._subscribed = False
        self._reader = None
        self._writer = None
        logger.info("Disconnected from %s:%d", self.host, self.port)

    async def _send(self, cmd: str, **kwargs: Any) -> None:
        """Send a raw command to the room."""
        if not self.connected or self._writer is None:
            raise ConnectionError("Not connected")
        line = format_command(cmd, **kwargs) + "\n"
        self._writer.write(line.encode("utf-8"))
        await self._writer.drain()

    async def _recv(self) -> str:
        """Receive a single line from the room."""
        if self._reader is None:
            raise ConnectionError("Not connected")
        data = await self._reader.readline()
        if not data:
            raise ConnectionError("Connection closed by server")
        return data.decode("utf-8").strip()

    async def tick(self) -> TickData:
        """Request the current tick from the room.

        Returns:
            Current tick data.

        Raises:
            ConnectionError: If not connected.
            ProtocolError: If response is malformed.
        """
        async with self._lock:
            await self._send("TICK")
            response = await self._recv()
        parsed = parse_response(response)
        if isinstance(parsed, TickData):
            return parsed
        if isinstance(parsed, ErrorResponse):
            raise ProtocolError(f"Room error: {parsed.message}")
        raise ProtocolError(f"Expected TICK response, got: {response}")

    async def history(self, n: int = 10) -> HistoryData:
        """Request tick history from the room.

        Args:
            n: Number of recent ticks to retrieve.

        Returns:
            History data with ticks and cursor.

        Raises:
            ConnectionError: If not connected.
            ProtocolError: If response is malformed.
        """
        async with self._lock:
            await self._send("HISTORY", n=n)
            response = await self._recv()
        parsed = parse_response(response)
        if isinstance(parsed, HistoryData):
            return parsed
        if isinstance(parsed, ErrorResponse):
            raise ProtocolError(f"Room error: {parsed.message}")
        raise ProtocolError(f"Expected HISTORY response, got: {response}")

    async def actuate(self, name: str, value: Any) -> AckResponse:
        """Send an actuator command to the room.

        Args:
            name: Actuator name.
            value: Value to set.

        Returns:
            Acknowledgement response.

        Raises:
            ConnectionError: If not connected.
            ProtocolError: If the room rejects the command.
        """
        async with self._lock:
            await self._send("ACTUATE", name=name, value=value)
            response = await self._recv()
        parsed = parse_response(response)
        if isinstance(parsed, AckResponse):
            return parsed
        if isinstance(parsed, ErrorResponse):
            raise ProtocolError(f"Actuate error: {parsed.message}")
        raise ProtocolError(f"Expected ACK response, got: {response}")

    async def subscribe(self) -> AckResponse:
        """Subscribe to real-time tick updates.

        Returns:
            Acknowledgement response.
        """
        async with self._lock:
            await self._send("SUBSCRIBE")
            response = await self._recv()
        parsed = parse_response(response)
        if isinstance(parsed, AckResponse):
            self._subscribed = True
            return parsed
        raise ProtocolError(f"Expected ACK, got: {response}")

    async def unsubscribe(self) -> AckResponse:
        """Unsubscribe from real-time tick updates.

        Returns:
            Acknowledgement response.
        """
        async with self._lock:
            await self._send("UNSUBSCRIBE")
            response = await self._recv()
        parsed = parse_response(response)
        if isinstance(parsed, AckResponse):
            self._subscribed = False
            return parsed
        raise ProtocolError(f"Expected ACK, got: {response}")

    async def stream(self) -> AsyncIterator[TickData | AlarmNotification | AlarmCleared]:
        """Async iterator yielding real-time ticks and alarm notifications.

        Must call subscribe() first, or the room must be in push mode.

        Yields:
            TickData, AlarmNotification, or AlarmCleared objects.
        """
        while self.connected:
            try:
                line = await self._recv()
                parsed = parse_response(line)
                yield parsed
            except ConnectionError:
                logger.info("Stream ended: connection closed")
                break
            except ProtocolError as e:
                logger.warning("Protocol error in stream: %s", e)
                continue
