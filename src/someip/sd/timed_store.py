from __future__ import annotations

import asyncio
import collections
import itertools
import typing

import someip.header
import someip.config

from someip.config import _T_SOCKNAME as _T_SOCKADDR
from timing import TTL_FOREVER

KT = typing.TypeVar("KT")
_T_CALLBACK = typing.Callable[[KT, _T_SOCKADDR], None]

class TimedStore(typing.Generic[KT]):
    def __init__(self, log):
        self.log = log
        self.store: typing.Dict[
            _T_SOCKADDR,
            typing.Dict[
                KT,
                typing.Tuple[
                    typing.Callable[[KT, _T_SOCKADDR], None],
                    typing.Optional[asyncio.Handle],
                ],
            ],
        ] = collections.defaultdict(dict)

    def refresh(
        self,
        ttl,
        address: _T_SOCKADDR,
        entry: KT,
        callback_new: _T_CALLBACK[KT],
        callback_expired: _T_CALLBACK[KT],
    ) -> None:
        try:
            _, old_timeout_handle = self.store[address].pop(entry)
            if old_timeout_handle:
                old_timeout_handle.cancel()
        except KeyError:
            # pop failed => new entry
            callback_new(entry, address)

        timeout_handle = None
        if ttl != TTL_FOREVER:
            timeout_handle = asyncio.get_event_loop().call_later(
                ttl, self._expired, address, entry
            )

        self.store[address][entry] = (callback_expired, timeout_handle)

    def stop(self, address: _T_SOCKADDR, entry: KT) -> None:
        try:
            callback, _timeout_handle = self.store[address].pop(entry)
        except KeyError:
            # race-condition: service was already stopped. don't notify again
            return

        if _timeout_handle:
            _timeout_handle.cancel()

        # this must be called immediately - otherwise pairs of StopSubscribe/Subscribe
        # would not be handled correctly. If this were deferred to the event loop,
        # callback_new would also need to run deferred, but then NakSubscription errors
        # would not propagate to the sender
        callback(entry, address)

    def stop_all_for_address(self, address: _T_SOCKADDR) -> None:
        for entry, (callback, handle) in self.store[address].items():
            if handle:
                handle.cancel()
            asyncio.get_event_loop().call_soon(callback, entry, address)
        self.store[address].clear()

    def stop_all(self) -> None:
        for addr in self.store.keys():
            self.stop_all_for_address(addr)
        self.store.clear()

    def stop_all_matching(self, match: typing.Callable[[KT], bool]) -> None:
        stopping_entries = [
            (ep, entry)
            for ep, entries in self.store.items()
            for entry in entries
            if match(entry)
        ]

        for endpoint, entry in stopping_entries:
            self.stop(endpoint, entry)

    def _expired(self, address: _T_SOCKADDR, entry: KT) -> None:
        try:
            callback, _ = self.store[address].pop(entry)
        except KeyError:  # pragma: nocover
            self.log.warning(
                "race-condition: entry %r timeout was not in store but triggered"
                " anyway. forgot to cancel?",
                entry,
            )
            return

        asyncio.get_event_loop().call_soon(callback, entry, address)

    def entries(self) -> typing.Iterator[KT]:
        return itertools.chain.from_iterable(x.keys() for x in self.store.values())
