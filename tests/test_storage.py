import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from hamd_syslog.protocol import SyslogEvent
from hamd_syslog.storage import EventStore


def event(received_at, app_name="HAMD", hostname="controller", message="started", severity=6):
    return SyslogEvent(
        received_at=received_at,
        event_time=received_at,
        facility=16,
        severity=severity,
        hostname=hostname,
        app_name=app_name,
        procid="",
        msgid="",
        structured_data="-",
        message=message,
        raw=message,
        transport="tls",
        peer="192.0.2.10",
    )


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.store = EventStore(Path(self.temporary.name) / "events.db")

    def tearDown(self):
        self.store.close()
        self.temporary.cleanup()

    def test_filters_device_and_audit_sources(self):
        now = "2026-08-24T12:00:00.000Z"
        self.store.insert_many(
            [event(now, message="device ready"), event(now, app_name="HAMD-Audit", message="login accepted")]
        )
        device = self.store.search({"source": "device"})
        audit = self.store.search({"source": "audit"})
        self.assertEqual([item["message"] for item in device["events"]], ["device ready"])
        self.assertEqual([item["message"] for item in audit["events"]], ["login accepted"])

    def test_combines_text_severity_and_hostname_filters(self):
        now = "2026-08-24T12:00:00.000Z"
        self.store.insert_many(
            [
                event(now, hostname="field-1", message="update failed", severity=3),
                event(now, hostname="field-2", message="update complete", severity=6),
            ]
        )
        result = self.store.search({"q": "failed", "severity": 3, "hostname": "field-1"})
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["events"][0]["severity_name"], "error")

    def test_retention_uses_received_time(self):
        now = datetime(2026, 8, 24, 12, tzinfo=timezone.utc)
        old = (now - timedelta(days=31)).isoformat(timespec="milliseconds").replace("+00:00", "Z")
        current = now.isoformat(timespec="milliseconds").replace("+00:00", "Z")
        self.store.insert_many([event(old, message="old"), event(current, message="current")])
        self.assertEqual(self.store.purge(30, now), 1)
        self.assertEqual([item["message"] for item in self.store.search({})["events"]], ["current"])


if __name__ == "__main__":
    unittest.main()
