#!/usr/bin/env python3

from __future__ import annotations
from functools import partial
from typing import *
from contextlib import asynccontextmanager
import signal

import anyio
from anyio.abc import TaskGroup, SocketStream, SocketAttribute
import logging

from utils import setup_logger, receive_line


logger = logging.getLogger('chat_server')
TIMEOUT = 30
users: Dict[str, Callable[[bytes], None]] = {}


async def write(client: SocketStream, message: str) -> None:
    if not message.endswith('\n'):
        message += '\n'

    await client.send(message.encode())


async def handle_connection(task_group: TaskGroup, client: SocketStream) -> None:
    async with client:
        remote_host, remote_port = client.extra(SocketAttribute.remote_address)

        logger.debug(f'Client connected {remote_host}:{remote_port}')

        client_write = partial(write, client)

        task_group.start_soon(client_write, 'Welcome! Please login. Example: `I''m Bob`')

        username = None

        async for message in receive_line(client):
            text = message.decode()
            if username is None:
                logger.debug(f'Received {text!r} from {remote_host}:{remote_port}')
            else:
                logger.debug(f'Received {text!r} from {username}')

            if text.startswith("I'm"):
                if username is not None:
                    logger.debug(f'Already logged in with username: {username!r}')
                    task_group.start_soon(client_write, f"Already logged in with username {tried_username}")
                else:
                    tried_username = text[3:].strip()
                    if tried_username in users.keys():
                        logger.debug(f'Duplicate login with username: {tried_username!r}')
                        task_group.start_soon(client_write, f"There's already somebody login in with username {tried_username}")
                    else:
                        username = tried_username
                        users[username] = client_write
                        logger.debug(f'User logged in as: {username!r}')
                        task_group.start_soon(client_write, 'Hello ' + username)
            elif text.startswith("@"):
                tag, text = text.split(' ', 1)
                target_username = tag[1:].strip()
                if target_username in users.keys():
                    if username is None:
                        logger.debug(f'Forwarding anonymous message to the user: {target_username!r}')
                        task_group.start_soon(users[target_username], f'<{remote_host}:{remote_port}>: {text}')
                    else:
                        logger.debug(f'Forwarding message from {username} to the user: {target_username!r}')
                        task_group.start_soon(users[target_username], f'<{username}>: {text}')
                else:
                    logger.debug(f'Failed to message the user: {target_username!r}')
                    task_group.start_soon(client_write, f"Couldn't find the username {target_username}")
            elif text == 'quit':
                with anyio.move_on_after(TIMEOUT):
                    logger.debug(f'Closing connection to {remote_host}:{remote_port}...')
                    await client_write(text)
                break
            else:
                logger.debug(f'Echoing {text!r}')
                task_group.start_soon(client_write, text)

        if username is not None:
            logger.debug(f'User logged out. username: {username!r}')
            users.pop(username)

        logger.debug(f'Connection to {remote_host}:{remote_port} closed')


@asynccontextmanager
async def start_server(server_address: str, server_port: int) -> None:
    async with anyio.create_task_group() as task_group:
        server = await anyio.create_tcp_listener(local_host=server_address, local_port=server_port)

        logger.debug('Starting server...')
        task_group.start_soon(server.serve, partial(handle_connection, task_group), task_group)

        yield

        logger.debug('Server stopped')
        task_group.cancel_scope.cancel()


async def main() -> None:
    setup_logger()

    server_address='127.0.0.1'
    server_port=8888

    async with start_server(server_address, server_port):
        async with anyio.open_signal_receiver(signal.SIGINT, signal.SIGTERM) as signals:
            async for s in signals:
                print(f'Received signal {s}')
                break


if __name__ == "__main__":
    anyio.run(main)
