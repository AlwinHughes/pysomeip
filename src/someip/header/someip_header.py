from __future__ import annotations

import asyncio
import dataclasses
import struct
import typing

from .enums import SOMEIPReturnCode  
from .enums import SOMEIPMessageType
from .util import _unpack
from .util import ParseError
from .util import IncompleteReadError

@dataclasses.dataclass(frozen=True)
class SOMEIPHeader:
    """
    Represents a top-level SOMEIP packet (header and payload).
    """

    __format: typing.ClassVar[struct.Struct] = struct.Struct("!HHIHHBBBB")
    service_id: int
    method_id: int
    client_id: int
    session_id: int
    interface_version: int
    message_type: SOMEIPMessageType
    protocol_version: int = 1
    return_code: SOMEIPReturnCode = SOMEIPReturnCode.E_OK
    payload: bytes = b""

    @property
    def description(self):  # pragma: nocover
        return f"""service: 0x{self.service_id:04x}
method: 0x{self.method_id:04x}
client: 0x{self.client_id:04x}
session: 0x{self.session_id:04x}
protocol: {self.protocol_version}
interface: 0x{self.interface_version:02x}
message: {self.message_type.name}
return code: {self.return_code.name}
payload: {len(self.payload)} bytes"""

    def __str__(self):  # pragma: nocover
        return (
            f"service=0x{self.service_id:04x}, method=0x{self.method_id:04x},"
            f" client=0x{self.client_id:04x}, session=0x{self.session_id:04x},"
            f" protocol={self.protocol_version},"
            f" interface=0x{self.interface_version:02x},"
            f" message={self.message_type.name}, returncode={self.return_code.name},"
            f" payload: {len(self.payload)} bytes"
        )

    @classmethod
    def _parse_header(
        cls, parsed
    ) -> typing.Tuple[int, typing.Callable[[bytes], SOMEIPHeader]]:
        sid, mid, size, cid, sessid, pv, iv, mt_b, rc_b = parsed
        if pv != 1:
            raise ParseError(f"bad someip protocol version 0x{pv:02x}, expected 0x01")

        try:
            mt = SOMEIPMessageType(mt_b)
        except ValueError as exc:
            raise ParseError("bad someip message type {mt_b:#x}") from exc
        try:
            rc = SOMEIPReturnCode(rc_b)
        except ValueError as exc:
            raise ParseError("bad someip return code {rc_b:#x}") from exc

        if size < 8:
            raise ParseError("SOMEIP length must be at least 8")

        return (
            size,
            lambda payload_b: cls(
                service_id=sid,
                method_id=mid,
                client_id=cid,
                session_id=sessid,
                protocol_version=pv,
                interface_version=iv,
                message_type=mt,
                return_code=rc,
                payload=payload_b,
            ),
        )

    @classmethod
    def parse(cls, buf: bytes) -> typing.Tuple[SOMEIPHeader, bytes]:
        """
        parses SOMEIP packet in `buf`

        :param buf: buffer containing SOMEIP packet
        :raises IncompleteReadError: if the buffer did not contain enough data to unpack
            the SOMEIP packet. Either there was less data than one SOMEIP header length,
            or the size in the header was too big
        :raises ParseError: if the packet contained invalid data, such as an unknown
            message type or return code
        :return: tuple (S, B) where S is the parsed :class:`SOMEIPHeader` instance and B
            is the unparsed rest of `buf`
        """
        parsed, buf_rest = _unpack(cls.__format, buf)
        size, builder = cls._parse_header(parsed)
        if len(buf_rest) < size - 8:
            raise IncompleteReadError(
                f"packet too short, expected {size+4}, got {len(buf)}"
            )
        payload_b, buf_rest = buf_rest[: size - 8], buf_rest[size - 8 :]

        parsed = builder(payload_b)

        return parsed, buf_rest

    @classmethod
    async def read(cls, reader: asyncio.StreamReader) -> SOMEIPHeader:
        """
        reads a SOMEIP packet from `reader`. Waits until one full SOMEIP packet is
        available from the stream.

        :param reader: (usually TCP) stream to parse into SOMEIP packets
        :raises ParseError: if the packet contained invalid data, such as an unknown
            message type or return code
        :return: the parsed :class:`SOMEIPHeader` instance
        """
        hdr_b = await reader.readexactly(cls.__format.size)
        parsed = cls.__format.unpack(hdr_b)
        size, builder = cls._parse_header(parsed)

        payload_b = await reader.readexactly(size - 8)

        return builder(payload_b)

    def build(self) -> bytes:
        """
        builds the byte representation of this SOMEIP packet.

        :raises struct.error: if any attribute was out of range for serialization
        :return: the byte representation
        """
        size = len(self.payload) + 8
        hdr = self.__format.pack(
            self.service_id,
            self.method_id,
            size,
            self.client_id,
            self.session_id,
            self.protocol_version,
            self.interface_version,
            self.message_type.value,
            self.return_code.value,
        )
        return hdr + self.payload
