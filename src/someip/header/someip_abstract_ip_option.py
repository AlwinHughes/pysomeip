from __future__ import annotations

import dataclasses
import ipaddress
import struct
import socket
import typing

import someip.utils

from .someip_sd_option import SOMEIPSDAbstractOption
from .enums import L4Protocols
from .util import ParseError

T = typing.TypeVar("T", ipaddress.IPv4Address, ipaddress.IPv6Address)
_T_SOCKNAME = typing.Union[typing.Tuple[str, int], typing.Tuple[str, int, int, int]]

@dataclasses.dataclass(frozen=True)
class AbstractIPOption(SOMEIPSDAbstractOption, typing.Generic[T]):
    """
    Abstract base class for options with IP payloads. Generalizes parsing and building
    based on :attr:`_format`, :attr:`_address_type` and :attr:`_family`.
    """

    _format: typing.ClassVar[struct.Struct]
    _address_type: typing.ClassVar[typing.Type[typing.Any]]
    _family: typing.ClassVar[socket.AddressFamily]
    address: T
    l4proto: typing.Union[L4Protocols, int]
    port: int

    @classmethod
    def parse_option(cls, buf: bytes) -> AbstractIPOption[T]:
        if len(buf) != cls._format.size:
            raise ParseError(
                f"{cls.__name__} with wrong payload length {len(buf)} != 9"
            )

        r1, addr_b, r2, l4proto_b, port = cls._format.unpack(buf)

        addr = cls._address_type(addr_b)
        try:
            l4proto = L4Protocols(l4proto_b)
        except ValueError:
            l4proto = l4proto_b

        return cls(address=addr, l4proto=l4proto, port=port)

    def build(self) -> bytes:
        """
        build the byte representation of this option.

        :raises struct.error: if :attr:`payload` is too big to be represented, or
            :attr:`type` is out of range
        :return: the byte representation
        """
        payload = self._format.pack(0, self.address.packed, 0, self.l4proto, self.port)
        return self.build_option(self.type, payload)

    async def addrinfo(self) -> _T_SOCKNAME:
        """
        return address info for this IP option for use in socket-based functions, e.g.,
        :meth:`socket.connect` or :meth:`socket.sendto`.

        :raises socket.gaierror: if the call to `getaddrinfo` failed or returned no
            result
        :returns: the first resolved sockaddr tuple
        """
        addr = await someip.utils.getfirstaddrinfo(
            str(self.address),
            self.port,
            family=self._family,
            proto=self.l4proto,
            flags=socket.AI_NUMERICHOST | socket.AI_NUMERICSERV,
        )
        return typing.cast(_T_SOCKNAME, addr[4])


class EndpointOption(AbstractIPOption[T]):
    """
    Abstract base class for endpoint options (IPv4 or IPv6).
    """

    pass


class MulticastOption(AbstractIPOption[T]):
    """
    Abstract base class for multicast options (IPv4 or IPv6).
    """

    pass


class SDEndpointOption(AbstractIPOption[T]):
    """
    Abstract base class for SD Endpoint options (IPv4 or IPv6).
    """

    pass


class AbstractIPv4Option(AbstractIPOption[ipaddress.IPv4Address]):
    """
    Abstract base class for IPv4 options.
    """

    _format: typing.ClassVar[struct.Struct] = struct.Struct("!B4sBBH")
    _address_type = ipaddress.IPv4Address
    _family = socket.AF_INET

    def __str__(self) -> str:  # pragma: nocover
        if isinstance(self.l4proto, L4Protocols):
            return f"{self.address}:{self.port} ({self.l4proto.name})"
        else:
            return f"{self.address}:{self.port} (protocol={self.l4proto:#x})"


class AbstractIPv6Option(AbstractIPOption[ipaddress.IPv6Address]):
    """
    Abstract base class for IPv6 options.
    """

    _format: typing.ClassVar[struct.Struct] = struct.Struct("!B16sBBH")
    _address_type = ipaddress.IPv6Address
    _family = socket.AF_INET6

    def __str__(self) -> str:  # pragma: nocover
        if isinstance(self.l4proto, L4Protocols):
            return f"{self.address}:{self.port} ({self.l4proto.name})"
        else:
            return f"{self.address}:{self.port} (protocol={self.l4proto:#x})"
