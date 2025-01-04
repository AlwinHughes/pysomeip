from __future__ import annotations

import asyncio
import typing

import someip.header
import someip.config
from someip.config import _T_SOCKNAME as _T_SOCKADDR
from someip.config import _T_SOCKNAME as _T_SOCKADDR
from someip.utils import log_exceptions, wait_cancelled
from interfaces import ServerServiceListener
from service_announcer import ServiceAnnouncer
from timings import Timings
from timed_store import TimedStore

_T_OPT_SOCKADDR = typing.Optional[_T_SOCKADDR]

class ServiceInstance:
    def __init__(
        self,
        service: someip.config.Service,
        listener: ServerServiceListener,
        announcer: ServiceAnnouncer,
        timings: Timings,
    ):
        self.service = service
        self.listener = listener
        self.announcer = announcer
        self.timings = timings

        self.log = announcer.log.getChild(
            f"service_{service.service_id:04x}.instance_{service.instance_id:04x}"
        )

        self._can_answer_offers = False
        self._task: typing.Optional[asyncio.Task[None]] = None
        self.subscriptions: TimedStore[EventgroupSubscription] = TimedStore(self.log)

    def __repr__(self):
        return f"<ServiceInstance {self.service}>"

    def start(self, loop=None):
        if self._task is not None:  # pragma: nocover
            raise RuntimeError("task already started")

        self._can_answer_offers = False
        self._task = asyncio.create_task(self._offer_task())

    def stop(self):
        if self._task is None:  # pragma: nocover
            raise RuntimeError("task already stopped")

        self._task.cancel()
        asyncio.create_task(wait_cancelled(self._task))
        self._task = None

        # cyclic tasks send stop when they are cancelled
        if not self.timings.CYCLIC_OFFER_DELAY:
            self._send_offer(stop=True)

        self.subscriptions.stop_all()

    @log_exceptions()
    async def _offer_task(self) -> None:
        ttl = self.timings.ANNOUNCE_TTL
        if ttl is not TTL_FOREVER and (
            not self.timings.CYCLIC_OFFER_DELAY
            or self.timings.CYCLIC_OFFER_DELAY >= ttl
        ):
            self.log.warning(
                "CYCLIC_OFFER_DELAY=%r too long for TTL=%r."
                " expect connectivity issues",
                self.timings.CYCLIC_OFFER_DELAY,
                ttl,
            )
        await asyncio.sleep(
            random.uniform(
                self.timings.INITIAL_DELAY_MIN, self.timings.INITIAL_DELAY_MAX
            )
        )
        self._send_offer()

        try:
            self._can_answer_offers = True
            for i in range(self.timings.REPETITIONS_MAX):
                await asyncio.sleep((2 ** i) * self.timings.REPETITIONS_BASE_DELAY)
                self._send_offer()

            if not self.timings.CYCLIC_OFFER_DELAY:  # 4.2.1 SWS_SD_00451
                return

            while True:
                # 4.2.1 SWS_SD_00450
                await asyncio.sleep(self.timings.CYCLIC_OFFER_DELAY)
                self._send_offer()
        except asyncio.CancelledError:
            self._can_answer_offers = False
            raise
        finally:
            if self.timings.CYCLIC_OFFER_DELAY:
                self._send_offer(stop=True)

    def _send_offer(self, remote: _T_OPT_SOCKADDR = None, stop: bool = False) -> None:
        entry = self.service.create_offer_entry(
            self.timings.ANNOUNCE_TTL if not stop else 0
        )
        self.announcer.queue_send(entry, remote=remote)

    def matches_find(
        self, entry: someip.header.SOMEIPSDEntry, addr: _T_SOCKADDR
    ) -> bool:
        if not self._can_answer_offers:
            # 4.2.1 SWS_SD_00319
            self.log.info(
                "ignoring FindService from %s during Initial Wait Phase: %s",
                format_address(addr),
                entry,
            )
            return False

        return self.service.matches_find(entry)

    def handle_subscribe(
        self,
        entry: someip.header.SOMEIPSDEntry,
        addr: _T_SOCKADDR,
    ) -> bool:
        if self._task is None:
            return False

        if not self.service.matches_subscribe(entry):
            return False

        subscription = EventgroupSubscription.from_subscribe_entry(entry)
        if entry.ttl == 0:
            self.eventgroup_subscribe_stopped(addr, subscription)
            return True

        try:
            self.subscriptions.refresh(
                subscription.ttl,
                addr,
                subscription,
                self.listener.client_subscribed,
                self.listener.client_unsubscribed,
            )
        except NakSubscription:
            self.announcer._send_subscribe_nack(subscription, addr)
        else:
            self.announcer.queue_send(subscription.to_ack_entry(), remote=addr)

        return True

    def eventgroup_subscribe_stopped(
        self, addr: _T_SOCKADDR, subscription: EventgroupSubscription
    ) -> None:
        self.subscriptions.stop(addr, subscription)

    def reboot_detected(self, addr: _T_SOCKADDR) -> None:
        self.subscriptions.stop_all_for_address(addr)

