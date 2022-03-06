#!/usr/bin/env python3

from __future__ import annotations
import asyncio
from typing import *
from typing import TextIO
from contextlib import asynccontextmanager
import signal

import anyio
from anyio.abc import TaskGroup, SocketStream

import logging
import sys

from utils import setup_logger, receive_line, simulate_slow_write


logger = logging.getLogger('chat_client')


async def handle_reads(client: SocketStream, running_lock: anyio.Event) -> None:
    async for message in receive_line(client):
        text = message.decode()
        logger.debug(f'Received {text!r}')
        if text == 'quit':
            running_lock.set()
            break


async def forward_console(client: SocketStream) -> None:
    async for message in anyio.wrap_file(sys.stdin):
        if message.strip() == '':
            continue
        await simulate_slow_write(client, message.encode())


async def connect_server(server_address: str, server_port: int, task_group: TaskGroup) -> None:
    running_lock = anyio.Event()
    try:
        async with await anyio.connect_tcp(server_address, server_port) as client:
            task_group.start_soon(handle_reads, client, running_lock)
            task_group.start_soon(forward_console, client)
            await running_lock.wait()
            logger.debug('Closing the connection')
    except OSError as os_error:
        logger.error('Failed to connect: ' + str(os_error))
        pass

    task_group.cancel_scope.cancel()


@asynccontextmanager
async def start_client(server_address: str, server_port: int) -> None:
    async with anyio.create_task_group() as task_group:
        logger.debug('Connecting to server')
        task_group.start_soon(connect_server, server_address, server_port, task_group)

        yield

        logger.debug('Client stopped')
        task_group.cancel_scope.cancel()


async def main() -> None:
    setup_logger()

    server_address='127.0.0.1'
    server_port=8888

    async with start_client(server_address, server_port):
        async with anyio.open_signal_receiver(signal.SIGINT, signal.SIGTERM) as signals:
            async for s in signals:
                print(f'Received signal {s}')
                break


if __name__ == "__main__":
    anyio.run(main)
