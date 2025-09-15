from __future__ import annotations

import asyncio
import logging
import typing

from someip import config
from someip import header
from someip import sd


class SimpleClient(sd.ClientServiceListener):

    service_id: typing.ClassVar[int] 
    version_major: typing.ClassVar[int] = 1
    version_minor: typing.ClassVar[int] = 1
    client_id: typing.ClassVar[int] = 1


    def __init__(
        self,
        instance_id: int,
        discovery: sd.ServiceDiscover,
        subscriber: sd.ServiceSubscriber,
        reliable: bool = False,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.discovery = discovery
        self.subscriber = subscriber
        self.prot: typing.Union[
            sd.SOMEIPDatagramProtocol, sd.SOMEIPTCPClientProtocol, None
        ] = None
        self.transport = None
        self.is_found = False
        self.found_at = None
        self.log = logging.getLogger("client")


    async def create_connection_to_server(
        self, remote_addr, reliable: bool = False, **kwargs
    ):
        if reliable:
            endpoint = (str(remote_addr.address), remote_addr.port)
            self.endpoint = endpoint
            trans, prot = await sd.PassUpSOMEIPTCPClient.create_unicast_endpoint(
                remote_addr=endpoint, callback=self.message_received, **kwargs
            )
            self.prot = prot
            self.transport = trans
        else:

            endpoint = (str(remote_addr.address), remote_addr.port)
            self.endpoint = endpoint
            trans, prot = await sd.PassUpSOMEIPDatagramProtocol.create_unicast_endpoint(
                remote_addr=endpoint, callback=self.message_received, **kwargs
            )
            self.prot = prot
            self.transport = trans
        return self


    def start_find(self):
        self.discovery.watch_service(config.Service(
            service_id=self.service_id,
            reliable=self.reliable
            ), self)


    def stop_find(self):
        self.discovery.stop_watch_service(config.Service(service_id=self.service_id, reliable=self.reliable), self)
        if self.transport is not None:
            self.transport.close()


    def service_offered(self, service: config.Service, source):
        self.found_at = service.options_1[0]
        self.log.info(f"found service {service} at {self.found_at}")
        self.is_found = True
        asyncio.create_task(self.create_connection_to_server(self.found_at, self.reliable))


    def message_received(
        self,
        someip_message: header.SOMEIPHeader,
        addr: header._T_SOCKNAME,
        multicast: bool,
    ) -> None:
        self.log.info(f"callback!!!!!!!! {someip_message}")
        pass
    
    
    def subscribe(self, eventgroup: someip.config.Eventgroup, endpoint: _T_SOCKADDR):
        self.subscriber.subscriber.subscribe_eventgroup(eventgroup, endpoint)


    def send_request(self, method: int, payload: bytes) -> int:
        _, session_id = self.prot.session_storage.assign_outgoing(self.found_at)
        self.prot.send(
            header.SOMEIPHeader(
                service_id=self.service_id,
                method_id=method,
                client_id=self.client_id,
                session_id=session_id,
                interface_version=self.version_major,
                message_type=header.SOMEIPMessageType.REQUEST,
                payload=payload,
            ).build()
        )
        return session_id
