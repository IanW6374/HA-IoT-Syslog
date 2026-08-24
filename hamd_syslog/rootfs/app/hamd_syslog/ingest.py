"""Bounded asynchronous database writer."""

from __future__ import annotations

import asyncio
import logging

from .protocol import SyslogEvent
from .storage import EventStore


LOGGER = logging.getLogger(__name__)


class EventIngestor:
    def __init__(self, store: EventStore, queue_size: int = 10000):
        self.store = store
        self.queue: asyncio.Queue[SyslogEvent] = asyncio.Queue(maxsize=queue_size)
        self.accepted = 0
        self.dropped = 0
        self.persisted = 0
        self._stopping = False

    def submit(self, event: SyslogEvent) -> bool:
        try:
            self.queue.put_nowait(event)
            self.accepted += 1
            return True
        except asyncio.QueueFull:
            self.dropped += 1
            if self.dropped == 1 or self.dropped % 100 == 0:
                LOGGER.error("Ingest queue full; dropped %d syslog events", self.dropped)
            return False

    async def run(self) -> None:
        while not self._stopping or not self.queue.empty():
            batch = []
            try:
                batch.append(await asyncio.wait_for(self.queue.get(), timeout=0.5))
            except asyncio.TimeoutError:
                continue
            while len(batch) < 250:
                try:
                    batch.append(self.queue.get_nowait())
                except asyncio.QueueEmpty:
                    break
            try:
                self.persisted += self.store.insert_many(batch)
            except Exception:
                self.dropped += len(batch)
                LOGGER.exception("Could not persist a batch of %d syslog events", len(batch))
                await asyncio.sleep(1)
            finally:
                for _ in batch:
                    self.queue.task_done()

    async def stop(self) -> None:
        self._stopping = True
        await self.queue.join()
