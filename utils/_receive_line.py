from __future__ import annotations
from typing import *

import anyio
from anyio.abc import SocketStream


async def receive_line(client: SocketStream) -> AsyncIterator[bytes]:
    data = b''
    try:
        while data := data + await client.receive(100):
            if b'\n' in data:
                message, data = data.split(b'\n', 1)
                yield message
    except anyio.EndOfStream:
        pass
    if data:
        yield data
