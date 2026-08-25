import json
import shutil
import ssl
import tempfile
import unittest
from pathlib import Path

from cryptography import x509
from cryptography.x509 import DNSName, IPAddress
from cryptography.x509.oid import NameOID

from iot_syslog.config import load_settings
from iot_syslog.tls import prepare_tls


class TLSTests(unittest.TestCase):
    def test_generated_material_is_persistent_and_contains_all_sans(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            options = root / "options.json"
            options.write_text(
                json.dumps({"tls_server_names": "syslog.home.arpa,192.168.1.20"}),
                encoding="utf-8",
            )
            settings = load_settings(options, root / "data", root / "ssl")
            first = prepare_tls(settings)
            first_ca = first.ca_certificate.read_bytes()
            second = prepare_tls(settings)
            self.assertEqual(second.ca_certificate.read_bytes(), first_ca)
            self.assertIsInstance(second.context, ssl.SSLContext)
            ca = x509.load_pem_x509_certificate(first_ca)
            self.assertEqual(
                ca.subject.get_attributes_for_oid(NameOID.COMMON_NAME)[0].value,
                "IoT Syslog Local CA",
            )
            cert = x509.load_pem_x509_certificate((root / "data/tls/server.crt").read_bytes())
            sans = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
            self.assertEqual(sans.get_values_for_type(DNSName), ["syslog.home.arpa"])
            self.assertEqual([str(value) for value in sans.get_values_for_type(IPAddress)], ["192.168.1.20"])
            self.assertEqual((root / "data/tls/ca.key").stat().st_mode & 0o777, 0o600)

    def test_custom_mode_loads_existing_home_assistant_ssl_identity(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            options = root / "options.json"
            options.write_text("{}", encoding="utf-8")
            generated = load_settings(options, root / "generated", root / "ssl")
            material = prepare_tls(generated)
            ssl_dir = root / "ssl"
            ssl_dir.mkdir()
            shutil.copy(root / "generated/tls/server.crt", ssl_dir / "fullchain.pem")
            shutil.copy(root / "generated/tls/server.key", ssl_dir / "privkey.pem")
            shutil.copy(material.ca_certificate, ssl_dir / "iot-ca-root.pem")
            options.write_text(json.dumps({"tls_mode": "custom"}), encoding="utf-8")
            custom = load_settings(options, root / "custom", ssl_dir)
            loaded = prepare_tls(custom)
            self.assertFalse(loaded.generated)
            self.assertEqual(loaded.ca_certificate, ssl_dir / "iot-ca-root.pem")
            self.assertIsInstance(loaded.context, ssl.SSLContext)


if __name__ == "__main__":
    unittest.main()
