from __future__ import annotations

import dataclasses
import typing

import someip.header

@dataclasses.dataclass(frozen=True)
class EventgroupSubscription:
    service_id: int
    instance_id: int
    major_version: int
    id: int
    counter: int
    ttl: int = dataclasses.field(compare=False)
    endpoints: typing.FrozenSet[
        someip.header.EndpointOption[typing.Any]
    ] = dataclasses.field(default_factory=frozenset)
    options: typing.Tuple[someip.header.SOMEIPSDOption, ...] = dataclasses.field(
        default_factory=tuple, compare=False
    )

    @classmethod
    def from_subscribe_entry(cls, entry: someip.header.SOMEIPSDEntry):
        endpoints = []
        options = []
        for option in entry.options:
            if isinstance(option, someip.header.EndpointOption):
                endpoints.append(option)
            else:
                options.append(option)

        return cls(
            service_id=entry.service_id,
            instance_id=entry.instance_id,
            major_version=entry.major_version,
            id=entry.eventgroup_id,
            counter=entry.eventgroup_counter,
            ttl=entry.ttl,
            endpoints=frozenset(endpoints),
            options=tuple(options),
        )

    def to_ack_entry(self):
        return someip.header.SOMEIPSDEntry(
            sd_type=someip.header.SOMEIPSDEntryType.SubscribeAck,
            service_id=self.service_id,
            instance_id=self.instance_id,
            major_version=self.major_version,
            ttl=self.ttl,
            minver_or_counter=(self.counter << 16) | self.id,
        )

    def to_nack_entry(self):
        return dataclasses.replace(self, ttl=0).to_ack_entry()


class NakSubscription(Exception):  # noqa: N818
    pass

