# from __future__ import annotations
#
# import asyncio
# import collections
# import dataclasses
# import ipaddress
# import itertools
# import logging
# import os
# import platform
# import random
# import socket
# import struct
# import threading
# import typing
#
# import someip.header
# import someip.config
# from someip.config import _T_SOCKNAME as _T_SOCKADDR
# from someip.utils import log_exceptions, wait_cancelled
#
# LOG = logging.getLogger("someip.sd")
# _T_IPADDR = typing.Union[ipaddress.IPv4Address, ipaddress.IPv6Address]
# _T_OPT_SOCKADDR = typing.Optional[_T_SOCKADDR]
#
#
#
#
#
# KT = typing.TypeVar("KT")
# _T_CALLBACK = typing.Callable[[KT, _T_SOCKADDR], None]
#
#
#
#
#
# _T_SL = typing.Tuple[someip.config.Service, ServerServiceListener]
#
#
#
#
