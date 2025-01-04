from __future__ import annotations

import someip.config
from someip.protocol import SOMEIPDatagramProtocol
from event_group_sub import EventgroupSubscription
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


class IServiceDiscoveryProtocol(SOMEIPDatagramProtocol)

    def send_sd(
            self,
            entries: typing.Collection[someip.header.SOMEIPSDEntry],
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
