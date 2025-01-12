from __future__ import annotations

import asyncio
import dataclasses
import collections
import functools
import warnings
import typing

import someip.header as header
import someip.config as config
import someip.sd as sd
import someip.utils as utils

from .simple_event_group import SimpleEventgroup

_T_METHOD_HANDLER = typing.Callable[
    [header.SOMEIPHeader, header._T_SOCKNAME], typing.Optional[bytes]
]


class MalformedMessageError(Exception):
    pass


class SimpleService(sd.SOMEIPDatagramProtocol, sd.ServerServiceListener):
    service_id: typing.ClassVar[int]
    version_major: typing.ClassVar[int]
    version_minor: typing.ClassVar[int]

    def __init__(self, instance_id: int):
        """
        override, call super().__init__() followed by :meth:`register_method`
        and :meth:`register_cyclic_eventgroup`
        """
        super().__init__()
        self.clients: typing.DefaultDict[
            int, typing.Set[sd.EventgroupSubscription]
        ] = collections.defaultdict(set)
        self.eventgroups: typing.Dict[int, SimpleEventgroup] = {}
        self.methods: typing.Dict[int, _T_METHOD_HANDLER] = {}
        self.instance_id: int = instance_id
        self.log = self.log.getChild(f"service-{self.service_id:04x}-{instance_id:04x}")

    def register_method(self, id: int, handler: _T_METHOD_HANDLER) -> None:
        """
        register a SOME/IP method with the given id on this service. Incoming
        requests matching the given id will be dispatched to the handler.

        Callbacks can raise :exc:`MalformedMessageError` to generate an error
        response with return code
        :data:`someip.header.SOMEIPReturnCode.E_MALFORMED_MESSAGE`

        :param id: the method ID
        :param handler: the callback to handle the request
        """
        if id in self.methods:
            raise KeyError(f"method with id {id:#x} already registered on {self}")
        self.methods[id] = handler

    def register_eventgroup(self, eventgroup: SimpleEventgroup) -> None:
        """
        register an eventgroup on this service. Incoming subscriptions will be
        handled and passed to the given eventgroup.

        :param eventgroup:
        """
        if eventgroup.id in self.eventgroups:
            raise KeyError(
                f"eventgroup with id {eventgroup.id:#x} already registered on {self}"
            )
        self.eventgroups[eventgroup.id] = eventgroup

    @functools.cached_property
    def _endpoint(self) -> header.SOMEIPSDOption:
        sockname = self.transport.get_extra_info("sockname")
        return config.Eventgroup._sockaddr_to_endpoint(sockname, header.L4Protocols.UDP)

    def as_config(self):
        return config.Service(
            self.service_id,
            self.instance_id,
            self.version_major,
            self.version_minor,
            options_1=(self._endpoint,),
            eventgroups=frozenset(self.eventgroups.keys()),
        )

    @classmethod
    async def start_datagram_endpoint(
        cls,
        instance_id: int,
        announcer: sd.ServiceAnnouncer,
        local_addr: sd._T_OPT_SOCKADDR = None,
    ):  # pragma: nocover
        """
        create a unicast datagram endpoint for this service and register it with
        the service discovery announcer.

        :param instance_id: the service instance ID for this service
        :param announcer: the SD protocol instance that will announce this service
        :param local_addr: a local address to bind to (default: any)
        """
        _, prot = await cls.create_unicast_endpoint(instance_id, local_addr=local_addr)

        prot.start_announce(announcer)

        return prot

    def start_announce(self, announcer: sd.ServiceAnnouncer):
        self.service_instance = sd.ServiceInstance(
            self.as_config(), self, announcer, announcer.timings
        )
        announcer.announce_service(self.service_instance)

    def stop_announce(self, announcer: sd.ServiceAnnouncer):
        announcer.stop_announce_service(self.service_instance)

    def stop(self):  # pragma: nocover
        self.transport.close()

    def message_received(
        self,
        someip_message: header.SOMEIPHeader,
        addr: header._T_SOCKNAME,
        multicast: bool,
    ) -> None:
        if multicast:
            warnings.warn(
                "Service packet received over multicast - this does not make sense."
                " You probably created the wrong type of socket for this service.",
                stacklevel=2,
            )
            return
        if someip_message.service_id != self.service_id:
            self.log.warning("received message for unknown service: %r", someip_message)
            self.send_error_response(
                someip_message, addr, header.SOMEIPReturnCode.E_UNKNOWN_SERVICE
            )
            return
        if someip_message.interface_version != self.version_major:
            self.log.warning(
                "received message for incompatible service version: %r", someip_message
            )
            self.send_error_response(
                someip_message, addr, header.SOMEIPReturnCode.E_WRONG_INTERFACE_VERSION
            )
            return

        method = self.methods.get(someip_message.method_id)
        if method is None:
            self.log.warning(
                "received message for unknown method id: %r", someip_message
            )
            self.send_error_response(
                someip_message, addr, header.SOMEIPReturnCode.E_UNKNOWN_METHOD
            )
            return

        if someip_message.message_type not in (
            header.SOMEIPMessageType.REQUEST,
            header.SOMEIPMessageType.REQUEST_NO_RETURN,
        ):
            self.log.warning(
                "received message with bad message type: %r", someip_message
            )
            self.send_error_response(
                someip_message, addr, header.SOMEIPReturnCode.E_WRONG_MESSAGE_TYPE
            )
            return

        if someip_message.return_code != header.SOMEIPReturnCode.E_OK:
            self.log.warning(
                "received message with bad return code: %r", someip_message
            )
            self.send_error_response(
                someip_message, addr, header.SOMEIPReturnCode.E_WRONG_MESSAGE_TYPE
            )
            return

        self.log.info(
            "%r calling %s: %r",
            addr,
            method,
            someip_message.payload,
        )
        try:
            response = method(someip_message, addr)
        except MalformedMessageError:
            self.send_error_response(
                someip_message, addr, header.SOMEIPReturnCode.E_MALFORMED_MESSAGE
            )
            return

        if (
            response is not None
            and someip_message.message_type == header.SOMEIPMessageType.REQUEST
        ):
            self.send_positive_response(someip_message, addr, payload=response)

    def send_error_response(
        self,
        msg: header.SOMEIPHeader,
        addr: header._T_SOCKNAME,
        return_code: header.SOMEIPReturnCode,
    ) -> None:
        resp = dataclasses.replace(
            msg,
            message_type=header.SOMEIPMessageType.ERROR,
            return_code=return_code,
            payload=b"",
        )
        self.send(resp.build(), addr)

    def send_positive_response(
        self,
        msg: header.SOMEIPHeader,
        addr: header._T_SOCKNAME,
        payload: bytes = b"",
    ) -> None:
        resp = dataclasses.replace(
            msg, message_type=header.SOMEIPMessageType.RESPONSE, payload=payload
        )
        self.send(resp.build(), addr)

    def client_subscribed(
        self,
        subscription: sd.EventgroupSubscription,
        source: header._T_SOCKNAME,
    ) -> None:
        try:
            evgrp = self.eventgroups.get(subscription.id)
            assert (
                evgrp
            ), f"{self}.client_subscribed called with unknown subscription id"
            if len(subscription.endpoints) != 1:
                self.log.error(
                    "client tried to subscribe with multiple endpoints from %r:\n%s",
                    source,
                    subscription,
                )
                raise sd.NakSubscription
            self.log.info("client_subscribed from %r: %s", source, subscription)

            ep = next(iter(subscription.endpoints))
            evgrp.subscribe(ep)
        except Exception as exc:
            self.log.exception(
                "client_subscribed from %r: %s failed", source, subscription
            )
            raise sd.NakSubscription from exc

    def client_unsubscribed(
        self, subscription: sd.EventgroupSubscription, source: header._T_SOCKNAME
    ) -> None:
        try:
            evgrp = self.eventgroups.get(subscription.id)
            assert (
                evgrp
            ), f"{self}.client_unsubscribed called with unknown subscription id"
            ep = next(iter(subscription.endpoints))
            evgrp.unsubscribe(ep)
            self.log.info("client_unsubscribed from %r: %s", source, subscription)
        except KeyError:
            self.log.warning(
                "client_unsubscribed unknown from %r: %s", source, subscription
            )
