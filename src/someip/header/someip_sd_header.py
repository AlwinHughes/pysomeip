from __future__ import annotations

import dataclasses
import struct
import typing

from .someip_sd_entry import SOMEIPSDEntry
from .someip_sd_option import SOMEIPSDOption
from .util import ParseError

@dataclasses.dataclass(frozen=True)
class SOMEIPSDHeader:
    """
    Represents a SOMEIP SD packet.
    """

    entries: typing.Tuple[SOMEIPSDEntry, ...]
    options: typing.Tuple[SOMEIPSDOption, ...] = ()
    flag_reboot: bool = False
    flag_unicast: bool = True
    flags_unknown: int = 0

    def resolve_options(self):
        """
        resolves all `entries`' options from `options` list.

        :return: a new :class:`SOMEIPSDHeader` instance with entries with resolved
            options
        """
        entries = [e.resolve_options(self.options) for e in self.entries]
        return dataclasses.replace(self, entries=tuple(entries))

    def assign_option_indexes(self):
        """
        assigns option indexes to all `entries` and builds the `options` list.

        :return: a new :class:`SOMEIPSDHeader` instance with entries with assigned
            options indexes
        """
        options = list(self.options)
        entries = [e.assign_option_index(options) for e in self.entries]
        return dataclasses.replace(self, entries=tuple(entries), options=tuple(options))

    def __str__(self):  # pragma: nocover
        entries = "\n".join(str(e) for e in self.entries)
        return f"""reboot={self.flag_reboot}, unicast={self.flag_unicast}, entries:
{entries}"""

    @classmethod
    def parse(cls, buf: bytes) -> typing.Tuple[SOMEIPSDHeader, bytes]:
        """
        parses SOMEIP SD packet in `buf`

        :param buf: buffer containing SOMEIP packet
        :raises ParseError: if the packet contained invalid data, such as out-of-bounds
            lengths or failing :meth:`SOMEIPSDEntry.parse` and
            :meth:`SOMEIPSDOption.parse`
        :return: tuple (S, B) where S is the parsed :class:`SOMEIPSDHeader` instance and
            B is the unparsed rest of `buf`
        """
        if len(buf) < 12:
            raise ParseError(f"can not parse SOMEIPSDHeader, got only {len(buf)} bytes")

        flags = buf[0]

        entries_length = struct.unpack("!I", buf[4:8])[0]
        rest_buf = buf[8:]
        if len(rest_buf) < entries_length + 4:
            raise ParseError(
                f"can not parse SOMEIPSDHeader, entries length too big"
                f" ({entries_length})"
            )
        entries_buffer, rest_buf = rest_buf[:entries_length], rest_buf[entries_length:]

        options_length = struct.unpack("!I", rest_buf[:4])[0]
        rest_buf = rest_buf[4:]
        if len(rest_buf) < options_length:
            raise ParseError(
                f"can not parse SOMEIPSDHeader, options length too big"
                f" ({options_length}"
            )
        options_buffer, rest_buf = rest_buf[:options_length], rest_buf[options_length:]

        options = []
        while options_buffer:
            option, options_buffer = SOMEIPSDOption.parse(options_buffer)
            options.append(option)

        entries = []
        while entries_buffer:
            entry, entries_buffer = SOMEIPSDEntry.parse(entries_buffer, len(options))
            entries.append(entry)

        flag_reboot = bool(flags & 0x80)
        flags &= ~0x80

        flag_unicast = bool(flags & 0x40)
        flags &= ~0x40

        parsed = cls(
            flag_reboot=flag_reboot,
            flag_unicast=flag_unicast,
            flags_unknown=flags,
            entries=tuple(entries),
            options=tuple(options),
        )
        return parsed, rest_buf

    def build(self) -> bytes:
        """
        builds the byte representation of this SOMEIP SD packet.

        :raises struct.error: if any attribute was out of range for serialization
        :raises ValueError: from :meth:`SOMEIPSDEntry.build`
        :return: the byte representation
        """
        flags = self.flags_unknown

        if self.flag_reboot:
            flags |= 0x80

        if self.flag_unicast:
            flags |= 0x40

        buf = bytearray([flags, 0, 0, 0])

        entries_buf = b"".join(e.build() for e in self.entries)
        options_buf = b"".join(e.build() for e in self.options)

        buf += struct.pack("!I", len(entries_buf))
        buf += entries_buf
        buf += struct.pack("!I", len(options_buf))
        buf += options_buf

        return buf
