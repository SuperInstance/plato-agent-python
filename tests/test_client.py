"""Tests for PlatoClient using a mock TCP server."""

import asyncio
import json
import pytest

from plato_agent.client import PlatoClient
from plato_agent.protocol import TickData, HistoryData, AckResponse


@pytest.fixture
async def mock_server_and_client(unused_tcp_port):
    """Set up a mock Plato room server and connected client."""
    received_commands: list[str] = []
    responses: asyncio.Queue[str] = asyncio.Queue()

    async def handle_client(reader, writer):
        try:
            while True:
                data = await reader.readline()
                if not data:
                    break
                cmd = data.decode().strip()
                received_commands.append(cmd)

                if cmd == "TICK":
                    payload = json.dumps({"temp": 72.5, "humidity": 45})
                    writer.write(f"TICK 100.0 {payload}\n".encode())
                elif cmd.startswith("HISTORY"):
                    ticks = [{"ts": 100.0 + i, "sensors": {"temp": 70 + i}} for i in range(3)]
                    writer.write(f"HISTORY 0 3 {json.dumps(ticks)}\n".encode())
                elif cmd.startswith("ACTUATE"):
                    writer.write(f"ACK {cmd}\n".encode())
                elif cmd == "SUBSCRIBE":
                    writer.write(b"ACK SUBSCRIBE\n")
                    # Send a few ticks
                    for i in range(3):
                        payload = json.dumps({"temp": 72 + i})
                        writer.write(f"TICK {200.0 + i} {payload}\n".encode())
                        await writer.drain()
                        await asyncio.sleep(0.05)
                elif cmd == "UNSUBSCRIBE":
                    writer.write(b"ACK UNSUBSCRIBE\n")
                else:
                    resp = await responses.get()
                    writer.write(f"{resp}\n".encode())

                await writer.drain()
        except (ConnectionError, asyncio.CancelledError):
            pass
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass

    server = await asyncio.start_server(handle_client, "127.0.0.1", unused_tcp_port)

    client = PlatoClient()
    await client.connect("127.0.0.1", unused_tcp_port)

    yield client, server, received_commands

    await client.disconnect()
    server.close()
    await server.wait_closed()


class TestClientConnection:
    @pytest.mark.asyncio
    async def test_connect_and_disconnect(self, unused_tcp_port):
        server = await asyncio.start_server(lambda r, w: None, "127.0.0.1", unused_tcp_port)
        client = PlatoClient()
        await client.connect("127.0.0.1", unused_tcp_port)
        assert client.connected
        await client.disconnect()
        assert not client.connected
        server.close()
        await server.wait_closed()

    @pytest.mark.asyncio
    async def test_connect_failure(self):
        client = PlatoClient()
        with pytest.raises(ConnectionError):
            await client.connect("127.0.0.1", 1)


class TestClientTick:
    @pytest.mark.asyncio
    async def test_tick(self, mock_server_and_client):
        client, _, cmds = mock_server_and_client
        result = await client.tick()
        assert isinstance(result, TickData)
        assert result.timestamp == 100.0
        assert result.sensors["temp"] == 72.5


class TestClientHistory:
    @pytest.mark.asyncio
    async def test_history(self, mock_server_and_client):
        client, _, _ = mock_server_and_client
        result = await client.history(n=3)
        assert isinstance(result, HistoryData)
        assert result.count == 3
        assert len(result.ticks) == 3


class TestClientActuate:
    @pytest.mark.asyncio
    async def test_actuate(self, mock_server_and_client):
        client, _, _ = mock_server_and_client
        result = await client.actuate("pump", "on")
        assert isinstance(result, AckResponse)
        assert "pump=on" in result.command


class TestClientSubscribe:
    @pytest.mark.asyncio
    async def test_subscribe_and_stream(self, mock_server_and_client):
        client, _, _ = mock_server_and_client
        await client.subscribe()
        ticks = []
        async for event in client.stream():
            if isinstance(event, TickData):
                ticks.append(event)
            if len(ticks) >= 3:
                break
        assert len(ticks) == 3
        assert ticks[0].sensors["temp"] == 72

    @pytest.mark.asyncio
    async def test_unsubscribe(self, mock_server_and_client):
        client, _, _ = mock_server_and_client
        result = await client.unsubscribe()
        assert isinstance(result, AckResponse)
        assert not client._subscribed
