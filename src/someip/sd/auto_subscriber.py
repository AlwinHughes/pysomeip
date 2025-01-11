from __future__ import annotations

import dataclasses
import someip.header
import someip.config

from .interfaces import IClientServiceListener
from .service_subscriber import ServiceSubscriber


"""
todo: documentation

Automatically subscribes to all of a service's event groups?

"""

@dataclasses.dataclass(frozen=True)
class AutoSubscribeServiceListener(IClientServiceListener):
    subscriber: ServiceSubscriber
    eventgroup: someip.config.Eventgroup

    def service_offered(
        self, service: someip.config.Service, source: _T_SOCKADDR
    ) -> None:
        eventgroup = self.eventgroup.for_service(service)
        if not eventgroup:  # pragma: nocover
            return
        # TODO support TCP event groups: application (or lib?) needs to open connection
        # before subscribe
        self.subscriber.subscribe_eventgroup(eventgroup, source)

    def service_stopped(
        self, service: someip.config.Service, source: _T_SOCKADDR
    ) -> None:
        eventgroup = self.eventgroup.for_service(service)
        if not eventgroup:  # pragma: nocover
            return
        # TODO support TCP event groups: application (or lib?) needs to close connection
        self.subscriber.stop_subscribe_eventgroup(eventgroup, source)
