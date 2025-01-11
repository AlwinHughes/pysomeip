from __future__ import annotations

import asyncio
import collections
import dataclasses
import ipaddress
import itertools
import logging
import os
import platform
import random
import socket
import struct
import threading
import typing

import someip.header
import someip.config
from someip.config import _T_SOCKNAME as _T_SOCKADDR
_T_OPT_SOCKADDR = typing.Optional[_T_SOCKADDR]

from .session_storage import _SessionStorage
from .datagram_protocol_adapter import DatagramProtocolAdapter

from .interfaces import ISOMEIPDatagramProtocol

#from sd.py
# needs: _SessionStorage
class SOMEIPDatagramProtocol(ISOMEIPDatagramProtocol):
    """
    is actually not a subclass of asyncio.BaseProtocol or asyncio.DatagramProtocol,
    because datagram_received() has an additional parameter `multicast: bool`

    TODO: fix misleading name
    """

    @classmethod
    async def create_unicast_endpoint(
# _T_OPT_SOCKADDR = typing.Optional[_T_SOCKADDR]
        cls,
        *args,
        local_addr: _T_OPT_SOCKADDR = None,
        remote_addr: _T_OPT_SOCKADDR = None,
        loop=None,
        **kwargs,
    ):
        if loop is None:  # pragma: nobranch
            loop = asyncio.get_event_loop()
        protocol = cls(*args, **kwargs)
        transport, _ = await loop.create_datagram_endpoint(
            lambda: DatagramProtocolAdapter(protocol, is_multicast=False),
            local_addr=local_addr,
            remote_addr=remote_addr,
        )
        protocol.transport = transport
        return transport, protocol

    def __init__(self, logger: str = "someip"):
        self.log = logging.getLogger(logger)
        self.transport: asyncio.DatagramTransport
        self.session_storage = _SessionStorage()

        # default_addr=None means use connected address from socket
        self.default_addr: _T_OPT_SOCKADDR = None

    def datagram_received(self, data, addr: _T_SOCKADDR, multicast: bool) -> None:
        try:
            while data:
                # 4.2.1, TR_SOMEIP_00140 more than one SOMEIP message per UDP frame
                # allowed
                parsed, data = someip.header.SOMEIPHeader.parse(data)
                self.message_received(parsed, addr, multicast)
        except someip.header.ParseError as exc:
            self.log.error(
                "failed to parse SOME/IP datagram from %s: %r",
                format_address(addr),
                data,
                exc_info=exc,
            )

    def error_received(self, exc: typing.Optional[Exception]):  # pragma: nocover
        self.log.exception("someip event listener protocol failed", exc_info=exc)

    def connection_lost(
        self, exc: typing.Optional[Exception]
    ) -> None:  # pragma: nocover
        log = self.log.exception if exc else self.log.info
        log("someip closed", exc_info=exc)

    def message_received(
        self,
        someip_message: someip.header.SOMEIPHeader,
        addr: _T_SOCKADDR,
        multicast: bool,
    ) -> None:  # pragma: nocover
        """
        called when a well-formed SOME/IP datagram was received
        """
        self.log.info("received from %s\n%s", format_address(addr), someip_message)
        pass

    def send(self, buf: bytes, remote: _T_OPT_SOCKADDR = None):
        # ideally, we'd use transport.write() and have the DGRAM socket connected to the
        # default_addr. However, after connect() the socket will not be bound to
        # INADDR_ANY anymore. so we store the multicast address as a default destination
        # address on the instance and wrap the send calls with self.send
        if not self.transport:  # pragma: nocover
            self.log.error(
                "no transport set on %r but tried to send to %r: %r", self, remote, buf
            )
            return
        if not remote:
            remote = self.default_addr
        self.transport.sendto(buf, remote)

