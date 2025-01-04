from __future__ import annotations

import dataclasses
import typing

@dataclasses.dataclass()
class Timings:
    INITIAL_DELAY_MIN: float = 0.0  # in seconds
    INITIAL_DELAY_MAX: float = 3  # in seconds
    REQUEST_RESPONSE_DELAY_MIN: float = 0.01  # in seconds
    REQUEST_RESPONSE_DELAY_MAX: float = 0.05  # in seconds
    REPETITIONS_MAX: int = 3
    REPETITIONS_BASE_DELAY: float = 0.01  # in seconds
    CYCLIC_OFFER_DELAY: float = 1  # in seconds
    FIND_TTL: int = 3  # in seconds
    ANNOUNCE_TTL: int = 3  # in seconds
    SUBSCRIBE_TTL: int = 5  # in seconds
    SUBSCRIBE_REFRESH_INTERVAL: typing.Optional[float] = 3  # in seconds
    SEND_COLLECTION_TIMEOUT: float = 0.005  # in seconds


TTL_FOREVER = 0xFFFFFF
