from __future__ import annotations

import asyncio
import collections
import dataclasses
import ipaddress
import itertools
import logging
import os
import platform
import random
import socket
import struct
import threading
import typing

import someip.header
import someip.config
from someip.config import _T_SOCKNAME as _T_SOCKADDR
_T_OPT_SOCKADDR = typing.Optional[_T_SOCKADDR]

class _SessionStorage:
    def __init__(self):
        self.incoming = {}
        self.outgoing: typing.DefaultDict[
            _T_OPT_SOCKADDR, typing.Tuple[bool, int]
        ] = collections.defaultdict(lambda: (True, 1))
        self.outgoing_lock = threading.Lock()

    def check_received(
        self, sender: _T_SOCKADDR, multicast: bool, flag: bool, session_id: int
    ) -> bool:
        """
        return true if a reboot was detected
        """
        k = (sender, multicast)

        try:
            old_flag, old_session_id = self.incoming[k]

            if flag and (
                not old_flag or (old_session_id > 0 and old_session_id >= session_id)
            ):
                return True
            return False
        except KeyError:
            # sender not yet known -> insert
            self.incoming[k] = (flag, session_id)
            return False
        finally:
            self.incoming[k] = (flag, session_id)

    def assign_outgoing(self, remote: _T_OPT_SOCKADDR):
        # need a lock for outgoing messages if they may be sent from separate threads
        # eg. when an application logic runs in a seperate thread from the SOMEIP stack
        # event loop
        with self.outgoing_lock:
            flag, _id = self.outgoing[remote]
            if _id >= 0xFFFF:
                # 4.2.1, TR_SOMEIP_00521
                # 4.2.1, TR_SOMEIP_00255
                self.outgoing[remote] = (False, 1)
            else:
                self.outgoing[remote] = (flag, _id + 1)
        return flag, _id

