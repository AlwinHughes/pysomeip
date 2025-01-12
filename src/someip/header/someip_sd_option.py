from __future__ import annotations

import abc
import dataclasses
import typing
import struct

from .util import _unpack
from .util import ParseError


class SOMEIPSDOption(metaclass=abc.ABCMeta):
    """
    Abstract base class representing SD options
    """

    __format: typing.ClassVar[struct.Struct] = struct.Struct("!HB")
    _options: typing.ClassVar[
        typing.Dict[int, typing.Type[SOMEIPSDAbstractOption]]
    ] = {}

    @classmethod
    def register(
        cls, option_cls: typing.Type[SOMEIPSDAbstractOption]
    ) -> typing.Type[SOMEIPSDAbstractOption]:
        """
        Decorator for SD option classes, to register them for option parsing, identified
        by their :attr:`SOMEIPSDAbstractOption.type` members.
        """
        cls._options[option_cls.type] = option_cls
        return option_cls

    @classmethod
    def parse(cls, buf: bytes) -> typing.Tuple[SOMEIPSDOption, bytes]:
        """
        parses SOMEIP SD option in `buf`. Options with unknown types will be parsed as
        :class:`SOMEIPSDUnknownOption`, known types will be parsed to their registered
        types.

        :param buf: buffer containing SOMEIP SD option
        :raises ParseError: if the buffer did not parse as a SOMEIP SD option, e.g., due
            to out-of-bounds lengths or the specific
            :meth:`SOMEIPSDAbstractOption.parse_option` failed
        :return: tuple (S, B) where S is the parsed :class:`SOMEIPSDOption` instance and
            B is the unparsed rest of `buf`
        """
        (len_b, type_b), buf_rest = _unpack(cls.__format, buf)
        if len(buf_rest) < len_b:
            raise ParseError(
                f"option data too short, expected {len_b}, got {buf_rest!r}"
            )
        opt_b, buf_rest = buf_rest[:len_b], buf_rest[len_b:]

        opt_cls = cls._options.get(type_b)
        if not opt_cls:
            return SOMEIPSDUnknownOption(type=type_b, payload=opt_b), buf_rest

        return opt_cls.parse_option(opt_b), buf_rest

    def build_option(self, type_b: int, buf: bytes) -> bytes:
        """
        Helper for SD option classes to build the byte representation of their option.

        :param type_b: option type identifier
        :param buf: buffer SD option data
        :raises struct.error: if the buffer is too big to be represented, or `type_b` is
            out of range
        :return: the byte representation
        """
        return self.__format.pack(len(buf), type_b) + buf

    @abc.abstractmethod
    def build(self) -> bytes:
        """
        build the byte representation of this option, must be implemented by actual
        options. Should use :meth:`build_option` to build the option header.

        :raises struct.error: if any attribute was out of range for serialization
        :return: the byte representation
        """
        ...

@dataclasses.dataclass(frozen=True)
class SOMEIPSDUnknownOption(SOMEIPSDOption):
    """
    Received options with unknown option types are parsed as this generic class.

    :param type: the type identifier for this unknown option
    :param payload: the option payload
    """

    type: int
    payload: bytes

    def build(self) -> bytes:
        """
        build the byte representation of this option.

        :raises struct.error: if :attr:`payload` is too big to be represented, or
            :attr:`type` is out of range
        :return: the byte representation
        """
        return self.build_option(self.type, self.payload)


class SOMEIPSDAbstractOption(SOMEIPSDOption):
    """
    Base class for specific option implementations.
    """

    type: typing.ClassVar[int]
    """
    Class variable. Used to differentiate SD option types when parsing. See
    :meth:`SOMEIPSDOption.register` and :meth:`SOMEIPSDOption.parse`
    """

    @classmethod
    @abc.abstractmethod
    def parse_option(cls, buf: bytes) -> SOMEIPSDAbstractOption:
        """
        parses SD option payload in `buf`.

        :param buf: buffer containing SOMEIP SD option data
        :raises ParseError: if this option type fails to parse `buf`
        :return: the parsed instance
        """
        ...
