"""
Classes for defining a :class:`Service` or :class:`Eventgroup`.
These definitions will be used to match against, and to convert to SD service or
eventgroup entries as seen on the wire (see :class:`someip.header.SOMEIPSDEntry`).
"""
from __future__ import annotations

import dataclasses
import ipaddress
import socket
import typing

import someip.header

from .service import Service

_T_SOCKNAME = typing.Union[typing.Tuple[str, int], typing.Tuple[str, int, int, int]]

@dataclasses.dataclass(frozen=True)
class Eventgroup:
    """
    Defines an Eventgroup that can be subscribed to.

    :param service_id:
    :param instance_id:
    :param major_version:
    :param eventgroup_id:
    :param sockname: the socket address as returned by :meth:`socket.getsockname`
    :type  sockname: tuple
    :param protocol: selects the layer 4 protocol
    """

    service_id: int
    instance_id: int
    major_version: int
    eventgroup_id: int

    sockname: _T_SOCKNAME

    protocol: someip.header.L4Protocols

    def create_subscribe_entry(
        self, ttl: int = 3, counter: int = 0
    ) -> someip.header.SOMEIPSDEntry:
        """
        Create a SD Subscribe entry for this eventgroup.

        :param ttl: the TTL for this Subscribe entry
        :param counter: counter to identify this specific subscription in otherwise
          identical subscriptions
        :return: the Subscribe SD entry for this eventgroup
        """
        endpoint_option = self._sockaddr_to_endpoint(self.sockname, self.protocol)
        return someip.header.SOMEIPSDEntry(
            sd_type=someip.header.SOMEIPSDEntryType.Subscribe,
            service_id=self.service_id,
            instance_id=self.instance_id,
            major_version=self.major_version,
            ttl=ttl,
            minver_or_counter=(counter << 16) | self.eventgroup_id,
            options_1=(endpoint_option,),
        )

    def for_service(self, service: Service) -> typing.Optional[Eventgroup]:
        """
        replace a generic definition (that may contain wildcards in
        :attr:`instance_id` and :attr:`major_version`) with actual values from a
        :class:`Service`.

        :param service: actual service
        :return: A new :class:`Eventgroup` with :attr:`instance_id` and
            :attr:`major_version` from service. None if this eventgroup does not match
            the given service.
        """
        if not self.as_service().matches_offer(service.create_offer_entry()):
            return None
        return dataclasses.replace(
            self,
            instance_id=service.instance_id,
            major_version=service.major_version,
        )

    def as_service(self):
        """
        returns a :class:`Service` for this event group, e.g. for use with
        :meth:`~someip.sd.ServiceDiscover.watch_service`.
        """
        return Service(
            service_id=self.service_id,
            instance_id=self.instance_id,
            major_version=self.major_version,
        )

    @staticmethod
    def _sockaddr_to_endpoint(
        sockname: _T_SOCKNAME, protocol: someip.header.L4Protocols
    ) -> someip.header.SOMEIPSDOption:
        host, port = socket.getnameinfo(
            sockname, socket.NI_NUMERICHOST | socket.NI_NUMERICSERV
        )
        nport = int(port)
        naddr = ipaddress.ip_address(host)

        if isinstance(naddr, ipaddress.IPv4Address):
            return someip.header.IPv4EndpointOption(
                address=naddr, l4proto=protocol, port=nport
            )
        elif isinstance(naddr, ipaddress.IPv6Address):
            return someip.header.IPv6EndpointOption(
                address=naddr, l4proto=protocol, port=nport
            )
        else:  # pragma: nocover
            raise TypeError("unsupported IP address family")

    def __str__(self) -> str:  # pragma: nocover
        return (
            f"eventgroup={self.eventgroup_id:04x} service=0x{self.service_id:04x},"
            f" instance=0x{self.instance_id:04x}, version={self.major_version}"
            f" addr={self.sockname!r} proto={self.protocol.name}"
        )
