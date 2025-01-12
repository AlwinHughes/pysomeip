from __future__ import annotations

import enum
import socket


class SOMEIPMessageType(enum.IntEnum):
    REQUEST = 0
    REQUEST_NO_RETURN = 1
    NOTIFICATION = 2
    REQUEST_ACK = 0x40
    REQUEST_NO_RETURN_ACK = 0x41
    NOTIFICATION_ACK = 0x42
    RESPONSE = 0x80
    ERROR = 0x81
    RESPONSE_ACK = 0xC0
    ERROR_ACK = 0xC1


class SOMEIPReturnCode(enum.IntEnum):
    E_OK = 0
    E_NOT_OK = 1
    E_UNKNOWN_SERVICE = 2
    E_UNKNOWN_METHOD = 3
    E_NOT_READY = 4
    E_NOT_REACHABLE = 5
    E_TIMEOUT = 6
    E_WRONG_PROTOCOL_VERSION = 7
    E_WRONG_INTERFACE_VERSION = 8
    E_MALFORMED_MESSAGE = 9
    E_WRONG_MESSAGE_TYPE = 10


class SOMEIPSDEntryType(enum.IntEnum):
    FindService = 0
    OfferService = 1
    Subscribe = 6
    SubscribeAck = 7


class L4Protocols(enum.IntEnum):
    """
    Enum for valid layer 4 protocol identifiers.
    """

    TCP = socket.IPPROTO_TCP
    UDP = socket.IPPROTO_UDP
