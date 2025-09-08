from __future__ import annotations

import typing

from someip import config
from someip import header
from someip import sd


class SimpleClient(sd.ClientServiceListener):
    service_id: typing.ClassVar[int] = 0xAAAA
    version_major: typing.ClassVar[int] = 1
    version_minor: typing.ClassVar[int] = 1
    client_id: typing.ClassVar[int] = 1

    def __init__(
        self,
        instance_id: int,
        discovery: sd.ServiceDiscover,
        subscriber: ServiceSubscriber,
        reliable: bool = False,
        **kwargs,
    ):
        super().__init__(**kwargs)

        self.prot: typeing.Union[
            sd.SOMEIPDatagramProtocol, SOMEIPTCPClientProtocol, None
        ] = None
        self.transport = None
        self.is_found = False
        self.found_at = None
        self.log = logging.getLogger("client")

    async def create_connection_to_server(self, remote_addr, reliable: bool = False):
        if reliable:
            trans, prot = await sd.PassUpSOMEIPTCPClient.create_unicast_endpoint(
                remote_addr=remote_addr, callback=self.message_received, **kwargs
            )
            self.prot = prot
            self.transport = trans
        else:
            trans, prot = await sd.PassUpSOMEIPDatagramProtocol.create_unicast_endpoint(
                remote_addr=remote_addr, callback=self.message_received, **kwargs
            )
            self.prot = prot
            self.transport = trans

    def start_find(self):
        self.discovery.watch_service(config.Service(self.service_id), self)

    def service_offered(self, service: config.Service, source):
        self.is_found = True
        self.found_at = service.options_1[0]
        asyncio.create_task(self.create_connection_to_server(self.found_at, False))

    def message_received(
        self,
        someip_message: header.SOMEIPHeader,
        addr: header._T_SOCKNAME,
        multicast: bool,
    ) -> None:
        self.log.info(f"callback!!!!!!!! {someip_message}")
        pass

    def send_request(self, method: int, payload: bytes) -> None:
        _, session_id = self.prot.session_storage.assign_outgoing(self.found_at)
        self.prot.send(
            header.SOMEIPHeader(
                service_id=self.service_id,
                method_id=method,
                client_id=client_id,
                session_id=session_id,
                interface_version=version_major,
                message_type=header.SOMEIPMessageType.REQUEST,
                ayload=payload,
            ).build()
        )
