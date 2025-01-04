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
from someip.utils import log_exceptions, wait_cancelled

from interfaces import IServiceDiscoveryProtocol

LOG = logging.getLogger("someip.sd")
_T_IPADDR = typing.Union[ipaddress.IPv4Address, ipaddress.IPv6Address]
_T_OPT_SOCKADDR = typing.Optional[_T_SOCKADDR]


class ServiceSubscriber:
    """
    datagram protocol for subscribing to eventgroups via SOME/IP SD

    example:
        TODO
    """

    def __init__(self, sd: IServiceDiscoveryProtocol):
        self.sd = sd
        self.timings = sd.timings
        self.log = sd.log.getChild("subscribe")

        ttl = self.timings.SUBSCRIBE_TTL
        refresh_interval = self.timings.SUBSCRIBE_REFRESH_INTERVAL

        if not refresh_interval and ttl < TTL_FOREVER:  # pragma: nocover
            self.log.warning(
                "no refresh, but ttl=%r set. expect lost connection after ttl", ttl
            )
        elif refresh_interval and refresh_interval >= ttl:  # pragma: nocover
            self.log.warning(
                "refresh_interval=%r too high for ttl=%r. expect dropped updates.",
                refresh_interval,
                ttl,
            )

        self.task: typing.Optional[asyncio.Task[None]] = None
        # separate alive tracking (instead of using task.done()) as task will only run
        # for one iteration when ttl=None
        self.alive = False

        self.subscribeentries: typing.List[
            typing.Tuple[someip.config.Eventgroup, _T_SOCKADDR],
        ] = []

    def subscribe_eventgroup(
        self, eventgroup: someip.config.Eventgroup, endpoint: _T_SOCKADDR
    ) -> None:
        """
        eventgroup:
          someip.config.Eventgroup that describes the eventgroup to subscribe to and the
          local endpoint that accepts the notifications
        endpoint:
          remote SD endpoint that will receive the subscription messages
        """
        # relies on _subscribe() to send out the Subscribe messages in the next cycle.
        self.subscribeentries.append((eventgroup, endpoint))

        if self.alive:
            asyncio.get_event_loop().call_soon(
                self._send_start_subscribe, endpoint, [eventgroup]
            )

    def stop_subscribe_eventgroup(
        self,
        eventgroup: someip.config.Eventgroup,
        endpoint: _T_SOCKADDR,
        send: bool = True,
    ) -> None:
        """
        eventgroup:
          someip.config.Eventgroup that describes the eventgroup to unsubscribe from
        endpoint:
          remote SD endpoint that will receive the subscription messages
        """
        try:
            self.subscribeentries.remove((eventgroup, endpoint))
        except ValueError:
            return

        if send:
            asyncio.get_event_loop().call_soon(
                self._send_stop_subscribe, endpoint, [eventgroup]
            )

    def _send_stop_subscribe(
        self, remote: _T_SOCKADDR, entries: typing.Collection[someip.config.Eventgroup]
    ) -> None:
        self._send_subscribe(0, remote, entries)

    def _send_start_subscribe(
        self, remote: _T_SOCKADDR, entries: typing.Collection[someip.config.Eventgroup]
    ) -> None:
        self._send_subscribe(self.timings.SUBSCRIBE_TTL, remote, entries)


    def _send_subscribe(
        self,
        ttl: int,
        remote: _T_SOCKADDR,
        entries: typing.Collection[someip.config.Eventgroup],
    ) -> None:
        self.sd.send_sd(
            [e.create_subscribe_entry(ttl=ttl) for e in entries], remote=remote
        )

    def start(self, loop=None) -> None:
        if self.alive:  # pragma: nocover
            return
        if loop is None:  # pragma: nobranch
            loop = asyncio.get_event_loop()

        self.alive = True
        self.task = loop.create_task(self._subscribe())

    def stop(self, send_stop_subscribe=True) -> None:
        if not self.alive:
            return

        self.alive = False

        if self.task:  # pragma: nobranch
            self.task.cancel()
            asyncio.create_task(wait_cancelled(self.task))
            self.task = None

        if send_stop_subscribe:
            for endpoint, entries in self._group_entries().items():
                asyncio.get_event_loop().call_soon(
                    self._send_stop_subscribe, endpoint, entries
                )

    def _group_entries(
        self,
    ) -> typing.Mapping[_T_SOCKADDR, typing.Collection[someip.config.Eventgroup]]:
        endpoint_entries: typing.DefaultDict[
            _T_SOCKADDR, typing.List[someip.config.Eventgroup]
        ] = collections.defaultdict(list)
        for eventgroup, endpoint in self.subscribeentries:
            endpoint_entries[endpoint].append(eventgroup)
        return endpoint_entries

    @log_exceptions()
    async def _subscribe(self) -> None:
        while True:
            for endpoint, entries in self._group_entries().items():
                self._send_start_subscribe(endpoint, entries)

            if self.timings.SUBSCRIBE_REFRESH_INTERVAL is None:
                break

            try:
                await asyncio.sleep(self.timings.SUBSCRIBE_REFRESH_INTERVAL)
            except asyncio.CancelledError:
                break

    def reboot_detected(self, addr: _T_SOCKADDR) -> None:
        # TODO
        pass

    def connection_lost(self, exc: typing.Optional[Exception]) -> None:
        self.stop(send_stop_subscribe=False)
