from __future__ import annotations

import asyncio
import typing

import someip.utils as utils
import someip.header as header

class SimpleEventgroup:
    """
    set :attr:`values` to the current value, call :meth:`notify_once` to immediately
    notify subscribers about new value.

    New subscribers will be notified about the current :attr:`values`.
    """

    def __init__(
        self, service: SimpleService, id: int, interval: typing.Optional[float] = None
    ):
        """
        :param service: the service this group belongs to
        :param id: the event group ID that this group can be subscribed on
        """
        self.id = id
        self.service = service
        self.log = service.log.getChild(f"evgrp-{id:04x}")

        self.subscribed_endpoints: typing.Set[header.EndpointOption[typing.Any]] = set()

        self.notification_task: typing.Optional[asyncio.Task[None]] = None
        if interval:
            self.notification_task = asyncio.create_task(self.cyclic_notify(interval))

        self.has_clients = asyncio.Event()

        self.values: typing.Dict[int, bytes] = {}
        """
        the current value for each event to send out as notification payload.
        """

    @utils.log_exceptions()
    async def _notify_single(
        self,
        endpoint: header.EndpointOption[typing.Any],
        events: typing.Iterable[int],
        label: str,
    ) -> None:
        addr = await endpoint.addrinfo()

        msgbuf = bytearray()
        for event_id in events:
            payload = self.values[event_id]

            self.log.info("%s notify 0x%04x to %r: %r", label, event_id, addr, payload)

            _, session_id = self.service.session_storage.assign_outgoing(addr)
            hdr = header.SOMEIPHeader(
                service_id=self.service.service_id,
                method_id=0x8000 | event_id,
                client_id=0,
                session_id=session_id,
                message_type=header.SOMEIPMessageType.NOTIFICATION,
                interface_version=self.service.version_major,
                payload=payload,
            )

            msgbuf += hdr.build()

        if msgbuf:
            self.service.send(msgbuf, addr)

    @utils.log_exceptions()
    async def _notify_all(self, events: typing.Iterable[int], label: str):
        await asyncio.gather(
            *[
                self._notify_single(ep, events=events, label=label)
                for ep in self.subscribed_endpoints
            ]
        )

    def notify_once(self, events: typing.Iterable[int]):
        """
        Send a notification for all given event ids to all subscribers using the
        current event values set in :attr:`values`.
        """
        if not self.has_clients.is_set():
            return
        asyncio.create_task(self._notify_all(events=events, label="event"))

    @utils.log_exceptions()
    async def cyclic_notify(self, interval: float) -> None:
        """
        Schedule notifications for all events to all subscribers with a given interval.
        This coroutine is scheduled as a task by :meth:`__init__` if given a
        non-zero interval.

        :param interval: how much time to wait before sending the next notification
        """
        while True:
            await self.has_clients.wait()

            # client subscription already sent first notification.
            # wait for one interval *before* sending next
            await asyncio.sleep(interval)

            await self._notify_all(events=self.values.keys(), label="cyclic")

    def subscribe(self, endpoint: header.EndpointOption[typing.Any]) -> None:
        """
        Called by :class:`SimpleService` when a new subscription for this eventgroup
        was received.

        Triggers a notification of the current value to be sent to the subscriber.
        """
        self.subscribed_endpoints.add(endpoint)
        self.has_clients.set()
        # send initial eventgroup notification
        asyncio.create_task(
            self._notify_single(endpoint, events=self.values.keys(), label="initial")
        )

    def unsubscribe(self, endpoint: header.EndpointOption[typing.Any]) -> None:
        """
        Called by :class:`SimpleService` when a subscription for this eventgroup
        runs out.
        """
        self.subscribed_endpoints.remove(endpoint)
        if not self.subscribed_endpoints:
            self.has_clients.clear()
