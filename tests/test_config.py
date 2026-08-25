import json
import tempfile
import unittest
from pathlib import Path

from iot_syslog.config import load_settings


class ConfigTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.options = self.root / "options.json"

    def tearDown(self):
        self.temporary.cleanup()

    def write(self, options):
        self.options.write_text(json.dumps(options), encoding="utf-8")

    def test_secure_defaults(self):
        self.write({})
        settings = load_settings(self.options, self.root / "data", self.root / "ssl")
        self.assertTrue(settings.tls_enabled)
        self.assertFalse(settings.udp_enabled)
        self.assertEqual(settings.retention_days, 30)
        self.assertEqual(settings.tls_server_names, ("homeassistant.local",))

    def test_accepts_dns_and_ip_server_names(self):
        self.write({"tls_server_names": "syslog.home.arpa, 192.168.1.20,syslog.home.arpa"})
        settings = load_settings(self.options, self.root / "data", self.root / "ssl")
        self.assertEqual(settings.tls_server_names, ("syslog.home.arpa", "192.168.1.20"))

    def test_rejects_custom_path_traversal(self):
        self.write({"tls_certificate": "../secret.pem"})
        with self.assertRaisesRegex(ValueError, "beneath /ssl"):
            load_settings(self.options, self.root / "data", self.root / "ssl")

    def test_rejects_unbounded_retention(self):
        self.write({"retention_days": 0})
        with self.assertRaisesRegex(ValueError, "between 1 and 3650"):
            load_settings(self.options, self.root / "data", self.root / "ssl")


if __name__ == "__main__":
    unittest.main()
