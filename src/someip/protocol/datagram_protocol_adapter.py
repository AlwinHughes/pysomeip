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

from someip_datagram_protocol import SOMEIPDatagramProtocol

class DatagramProtocolAdapter(asyncio.DatagramProtocol):
    def __init__(self, protocol: SOMEIPDatagramProtocol, is_multicast: bool):
        self.is_multicast = is_multicast
        self.protocol = protocol

    def datagram_received(self, data, addr: _T_SOCKADDR) -> None:
        self.protocol.datagram_received(data, addr, multicast=self.is_multicast)

    def error_received(
        self, exc: typing.Optional[Exception]
    ) -> None:  # pragma: nocover
        self.protocol.error_received(exc)

    def connection_lost(
        self, exc: typing.Optional[Exception]
    ) -> None:  # pragma: nocover
        self.protocol.connection_lost(exc)
