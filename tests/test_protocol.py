import unittest

from hamd_syslog.protocol import OctetCountedFramer, parse_rfc5424


class ProtocolTests(unittest.TestCase):
    def test_parses_hamd_device_event(self):
        event = parse_rfc5424(
            b"<131>1 2026-08-22T12:00:00Z controller HAMD - - - Update failed",
            "tls",
            "192.0.2.10",
        )
        self.assertEqual(event.facility, 16)
        self.assertEqual(event.severity, 3)
        self.assertEqual(event.hostname, "controller")
        self.assertEqual(event.app_name, "HAMD")
        self.assertEqual(event.message, "Update failed")
        self.assertEqual(event.transport, "tls")

    def test_parses_hamd_audit_event(self):
        event = parse_rfc5424(
            b"<134>1 - field-unit HAMD-Audit - - - portal login accepted",
            "udp",
            "192.0.2.11",
        )
        self.assertEqual(event.app_name, "HAMD-Audit")
        self.assertIsNone(event.event_time)
        self.assertEqual(event.message, "portal login accepted")

    def test_preserves_structured_data(self):
        event = parse_rfc5424(
            b'<134>1 2026-08-22T12:00:00Z host app 7 ID47 [meta@324 key="a b"] message',
            "tls",
            "peer",
        )
        self.assertEqual(event.structured_data, '[meta@324 key="a b"]')
        self.assertEqual(event.message, "message")

    def test_octet_framer_handles_fragmented_and_coalesced_frames(self):
        framer = OctetCountedFramer(1024)
        self.assertEqual(framer.feed(b"5 he"), [])
        self.assertEqual(framer.feed(b"llo5 world"), [b"hello", b"world"])

    def test_octet_framer_rejects_oversize_frame(self):
        framer = OctetCountedFramer(10)
        with self.assertRaisesRegex(ValueError, "outside"):
            framer.feed(b"11 ")


if __name__ == "__main__":
    unittest.main()
