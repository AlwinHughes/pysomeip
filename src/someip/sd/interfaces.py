from __future__ import annotations

import someip.config
from someip.protocol import SOMEIPDatagramProtocol
from .event_group_sub import EventgroupSubscription
from someip.config import _T_SOCKNAME as _T_SOCKADDR

class IClientServiceListener:
    def service_offered(
        self, service: someip.config.Service, source: _T_SOCKADDR
    ) -> None:
        pass

    def service_stopped(
        self, service: someip.config.Service, source: _T_SOCKADDR
    ) -> None:
        pass


class ClientServiceListener(IClientServiceListener):
    pass


class IServiceDiscoveryProtocol(SOMEIPDatagramProtocol):

    def send_sd(
            self, entries: typing.Collection[someip.header.SOMEIPSDEntry],
            remote: _T_OPT_SOCKADDR = None,
        ) -> None:
        pass

    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass


class IServerServiceListener:
    def client_subscribed(
        self, subscription: EventgroupSubscription, source: _T_SOCKADDR
    ) -> None:
        """
        should raise someip.sd.NakSubscription if subscription should be rejected
        """
        ...

    def client_unsubscribed(
        self, subscription: EventgroupSubscription, source: _T_SOCKADDR
    ) -> None:
        ...


class ServerServiceListener(IServerServiceListener):
    pass

class IServiceAnnouncer:

    def queue_send(
        self, entry: someip.header.SOMEIPSDEntry, remote: _T_OPT_SOCKADDR = None
    ) -> None:
        pass

    def announce_service(self, instance: ServiceInstance) -> None:
        pass


    def stop_announce_service(self, instance: ServiceInstance, send_stop=True) -> None:
        pass


    def handle_subscribe(
        self,
        entry: someip.header.SOMEIPSDEntry,
        addr: _T_SOCKADDR,
    ) -> None:
        pass

    def _send_subscribe_nack(
        self, subscription: EventgroupSubscription, addr: _T_SOCKADDR
    ) -> None:
        pass


    def handle_findservice(
        self,
        entry: someip.header.SOMEIPSDEntry,
        addr: _T_SOCKADDR,
        received_over_multicast: bool,
    ) -> None:
        pass


    def start(self, loop=None):
        pass

    
    def stop(self):
        pass


    def connection_lost(self, exc: typing.Optional[Exception]) -> None:
        pass


    def reboot_detected(self, addr: _T_SOCKADDR) -> None:
        pass
