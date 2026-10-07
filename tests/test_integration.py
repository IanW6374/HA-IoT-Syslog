import asyncio
import csv
import io
import json
import ssl
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from aiohttp import ClientSession

from iot_syslog.config import load_settings
from iot_syslog.ingest import EventIngestor
from iot_syslog.receiver import SyslogListeners
from iot_syslog.storage import EventStore
from iot_syslog.tls import prepare_tls
from iot_syslog.web import WebInterface
from test_storage import event


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
                for path, page in (("/", "overview"), ("/events", "events"), ("/settings", "settings")):
                    async with session.get(f"http://127.0.0.1:{web_port}{path}") as response:
                        self.assertEqual(response.status, 200)
                        html = await response.text()
                        self.assertIn(f'<body data-page="{page}">', html)
        finally:
            await web.close()

    async def test_filtered_downloads_include_every_matching_event(self):
        now = "2026-08-24T12:00:00.000Z"
        self.store.insert_many(event(now, app_name="IoTMD-Audit", message=f"API failed {index} é", severity=3) for index in range(620))
        self.store.insert_many([event(now), event(now, hostname="other", app_name="IoTMD-Audit", message="API failed excluded", severity=3)])
        interface = WebInterface(self.store, self.ingestor, self.material, 30, ("localhost",), Path(__file__).parents[1] / "iot_syslog/rootfs/app/static")
        port = await interface.start(0)
        filters = {"q": "API failed", "hostname": "controller", "app": "IoTMD-Audit", "source": "audit", "severity": "3", "transport": "tls", "start": now, "end": now, "limit": "1", "offset": "100"}
        try:
            async with ClientSession() as session:
                async with session.get(f"http://127.0.0.1:{port}/api/export.log", params=filters) as response:
                    self.assertEqual(response.status, 200)
                    self.assertEqual(response.content_type, "text/plain")
                    self.assertIn('attachment; filename="iot-syslog-filtered.log"', response.headers["Content-Disposition"])
                    self.assertEqual(response.headers["Cache-Control"], "no-store")
                    lines = (await response.text()).splitlines()
                self.assertEqual(len(lines), 620)
                self.assertEqual(lines[0], "API failed 619 é")
                self.assertEqual(lines[-1], "API failed 0 é")
                async with session.get(f"http://127.0.0.1:{port}/api/export.csv", params=filters) as response:
                    self.assertEqual(response.status, 200)
                    self.assertEqual(response.content_type, "text/csv")
                    exported = list(csv.DictReader(io.StringIO(await response.text())))
                self.assertEqual(len(exported), 620)
                self.assertEqual(exported[0]["message"], lines[0])
                self.assertEqual(exported[-1]["message"], lines[-1])
                for path in ("export.log", "export.csv"):
                    async with session.get(f"http://127.0.0.1:{port}/api/{path}", params={"severity": "9"}) as response:
                        self.assertEqual(response.status, 400)
                        self.assertNotIn("Content-Disposition", response.headers)
                    async with session.get(f"http://127.0.0.1:{port}/api/{path}", params={"q": "absent"}) as response:
                        self.assertEqual(response.status, 200)
                        text = await response.text()
                        self.assertEqual(len(text.splitlines()), 0 if path.endswith("log") else 1)
        finally:
            await interface.close()

    async def test_csv_formula_protection_does_not_change_plain_syslog(self):
        text = '=HYPERLINK("https://example.invalid")'
        self.store.insert_many([event("2026-08-24T12:00:00.000Z", hostname="@sender", message=text)])
        interface = WebInterface(self.store, self.ingestor, None, 30, (), Path(__file__).parents[1] / "iot_syslog/rootfs/app/static")
        port = await interface.start(0)
        try:
            async with ClientSession() as session:
                async with session.get(f"http://127.0.0.1:{port}/api/export.csv") as response:
                    exported = list(csv.DictReader(io.StringIO(await response.text())))
                self.assertEqual(exported[0]["message"], "'" + text)
                self.assertEqual(exported[0]["hostname"], "'@sender")
                async with session.get(f"http://127.0.0.1:{port}/api/export.log") as response:
                    self.assertEqual(await response.text(), text + "\n")
        finally:
            await interface.close()

    async def test_disconnected_download_closes_snapshot_iterator(self):
        closed = []
        def rows():
            try:
                for index in range(620):
                    yield {"raw": f"log {index}", "message": f"log {index}"}
            finally:
                closed.append(True)
        interface = WebInterface(self.store, self.ingestor, None, 30, (), self.root)
        response = mock.Mock()
        response.prepare = mock.AsyncMock()
        response.write = mock.AsyncMock(side_effect=ConnectionResetError())
        with mock.patch.object(self.store, 'export_events', return_value=rows()), mock.patch('iot_syslog.web.web.StreamResponse', return_value=response):
            with self.assertRaises(ConnectionResetError):
                await interface.export_log(SimpleNamespace(query={}))
        self.assertEqual(closed, [True])


if __name__ == "__main__":
    unittest.main()
