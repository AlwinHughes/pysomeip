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

from .interfaces import IServiceDiscoveryProtocol
from .interfaces import ClientServiceListener
from .timed_store import TimedStore
from .auto_subscriber import AutoSubscribeServiceListener

LOG = logging.getLogger("someip.sd")
_T_IPADDR = typing.Union[ipaddress.IPv4Address, ipaddress.IPv6Address]
_T_OPT_SOCKADDR = typing.Optional[_T_SOCKADDR]

class ServiceDiscover:
    def __init__(self, sd: IServiceDiscoveryProtocol):
        self.sd = sd
        self.timings = sd.timings
        self.log = sd.log.getChild("discover")

        self.watched_services: typing.Dict[
            someip.config.Service,
            typing.Set[ClientServiceListener],
        ] = collections.defaultdict(set)
        self.watcher_all_services: typing.Set[ClientServiceListener] = set()

        self.found_services: TimedStore[someip.config.Service] = TimedStore(self.log)
        self.task: typing.Optional[asyncio.Task[None]] = None

    def start(self):
        if self.task is not None and not self.task.done():  # pragma: nocover
            return

        loop = asyncio.get_running_loop()
        self.task = loop.create_task(self.send_find_services())

    def stop(self):
        if self.task:  # pragma: nobranch
            self.task.cancel()
            asyncio.create_task(wait_cancelled(self.task))
            self.task = None

    def handle_offer(
        self, entry: someip.header.SOMEIPSDEntry, addr: _T_SOCKADDR
    ) -> None:
        if not self.is_watching_service(entry):
            return
        if entry.ttl == 0:
            self.service_offer_stopped(addr, entry)
        else:
            self.service_offered(addr, entry)

    def is_watching_service(self, entry: someip.header.SOMEIPSDEntry):
        if self.watcher_all_services:
            return True
        return any(s.matches_offer(entry) for s in self.watched_services.keys())

    def watch_service(
        self, service: someip.config.Service, listener: ClientServiceListener
    ) -> None:
        self.watched_services[service].add(listener)

        for addr, services in self.found_services.store.items():
            for s in services:
                if service.matches_service(s):
                    asyncio.get_event_loop().call_soon(
                        listener.service_offered, s, addr
                    )

    def stop_watch_service(
        self, service: someip.config.Service, listener: ClientServiceListener
    ) -> None:
        self.watched_services[service].remove(listener)

        # TODO verify if this makes sense
        for addr, services in self.found_services.store.items():
            for s in services:
                if service.matches_service(s):
                    asyncio.get_event_loop().call_soon(
                        listener.service_stopped, s, addr
                    )

    def watch_all_services(self, listener: ClientServiceListener) -> None:
        self.watcher_all_services.add(listener)

        for addr, services in self.found_services.store.items():
            for s in services:
                asyncio.get_event_loop().call_soon(listener.service_offered, s, addr)

    def stop_watch_all_services(self, listener: ClientServiceListener) -> None:
        self.watcher_all_services.remove(listener)

        # TODO verify if this makes sense
        for addr, services in self.found_services.store.items():
            for s in services:
                asyncio.get_event_loop().call_soon(listener.service_stopped, s, addr)

    def find_subscribe_eventgroup(self, eventgroup: someip.config.Eventgroup):
        self.watch_service(
            eventgroup.as_service(),
            AutoSubscribeServiceListener(self.sd.subscriber, eventgroup),
        )

    def stop_find_subscribe_eventgroup(self, eventgroup: someip.config.Eventgroup):
        self.stop_watch_service(
            eventgroup.as_service(),
            AutoSubscribeServiceListener(self.sd.subscriber, eventgroup),
        )

    def _service_found(self, service: someip.config.Service) -> bool:
        return any(service.matches_service(s) for s in self.found_services.entries())

    async def send_find_services(self):
        if not self.watched_services:
            return

        def _build_entries():
            return [
                service.create_find_entry(self.timings.FIND_TTL)
                for service in self.watched_services.keys()
                if not self._service_found(service)  # 4.2.1: SWS_SD_00365
            ]

        await asyncio.sleep(
            random.uniform(
                self.timings.INITIAL_DELAY_MIN, self.timings.INITIAL_DELAY_MAX
            )
        )
        find_entries = _build_entries()
        if not find_entries:
            return
        self.sd.send_sd(find_entries)  # 4.2.1: SWS_SD_00353

        for i in range(self.timings.REPETITIONS_MAX):
            await asyncio.sleep(
                (2 ** i) * self.timings.REPETITIONS_BASE_DELAY
            )  # 4.2.1: SWS_SD_00363

            find_entries = _build_entries()
            if not find_entries:
                return
            self.sd.send_sd(find_entries)  # 4.2.1: SWS_SD_00457

    def service_offered(self, addr: _T_SOCKADDR, entry: someip.header.SOMEIPSDEntry):
        service = someip.config.Service.from_offer_entry(entry)

        self.found_services.refresh(
            entry.ttl,
            addr,
            service,
            self._notify_service_offered,
            self._notify_service_stopped,
        )

    def connection_lost(self, exc: typing.Optional[Exception]) -> None:
        self.found_services.stop_all()

    def service_offer_stopped(
        self, addr: _T_SOCKADDR, entry: someip.header.SOMEIPSDEntry
    ) -> None:
        service = someip.config.Service.from_offer_entry(entry)

        self.found_services.stop(addr, service)

    def reboot_detected(self, addr: _T_SOCKADDR) -> None:
        # notify stop for each service of rebooted instance.
        # reboot_detected() is called before sd_message_received(), so any offered
        # service in this message will cause a new notify
        self.found_services.stop_all_for_address(addr)

    def _notify_service_offered(
        self, service: someip.config.Service, source: _T_SOCKADDR
    ) -> None:
        for service_filter, listeners in self.watched_services.items():
            if service_filter.matches_service(service):
                for listener in listeners:
                    listener.service_offered(service, source)
        for listener in self.watcher_all_services:
            listener.service_offered(service, source)

    def _notify_service_stopped(
        self, service: someip.config.Service, source: _T_SOCKADDR
    ) -> None:
        for service_filter, listeners in self.watched_services.items():
            if service_filter.matches_service(service):
                for listener in listeners:
                    listener.service_stopped(service, source)
        for listener in self.watcher_all_services:
            listener.service_stopped(service, source)
