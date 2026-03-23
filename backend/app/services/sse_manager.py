from __future__ import annotations

import asyncio
import threading
from dataclasses import dataclass
from typing import Any


SSE_DISCONNECT_SENTINEL = object()


@dataclass
class LiveConnection:
    queue: asyncio.Queue[object]
    loop: asyncio.AbstractEventLoop


class ConnectionManager:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._active_connections: dict[str, list[LiveConnection]] = {}

    async def connect(self, user_id: str) -> asyncio.Queue[object]:
        queue: asyncio.Queue[object] = asyncio.Queue()
        loop = asyncio.get_running_loop()
        with self._lock:
            self._active_connections.setdefault(user_id, []).append(LiveConnection(queue=queue, loop=loop))
        return queue

    def disconnect(self, user_id: str, queue: asyncio.Queue[object] | None = None) -> None:
        with self._lock:
            current_connections = self._active_connections.get(user_id)
            if not current_connections:
                return
            if queue is None:
                del self._active_connections[user_id]
                return

            remaining = [connection for connection in current_connections if connection.queue is not queue]
            if len(remaining) == len(current_connections):
                return
            if remaining:
                self._active_connections[user_id] = remaining
            else:
                del self._active_connections[user_id]

    def push_to_user(self, user_id: str, message_data: dict[str, Any]) -> bool:
        with self._lock:
            connections = list(self._active_connections.get(user_id) or [])
        if not connections:
            return False

        live_connections: list[LiveConnection] = []
        stale_queues: set[asyncio.Queue[object]] = set()
        for connection in connections:
            if connection.loop.is_closed():
                stale_queues.add(connection.queue)
                continue
            live_connections.append(connection)

        if stale_queues:
            with self._lock:
                current_connections = self._active_connections.get(user_id) or []
                remaining = [connection for connection in current_connections if connection.queue not in stale_queues]
                if remaining:
                    self._active_connections[user_id] = remaining
                else:
                    self._active_connections.pop(user_id, None)

        for connection in live_connections:
            connection.loop.call_soon_threadsafe(connection.queue.put_nowait, message_data)
        return bool(live_connections)

    def reset(self) -> None:
        with self._lock:
            connections = [connection for group in self._active_connections.values() for connection in group]
            self._active_connections = {}
        for connection in connections:
            if connection.loop.is_closed():
                continue
            connection.loop.call_soon_threadsafe(connection.queue.put_nowait, SSE_DISCONNECT_SENTINEL)


manager = ConnectionManager()
