from __future__ import annotations

import typing

import someip.header
import someip.config

from someip.config import _T_SOCKNAME as _T_SOCKADDR

class ISOMEIPDatagramProtocol:


    def datagram_received(self, data, addr: _T_SOCKADDR, multicast: bool) -> None:
        pass


    def error_received(self, exc: typing.Optional[Exception]):  # pragma: nocover
        pass


    def connection_lost(
        self, exc: typing.Optional[Exception]
    ) -> None:  # pragma: nocover
        pass


    def message_received(
        self,
        someip_message: someip.header.SOMEIPHeader,
        addr: _T_SOCKADDR,
        multicast: bool,
    ) -> None:  # pragma: nocover
        pass
