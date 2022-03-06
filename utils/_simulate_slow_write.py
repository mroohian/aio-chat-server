from __future__ import annotations
from typing import *

import anyio
from anyio.abc import SocketStream


async def simulate_slow_write(client: SocketStream, message: bytes) -> None:
    if not message.endswith(b'\n'):
        message += b'\n'

    for ch in message:
        await anyio.sleep(0.1)
        await client.send(bytes([ch]))
