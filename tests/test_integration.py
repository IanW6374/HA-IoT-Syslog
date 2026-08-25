import asyncio
import json
import ssl
import tempfile
import unittest
from pathlib import Path

from aiohttp import ClientSession

from iot_syslog.config import load_settings
from iot_syslog.ingest import EventIngestor
from iot_syslog.receiver import SyslogListeners
from iot_syslog.storage import EventStore
from iot_syslog.tls import prepare_tls
from iot_syslog.web import WebInterface


class IntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        options = self.root / "options.json"
        options.write_text(json.dumps({"tls_server_names": "localhost"}), encoding="utf-8")
        self.settings = load_settings(options, self.root / "data", self.root / "ssl")
        self.material = prepare_tls(self.settings)
        self.store = EventStore(self.settings.database_path)
        self.ingestor = EventIngestor(self.store)
        self.ingest_task = asyncio.create_task(self.ingestor.run())
        self.listeners = SyslogListeners(self.ingestor.submit, 64 * 1024)

    async def asyncTearDown(self):
        await self.listeners.close()
        await self.ingestor.stop()
        await self.ingest_task
        self.store.close()
        self.temporary.cleanup()

    async def test_iot_md_tls_frame_is_searchable_through_ingress_api(self):
        await self.listeners.start_tls(0, self.material.context)
        port = self.listeners.tls_server.sockets[0].getsockname()[1]
        client_context = ssl.create_default_context(cafile=str(self.material.ca_certificate))
        _, writer = await asyncio.open_connection(
            "127.0.0.1", port, ssl=client_context, server_hostname="localhost"
        )
        payload = b"<134>1 2026-08-24T12:00:00Z field-7 IoTMD-Audit - - - API connection accepted"
        writer.write(str(len(payload)).encode() + b" " + payload)
        await writer.drain()
        writer.close()
        await writer.wait_closed()
        for _ in range(20):
            if self.ingestor.accepted:
                break
            await asyncio.sleep(0.05)
        await self.ingestor.queue.join()

        web = WebInterface(
            self.store,
            self.ingestor,
            self.material,
            30,
            ("localhost",),
            Path(__file__).parents[1] / "iot_syslog/rootfs/app/static",
        )
        web_port = await web.start(0)
        try:
            async with ClientSession() as session:
                async with session.get(
                    f"http://127.0.0.1:{web_port}/api/events",
                    params={"source": "audit", "q": "API connection"},
                ) as response:
                    self.assertEqual(response.status, 200)
                    body = await response.json()
                self.assertEqual(body["total"], 1)
                self.assertEqual(body["events"][0]["hostname"], "field-7")
                self.assertEqual(body["events"][0]["transport"], "tls")

                async with session.get(f"http://127.0.0.1:{web_port}/api/ca.der") as response:
                    self.assertEqual(response.status, 200)
                    self.assertEqual(response.content_type, "application/pkix-cert")
                    self.assertGreater(len(await response.read()), 500)
        finally:
            await web.close()


if __name__ == "__main__":
    unittest.main()
