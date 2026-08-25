#!/usr/bin/env python3
"""IoT Syslog service entrypoint."""

from __future__ import annotations

import asyncio
import logging
import signal
from pathlib import Path

from iot_syslog.config import load_settings
from iot_syslog.ingest import EventIngestor
from iot_syslog.receiver import SyslogListeners
from iot_syslog.storage import EventStore
from iot_syslog.tls import prepare_tls
from iot_syslog.web import WebInterface


LOGGER = logging.getLogger("iot-syslog")


async def purge_periodically(store: EventStore, retention_days: int, interval_hours: int) -> None:
    while True:
        removed = store.purge(retention_days)
        if removed:
            LOGGER.info("Retention cleanup removed %d expired events", removed)
        await asyncio.sleep(interval_hours * 3600)


async def run() -> None:
    settings = load_settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    store = EventStore(settings.database_path)
    ingestor = EventIngestor(store)
    ingest_task = asyncio.create_task(ingestor.run(), name="database-writer")
    listeners = SyslogListeners(ingestor.submit, settings.max_message_bytes)
    tls_material = prepare_tls(settings) if settings.tls_enabled else None
    web = WebInterface(
        store,
        ingestor,
        tls_material,
        settings.retention_days,
        settings.tls_server_names,
        Path(__file__).parent / "static",
    )
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for event_signal in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(event_signal, stop.set)

    try:
        if settings.udp_enabled:
            await listeners.start_udp(settings.udp_port)
        if settings.tls_enabled and tls_material:
            await listeners.start_tls(settings.tls_port, tls_material.context)
        if not settings.udp_enabled and not settings.tls_enabled:
            LOGGER.warning("Both syslog listeners are disabled; the search interface will remain available")
        await web.start(settings.web_port)
        LOGGER.info(
            "IoT Syslog ready; retention=%d days, web_port=%d",
            settings.retention_days,
            settings.web_port,
        )
        purge_task = asyncio.create_task(
            purge_periodically(store, settings.retention_days, settings.purge_interval_hours),
            name="retention-cleanup",
        )
        await stop.wait()
        purge_task.cancel()
        await asyncio.gather(purge_task, return_exceptions=True)
    finally:
        await listeners.close()
        await web.close()
        await ingestor.stop()
        await ingest_task
        store.close()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    try:
        asyncio.run(run())
    except (OSError, ValueError) as error:
        LOGGER.critical("Startup failed: %s", error)
        raise SystemExit(1) from error


if __name__ == "__main__":
    main()
