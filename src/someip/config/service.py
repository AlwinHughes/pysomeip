from __future__ import annotations

import dataclasses
import ipaddress
import socket
import typing

import someip.header


_T_ADDR = typing.Tuple[typing.Union[ipaddress.IPv4Address, ipaddress.IPv6Address], int]

@dataclasses.dataclass(frozen=True)
class Service:
    """
    Defines a Service that can be found and offered.

    :param service_id:
    :param instance_id: may be 0xFFFF (default) to match any instance
    :param major_version: may be 0xFF (default) to match any major version
    :param minor_version: may be 0xFFFFFFFF (default) to match any major version
    :param options_1: options that apply to this service (run 1)
    :param options_2: options that apply to this service (run 2)
    :param eventgroups: offered eventgroup ids.
    """

    service_id: int
    instance_id: int = 0xFFFF
    major_version: int = 0xFF
    minor_version: int = 0xFFFFFFFF

    options_1: typing.Tuple[someip.header.SOMEIPSDOption, ...] = dataclasses.field(
        default=(), compare=False
    )
    options_2: typing.Tuple[someip.header.SOMEIPSDOption, ...] = dataclasses.field(
        default=(), compare=False
    )

    eventgroups: typing.FrozenSet[int] = frozenset()

    def matches_offer(self, entry: someip.header.SOMEIPSDEntry) -> bool:
        """
        Test if a received OfferService :class:`~someip.header.SOMEIPSDEntry` matches
        this service. This is the case if the `service_id` is identical, and
        `instance_id`, `major_version` and `minor_version` are either identical or set
        to wildcard values on this :class:`Service` instance.

        :param entry: the entry to match against
        :return: True if the given OfferService entry matches this service
        :raises ValueError: if the entry is no OfferService
        """
        if entry.sd_type != someip.header.SOMEIPSDEntryType.OfferService:
            raise ValueError("entry is no OfferService")

        if self.service_id != entry.service_id:
            return False

        if self.instance_id != 0xFFFF and self.instance_id != entry.instance_id:
            return False
        if self.major_version != 0xFF and self.major_version != entry.major_version:
            return False
        if (
            self.minor_version != 0xFFFFFFFF
            and self.minor_version != entry.service_minor_version
        ):
            return False
        return True

    def matches_find(self, entry: someip.header.SOMEIPSDEntry) -> bool:
        """
        Test if a received FindService :class:`~someip.header.SOMEIPSDEntry` matches
        this service. This is the case if the `service_id` fields are equal, and
        `instance_id`, `major_version` and `minor_version` fields are either equal or
        set to wildcard values on the FindService SD entry.

        :param entry: the entry to match against
        :return: True if the given FindService entry matches this service
        :raises ValueError: if the entry is no FindService
        """
        if entry.sd_type != someip.header.SOMEIPSDEntryType.FindService:
            raise ValueError("entry is no FindService")

        if self.service_id != entry.service_id:
            return False

        if entry.instance_id != 0xFFFF and self.instance_id != entry.instance_id:
            return False
        if entry.major_version != 0xFF and self.major_version != entry.major_version:
            return False
        if (
            entry.service_minor_version != 0xFFFFFFFF
            and self.minor_version != entry.service_minor_version
        ):
            return False
        return True

    def matches_subscribe(self, entry: someip.header.SOMEIPSDEntry) -> bool:
        """
        Test if a received Subscribe :class:`~someip.header.SOMEIPSDEntry` matches
        this service. This is the case if the `service_id` fields are equal, the
        `eventgroup_id` is in :attr:`eventgroups`, and `instance_id` and `major_version`
        fields are either equal or set to wildcard values on this :class:`Service`
        instance.

        :param entry: the entry to match against
        :return: True if the given Subscribe entry matches this service
        :raises ValueError: if the entry is no Subscribe
        """
        if entry.sd_type != someip.header.SOMEIPSDEntryType.Subscribe:
            raise ValueError("entry is no Subscribe")

        if self.service_id != entry.service_id:
            return False

        if self.instance_id != 0xFFFF and self.instance_id != entry.instance_id:
            return False

        if self.major_version != 0xFF and self.major_version != entry.major_version:
            return False

        return entry.eventgroup_id in self.eventgroups

    def matches_service(self, other: Service) -> bool:
        """
        Test if a given service matches this service. This is the case if the
        :attr:`service_id` fields are equal, and :attr:`instance_id`,
        :attr:`major_version` and :attr:`minor_version` are either equal or set to
        wildcard values on either :class:`Service` instance.

        :param other: the service to match against
        :return: True if the given service matches this service
        """
        if self.service_id != other.service_id:
            return False

        if (
            self.instance_id != 0xFFFF
            and other.instance_id != 0xFFFF
            and self.instance_id != other.instance_id
        ):
            return False

        if (
            self.major_version != 0xFF
            and other.major_version != 0xFF
            and self.major_version != other.major_version
        ):
            return False

        if (
            self.minor_version != 0xFFFFFFFF
            and other.minor_version != 0xFFFFFFFF
            and self.minor_version != other.minor_version
        ):
            return False

        return True

    def create_find_entry(self, ttl=3):
        """
        Create a SD FindService entry for this service.

        :param ttl: the TTL for this FindService entry
        :return: the FindService SD entry for this service
        """
        return someip.header.SOMEIPSDEntry(
            sd_type=someip.header.SOMEIPSDEntryType.FindService,
            service_id=self.service_id,
            instance_id=self.instance_id,
            major_version=self.major_version,
            ttl=ttl,
            minver_or_counter=self.minor_version,
        )

    def create_offer_entry(self, ttl=3):
        """
        Create a SD OfferService entry for this service.

        :param ttl: the TTL for this FindService entry
        :return: the OfferService SD entry for this service
        """
        return someip.header.SOMEIPSDEntry(
            sd_type=someip.header.SOMEIPSDEntryType.OfferService,
            service_id=self.service_id,
            instance_id=self.instance_id,
            major_version=self.major_version,
            ttl=ttl,
            minver_or_counter=self.minor_version,
            options_1=tuple(self.options_1),
            options_2=tuple(self.options_2),
        )

    def __str__(self) -> str:  # pragma: nocover
        version = f"{self.major_version}.{self.minor_version}"

        s_options_1 = (
            ", ".join(str(o) for o in self.options_1) if self.options_1 else ""
        )
        s_options_2 = (
            ", ".join(str(o) for o in self.options_2) if self.options_2 else ""
        )

        return (
            f"service=0x{self.service_id:04x}, instance=0x{self.instance_id:04x},"
            f" version={version}, options_1=[{s_options_1}], options_2=[{s_options_2}]"
        )

    @classmethod
    def from_offer_entry(cls, entry: someip.header.SOMEIPSDEntry) -> Service:
        """
        Create a :class:`Service` from a given OfferService SD entry.

        :param entry: the entry as seen on the wire
        :return: a new :class:`Service` instance with values set from the given
            OfferService entry
        :raises ValueError: if the entry is no OfferService, or the entry does not have
            resolved options (see :attr:`someip.header.SOMEIPSDEntry.options_resolved`)
        """
        if entry.sd_type != someip.header.SOMEIPSDEntryType.OfferService:
            raise ValueError("entry is no OfferService")
        if not entry.options_resolved:
            raise ValueError("entry must have resolved options")
        return cls(
            entry.service_id,
            entry.instance_id,
            entry.major_version,
            entry.service_minor_version,
            options_1=tuple(entry.options_1),
            options_2=tuple(entry.options_2),
        )
