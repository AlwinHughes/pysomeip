from __future__ import annotations

import asyncio
import typing

KT = typing.TypeVar("KT")
VT = typing.TypeVar("VT")

class SendCollector(typing.Generic[KT]):
    def __init__(
        self,
        timeout: float,
        callback: typing.Callable[[typing.List[VT]], None],
        *args,
        **kwargs,
    ):
        self.data: typing.List[VT] = []
        self.args = args
        self.kwargs = kwargs
        self.callback = callback

        self.done = False
        self._handle = asyncio.get_event_loop().call_later(
            timeout, self._handle_timeout
        )

    def _handle_timeout(self) -> None:
        self.done = True
        self.callback(self.data, *self.args, **self.kwargs)

    def append(self, datum) -> None:
        if self.done:
            raise RuntimeError("tried to append data on an expired SendCollector")

        self.data.append(datum)

    def cancel(self) -> None:
        self._handle.cancel()
