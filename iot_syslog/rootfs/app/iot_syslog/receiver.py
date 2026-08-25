"""UDP and authenticated TLS syslog listeners."""

from __future__ import annotations

import asyncio
import logging
import ssl
from collections.abc import Callable

from .protocol import OctetCountedFramer, SyslogEvent, parse_rfc5424


LOGGER = logging.getLogger(__name__)


def _peer_name(peer: object) -> str:
    if isinstance(peer, tuple) and peer:
        return str(peer[0])
    return str(peer or "")


class UDPReceiver(asyncio.DatagramProtocol):
    def __init__(self, submit: Callable[[SyslogEvent], bool], max_message_bytes: int):
        self.submit = submit
        self.max_message_bytes = max_message_bytes
        self.transport: asyncio.DatagramTransport | None = None

    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        self.transport = transport  # type: ignore[assignment]

    def datagram_received(self, data: bytes, address: object) -> None:
        if not data or len(data) > self.max_message_bytes:
            LOGGER.warning("Rejected UDP syslog datagram with %d bytes", len(data))
            return
        self.submit(parse_rfc5424(data, "udp", _peer_name(address)))

    def error_received(self, error: Exception) -> None:
        LOGGER.warning("UDP receiver error: %s", error)


class SyslogListeners:
    def __init__(
        self,
        submit: Callable[[SyslogEvent], bool],
        max_message_bytes: int,
    ):
        self.submit = submit
        self.max_message_bytes = max_message_bytes
        self.udp_transport: asyncio.DatagramTransport | None = None
        self.tls_server: asyncio.Server | None = None

    async def start_udp(self, port: int) -> None:
        loop = asyncio.get_running_loop()
        transport, _ = await loop.create_datagram_endpoint(
            lambda: UDPReceiver(self.submit, self.max_message_bytes),
            local_addr=("0.0.0.0", port),
        )
        self.udp_transport = transport  # type: ignore[assignment]
        LOGGER.info("Unencrypted UDP syslog listener started on port %d", port)

    async def start_tls(self, port: int, context: ssl.SSLContext) -> None:
        self.tls_server = await asyncio.start_server(
            self._handle_tls,
            host="0.0.0.0",
            port=port,
            ssl=context,
            ssl_handshake_timeout=15,
            start_serving=True,
        )
        LOGGER.info("TLS syslog listener started on port %d", port)

    async def _handle_tls(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        peer = _peer_name(writer.get_extra_info("peername"))
        framer = OctetCountedFramer(self.max_message_bytes)
        try:
            while True:
                data = await asyncio.wait_for(reader.read(65536), timeout=300)
                if not data:
                    break
                for frame in framer.feed(data):
                    self.submit(parse_rfc5424(frame, "tls", peer))
        except asyncio.TimeoutError:
            LOGGER.debug("Closed idle TLS syslog connection from %s", peer)
        except (ConnectionError, ssl.SSLError, ValueError) as error:
            LOGGER.warning("Closed invalid TLS syslog connection from %s: %s", peer, error)
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except (ConnectionError, ssl.SSLError):
                pass

    async def close(self) -> None:
        if self.udp_transport:
            self.udp_transport.close()
        if self.tls_server:
            self.tls_server.close()
            await self.tls_server.wait_closed()
