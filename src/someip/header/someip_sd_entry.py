from __future__ import annotations

import asyncio
import dataclasses
import struct
import typing


from .enums import SOMEIPSDEntryType
from .someip_sd_option import SOMEIPSDOption
from .util import _find
from .util import _unpack
from .util import ParseError

try:
    from functools import cached_property
except ImportError:  # pragma: nocover
    cached_property = property  # type: ignore[misc,assignment]

@dataclasses.dataclass(frozen=True)
class SOMEIPSDEntry:
    """
    Represents an Entry in SOMEIP SD packets.

    :param sd_type:
    :param service_id:
    :param instance_id:
    :param major_version:
    :param ttl:
    :param minver_or_counter: service minor version or eventgroup id and counter value
    :param options_1: resolved options that apply to this entry (run 1)
    :param options_2: resolved options that apply to this entry (run 2)
    :param option_index_1: option index (for unresolved options, run 1)
    :param option_index_2: option index (for unresolved options, run 2)
    :param num_options_1: number of option (for unresolved options, run 1)
    :param num_options_2: number of option (for unresolved options, run 2)
    """

    __format: typing.ClassVar[struct.Struct] = struct.Struct("!BBBBHHBBHI")
    sd_type: SOMEIPSDEntryType
    service_id: int
    instance_id: int
    major_version: int
    ttl: int
    minver_or_counter: int

    options_1: typing.Tuple[SOMEIPSDOption, ...] = ()
    options_2: typing.Tuple[SOMEIPSDOption, ...] = ()

    option_index_1: typing.Optional[int] = None
    option_index_2: typing.Optional[int] = None
    num_options_1: typing.Optional[int] = None
    num_options_2: typing.Optional[int] = None

    def __str__(self) -> str:  # pragma: nocover
        if self.sd_type in (
            SOMEIPSDEntryType.FindService,
            SOMEIPSDEntryType.OfferService,
        ):
            version = f"{self.major_version}.{self.service_minor_version}"
        elif self.sd_type in (
            SOMEIPSDEntryType.Subscribe,
            SOMEIPSDEntryType.SubscribeAck,
        ):
            version = (
                f"{self.major_version}, eventgroup_counter={self.eventgroup_counter},"
                f" eventgroup_id={self.eventgroup_id}"
            )

        if self.options_resolved:
            s_options_1 = ", ".join(str(o) for o in self.options_1)
            s_options_2 = ", ".join(str(o) for o in self.options_2)
        else:
            oi1 = typing.cast(int, self.option_index_1)
            oi2 = typing.cast(int, self.option_index_2)
            no1 = typing.cast(int, self.num_options_1)
            no2 = typing.cast(int, self.num_options_2)
            s_options_1 = repr(range(oi1, oi1 + no1))
            s_options_2 = repr(range(oi2, oi2 + no2))

        return (
            f"type={self.sd_type.name}, service=0x{self.service_id:04x},"
            f" instance=0x{self.instance_id:04x}, version={version}, ttl={self.ttl}, "
            f" options_1=[{s_options_1}], options_2=[{s_options_2}]"
        )

    @cached_property
    def options(self) -> typing.Tuple[SOMEIPSDOption, ...]:
        """
        convenience wrapper contains merged :attr:`options_1` and :attr:`options_2`
        """
        return self.options_1 + self.options_2

    @property
    def options_resolved(self) -> bool:
        """
        indicates if the options on this instance are resolved
        """
        return (
            self.option_index_1 is None
            or self.option_index_2 is None
            or self.num_options_1 is None
            or self.num_options_2 is None
        )

    def resolve_options(
        self, options: typing.Tuple[SOMEIPSDOption, ...]
    ) -> SOMEIPSDEntry:
        """
        resolves this entry's options with option list from containing
        :class:`SOMEIPSDHeader`.

        :return: a new :class:`SOMEIPSDEntry` instance with resolved options
        """
        if self.options_resolved:
            raise ValueError("options already resolved")

        oi1 = typing.cast(int, self.option_index_1)
        oi2 = typing.cast(int, self.option_index_2)
        no1 = typing.cast(int, self.num_options_1)
        no2 = typing.cast(int, self.num_options_2)

        return dataclasses.replace(
            self,
            options_1=options[oi1 : oi1 + no1],
            options_2=options[oi2 : oi2 + no2],
            option_index_1=None,
            option_index_2=None,
            num_options_1=None,
            num_options_2=None,
        )

    @staticmethod
    def _assign_option(entry_options, hdr_options) -> typing.Tuple[int, int]:
        if not entry_options:
            return (0, 0)

        no = len(entry_options)
        oi = _find(hdr_options, entry_options)
        if oi is None:
            oi = len(hdr_options)
            hdr_options.extend(entry_options)
        return oi, no

    def assign_option_index(
        self, options: typing.List[SOMEIPSDOption]
    ) -> SOMEIPSDEntry:
        """
        assigns option indexes, optionally inserting new options to the given option
        list. Index assignment is done in a simple manner by searching if a slice exists
        in `options` that matches the option runs (:attr:`options_1` and
        :attr:`options_2`).

        :return: a new :class:`SOMEIPSDEntry` instance with assigned options indexes
        """
        if not self.options_resolved:
            return dataclasses.replace(self)  # pragma: nocover

        oi1, no1 = self._assign_option(self.options_1, options)
        oi2, no2 = self._assign_option(self.options_2, options)
        return dataclasses.replace(
            self,
            option_index_1=oi1,
            option_index_2=oi2,
            num_options_1=no1,
            num_options_2=no2,
            options_1=(),
            options_2=(),
        )

    @property
    def service_minor_version(self) -> int:
        """
        the service minor version

        :raises TypeError: if this entry is not a FindService or OfferService
        """
        if self.sd_type not in (
            SOMEIPSDEntryType.FindService,
            SOMEIPSDEntryType.OfferService,
        ):
            raise TypeError(
                f"SD entry is type {self.sd_type},"
                " does not have service_minor_version"
            )
        return self.minver_or_counter

    @property
    def eventgroup_counter(self) -> int:
        """
        the eventgroup counter

        :raises TypeError: if this entry is not a Subscribe or SubscribeAck
        """
        if self.sd_type not in (
            SOMEIPSDEntryType.Subscribe,
            SOMEIPSDEntryType.SubscribeAck,
        ):
            raise TypeError(
                f"SD entry is type {self.sd_type}, does not have eventgroup_counter"
            )
        return (self.minver_or_counter >> 16) & 0x0F

    @property
    def eventgroup_id(self) -> int:
        """
        the eventgroup id

        :raises TypeError: if this entry is not a Subscribe or SubscribeAck
        """
        if self.sd_type not in (
            SOMEIPSDEntryType.Subscribe,
            SOMEIPSDEntryType.SubscribeAck,
        ):
            raise TypeError(
                f"SD entry is type {self.sd_type}, does not have eventgroup_id"
            )
        return self.minver_or_counter & 0xFFFF

    @classmethod
    def parse(cls, buf: bytes, num_options: int) -> typing.Tuple[SOMEIPSDEntry, bytes]:
        """
        parses SOMEIP SD entry in `buf`

        :param buf: buffer containing SOMEIP SD entry
        :param num_options: number of known options in containing
            :class:`SOMEIPSDHeader`
        :raises ParseError: if the buffer did not parse as a SOMEIP SD entry, e.g., due
            to an unknown entry type or out-of-bounds option indexes
        :return: tuple (S, B) where S is the parsed :class:`SOMEIPSDEntry` instance and
            B is the unparsed rest of `buf`
        """
        (
            (sd_type_b, oi1, oi2, numopt, sid, iid, majv, ttl_hi, ttl_lo, val),
            buf_rest,
        ) = _unpack(cls.__format, buf)
        try:
            sd_type = SOMEIPSDEntryType(sd_type_b)
        except ValueError as exc:
            raise ParseError("bad someip sd entry type {sd_type_b:#x}") from exc

        no1 = numopt >> 4
        no2 = numopt & 0x0F
        ttl = (ttl_hi << 16) | ttl_lo

        if oi1 + no1 > num_options:
            raise ParseError(
                f"SD entry options_1 ({oi1}:{oi1+no1}) out of range ({num_options})"
            )

        if oi2 + no2 > num_options:
            raise ParseError(
                f"SD entry options_2 ({oi2}:{oi2+no2}) out of range ({num_options})"
            )

        if sd_type in (SOMEIPSDEntryType.Subscribe, SOMEIPSDEntryType.SubscribeAck):
            if val & 0xFFF00000:
                raise ParseError(
                    "expected counter and eventgroup_id to be 4 + 16-bit"
                    " with 12 upper bits zeros"
                )

        parsed = cls(
            sd_type=sd_type,
            option_index_1=oi1,
            option_index_2=oi2,
            num_options_1=no1,
            num_options_2=no2,
            service_id=sid,
            instance_id=iid,
            major_version=majv,
            ttl=ttl,
            minver_or_counter=val,
        )

        return parsed, buf_rest

    def build(self) -> bytes:
        """
        build the byte representation of this entry.

        :raises ValueError: if the option indexes on this entry were not resolved.
            see :meth:`assign_option_index`
        :raises struct.error: if any attribute was out of range for serialization
        :return: the byte representation
        """
        if self.options_resolved:
            raise ValueError("option indexes must be assigned before building")
        oi1 = typing.cast(int, self.option_index_1)
        oi2 = typing.cast(int, self.option_index_2)
        no1 = typing.cast(int, self.num_options_1)
        no2 = typing.cast(int, self.num_options_2)
        return self.__format.pack(
            self.sd_type.value,
            oi1,
            oi2,
            (no1 << 4) | no2,
            self.service_id,
            self.instance_id,
            self.major_version,
            self.ttl >> 16,
            self.ttl & 0xFFFF,
            self.minver_or_counter,
        )

