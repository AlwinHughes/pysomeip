from __future__ import annotations

import asyncio

from .someip_header import SOMEIPHeader

class SOMEIPReader:
    """
    Wrapper class around :class:`asyncio.StreamReader` that returns parsed
    :class:`SOMEIPHeader` from :meth:`read`
    """

    def __init__(self, reader: asyncio.StreamReader):
        self.reader = reader

    async def read(self) -> typing.Optional[SOMEIPHeader]:
        return await SOMEIPHeader.read(self.reader)

    def at_eof(self):
        return self.reader.at_eof()
