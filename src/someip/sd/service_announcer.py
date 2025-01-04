from __future__ import annotations

import asyncio
import typing

import someip.header
import someip.config

from sd_protocol import ServiceDiscoveryProtocol
from service_instance import ServiceInstance
from send_collector import SendCollector
from someip.config import _T_SOCKNAME as _T_SOCKADDR
from event_group_sub import EventGroupSubscription
from util import format_address


_T_OPT_SOCKADDR = typing.Optional[_T_SOCKADDR]

class ServiceAnnouncer:
    # TODO doc
    def __init__(self, sd: ServiceDiscoveryProtocol):
        self.sd = sd
        self.timings = sd.timings
        self.log = sd.log.getChild("announce")

        self.started = False
        self.announcing_services: typing.List[ServiceInstance] = []
        self.send_queues: typing.Dict[
            _T_OPT_SOCKADDR, SendCollector[someip.header.SOMEIPSDEntry]
        ] = {}

    def queue_send(
        self, entry: someip.header.SOMEIPSDEntry, remote: _T_OPT_SOCKADDR = None
    ) -> None:
        if self.timings.SEND_COLLECTION_TIMEOUT == 0:
            self.sd.send_sd([entry], remote=remote)
            return

        queue = self.send_queues.get(remote)
        if queue is None or queue.done:
            self.send_queues[remote] = queue = SendCollector(
                self.timings.SEND_COLLECTION_TIMEOUT, self.sd.send_sd, remote=remote
            )

        # FIXME stops and starts for the same instance in the same queue make no sense
        # and should probably be cleaned out
        queue.append(entry)

    def announce_service(self, instance: ServiceInstance) -> None:
        if self.started:
            instance.start()
        self.announcing_services.append(instance)

    def stop_announce_service(self, instance: ServiceInstance, send_stop=True) -> None:
        """
        stops announcing previously started service

        :param instance: service instance to be stopped
        :raises ValueError: if the service was not announcing
        """
        self.announcing_services.remove(instance)
        if send_stop and self.started:
            instance.stop()

    def handle_subscribe(
        self,
        entry: someip.header.SOMEIPSDEntry,
        addr: _T_SOCKADDR,
    ) -> None:

        matching_services = []

        for instance in self.announcing_services:
            if instance.handle_subscribe(entry, addr):
                matching_services.append(instance)

        if not matching_services:
            self.log.warning(
                "discarding subscribe for unknown service from %s: %s",
                format_address(addr),
                entry,
            )
            subscription = EventgroupSubscription.from_subscribe_entry(entry)
            self._send_subscribe_nack(subscription, addr)
            return

        if len(matching_services) > 1:
            self.log.warning(
                "multiple configured services matched subscribe %s from %s: %s",
                entry,
                format_address(addr),
                matching_services,
            )

    def _send_subscribe_nack(
        self, subscription: EventgroupSubscription, addr: _T_SOCKADDR
    ) -> None:
        self.queue_send(subscription.to_nack_entry(), remote=addr)

    def handle_findservice(
        self,
        entry: someip.header.SOMEIPSDEntry,
        addr: _T_SOCKADDR,
        received_over_multicast: bool,
    ) -> None:
        self.log.info("received from %s: %s", format_address(addr), entry)

        matching_instances = []

        for instance in self.announcing_services:
            if instance.matches_find(entry, addr):
                matching_instances.append(instance)

        if not matching_instances:
            return

        # R21-11 PRS_SOMEIPSD_00423 not implemented because it's unclear how it should
        # behave for multiple services with different offer periods

        # R21-11 PRS_SOMEIPSD_00417 and PRS_SOMEIPSD_00419
        if received_over_multicast:
            # R21-11 PRS_SOMEIPSD_00420 and PRS_SOMEIPSD_00421
            delay = random.uniform(
                self.timings.REQUEST_RESPONSE_DELAY_MIN,
                self.timings.REQUEST_RESPONSE_DELAY_MAX,
            )

            def call(func) -> None:
                asyncio.get_event_loop().call_later(delay, func, addr)

        else:

            def call(func) -> None:
                asyncio.get_event_loop().call_soon(func, addr)

        for instance in matching_instances:
            call(instance._send_offer)

    def start(self, loop=None):
        for instance in self.announcing_services:
            instance.start()
        self.started = True

    def stop(self):
        for instance in self.announcing_services:
            instance.stop()
        self.started = False

    def connection_lost(self, exc: typing.Optional[Exception]) -> None:
        self.stop()

    def reboot_detected(self, addr: _T_SOCKADDR) -> None:
        for instance in self.announcing_services:
            instance.reboot_detected(addr)
