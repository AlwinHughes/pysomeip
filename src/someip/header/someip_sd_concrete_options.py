from __future__ import annotations

import dataclasses
import ipaddress
import typing

from .someip_sd_option import SOMEIPSDOption
from .someip_abstract_ip_option import AbstractIPv4Option
from .someip_abstract_ip_option import AbstractIPv6Option
from .someip_abstract_ip_option import MulticastOption
from .someip_abstract_ip_option import EndpointOption
from .someip_abstract_ip_option import SDEndpointOption

T = typing.TypeVar("T", ipaddress.IPv4Address, ipaddress.IPv6Address)

@SOMEIPSDOption.register
class IPv4EndpointOption(AbstractIPv4Option, EndpointOption[ipaddress.IPv4Address]):
    type: typing.ClassVar[int] = 0x04


@SOMEIPSDOption.register
class IPv4MulticastOption(AbstractIPv4Option, MulticastOption[ipaddress.IPv4Address]):
    type: typing.ClassVar[int] = 0x14


@SOMEIPSDOption.register
@dataclasses.dataclass(frozen=True)
class IPv4SDEndpointOption(AbstractIPv4Option, SDEndpointOption[ipaddress.IPv4Address]):
    type: typing.ClassVar[int] = 0x24


@SOMEIPSDOption.register
class IPv6EndpointOption(AbstractIPv6Option, EndpointOption[ipaddress.IPv6Address]):
    type: typing.ClassVar[int] = 0x06


@SOMEIPSDOption.register
class IPv6MulticastOption(AbstractIPv6Option, MulticastOption[ipaddress.IPv6Address]):
    type: typing.ClassVar[int] = 0x16


@SOMEIPSDOption.register
@dataclasses.dataclass(frozen=True)
class IPv6SDEndpointOption(AbstractIPv6Option, SDEndpointOption[ipaddress.IPv6Address]):
    type: typing.ClassVar[int] = 0x26


