from __future__ import annotations

import dataclasses
import struct
import typing

from .someip_sd_option import SOMEIPSDAbstractOption
from .someip_sd_option import SOMEIPSDOption
from .util import ParseError

@SOMEIPSDOption.register
@dataclasses.dataclass(frozen=True)
class SOMEIPSDConfigOption(SOMEIPSDAbstractOption):
    type: typing.ClassVar[int] = 1
    configs: typing.Tuple[typing.Tuple[str, typing.Optional[str]], ...]

    @classmethod
    def parse_option(cls, buf: bytes) -> SOMEIPSDConfigOption:
        if len(buf) < 2:
            raise ParseError(
                f"SD config option with wrong payload length {len(buf)} < 2"
            )

        b = buf[1:]
        nextlen, b = b[0], b[1:]

        configs: typing.List[typing.Tuple[str, typing.Optional[str]]] = []

        while nextlen != 0:
            if len(b) < nextlen + 1:
                raise ParseError(
                    f"SD config option length {nextlen} too big for remaining"
                    f" option buffer {b!r}"
                )

            cfg_str, b = b[:nextlen], b[nextlen:]

            split = cfg_str.find(b"=")
            if split == -1:
                configs.append((cfg_str.decode("ascii"), None))
            else:
                key, value = cfg_str[:split], cfg_str[split + 1 :]
                configs.append((key.decode("ascii"), value.decode("ascii")))
            nextlen, b = b[0], b[1:]
        return cls(configs=tuple(configs))

    def build(self) -> bytes:
        """
        build the byte representation of this option.

        :raises struct.error: if :attr:`payload` is too big to be represented, or
            :attr:`type` is out of range
        :return: the byte representation
        """
        buf = bytearray([0])
        for k, v in self.configs:
            if v is not None:
                buf.append(len(k) + len(v) + 1)
                buf += k.encode("ascii")
                buf += b"="
                buf += v.encode("ascii")
            else:
                buf.append(len(k))
                buf += k.encode("ascii")
        buf.append(0)
        return self.build_option(self.type, buf)

