from __future__ import annotations

import dataclasses
import struct
import typing

from .someip_sd_option import SOMEIPSDAbstractOption
from .someip_sd_option import SOMEIPSDOption
from .util import ParseError

@SOMEIPSDOption.register
@dataclasses.dataclass(frozen=True)
class SOMEIPSDLoadBalancingOption(SOMEIPSDAbstractOption):
    type: typing.ClassVar[int] = 2
    priority: int
    weight: int

    @classmethod
    def parse_option(cls, buf: bytes) -> SOMEIPSDLoadBalancingOption:
        if len(buf) != 5:
            raise ParseError(
                f"SD load balancing option with wrong payload length {len(buf)} != 5"
            )

        prio, weight = struct.unpack("!HH", buf[1:])
        return cls(priority=prio, weight=weight)

    def build(self) -> bytes:
        """
        build the byte representation of this option.

        :raises struct.error: if :attr:`payload` is too big to be represented, or
            :attr:`type` is out of range
        :return: the byte representation
        """
        return self.build_option(
            self.type, struct.pack("!BHH", 0, self.priority, self.weight)
        )

