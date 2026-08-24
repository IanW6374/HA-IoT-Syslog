"""TLS certificate management for generated and custom modes."""

from __future__ import annotations

import hashlib
import ipaddress
import os
import ssl
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

from .config import Settings


@dataclass(frozen=True)
class TLSMaterial:
    context: ssl.SSLContext
    ca_certificate: Path | None
    ca_sha256: str | None
    generated: bool


def _write_private(path: Path, content: bytes) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(content)
    os.chmod(temporary, 0o600)
    temporary.replace(path)


def _write_public(path: Path, content: bytes) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(content)
    os.chmod(temporary, 0o644)
    temporary.replace(path)


def _general_names(names: tuple[str, ...]) -> list[x509.GeneralName]:
    result = []
    for name in names:
        try:
            result.append(x509.IPAddress(ipaddress.ip_address(name)))
        except ValueError:
            result.append(x509.DNSName(name))
    return result


def _generate_ca(ca_key_path: Path, ca_cert_path: Path) -> tuple[object, x509.Certificate]:
    now = datetime.now(timezone.utc)
    key = rsa.generate_private_key(public_exponent=65537, key_size=3072)
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "HAMD Syslog Local CA")])
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=5))
        .not_valid_after(now + timedelta(days=3650))
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        .add_extension(
            x509.KeyUsage(
                digital_signature=True, key_encipherment=False, key_cert_sign=True,
                key_agreement=False, content_commitment=False, data_encipherment=False,
                encipher_only=False, decipher_only=False, crl_sign=True,
            ),
            critical=True,
        )
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()), critical=False)
        .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(key.public_key()), critical=False)
        .sign(key, hashes.SHA256())
    )
    _write_private(
        ca_key_path,
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ),
    )
    _write_public(ca_cert_path, cert.public_bytes(serialization.Encoding.PEM))
    return key, cert


def _load_or_generate_ca(ca_key_path: Path, ca_cert_path: Path) -> tuple[object, x509.Certificate]:
    if ca_key_path.exists() and ca_cert_path.exists():
        key = serialization.load_pem_private_key(ca_key_path.read_bytes(), password=None)
        cert = x509.load_pem_x509_certificate(ca_cert_path.read_bytes())
        return key, cert
    return _generate_ca(ca_key_path, ca_cert_path)


def _certificate_is_current(path: Path, names: tuple[str, ...]) -> bool:
    try:
        cert = x509.load_pem_x509_certificate(path.read_bytes())
        expiry = (
            cert.not_valid_after_utc
            if hasattr(cert, "not_valid_after_utc")
            else cert.not_valid_after.replace(tzinfo=timezone.utc)
        )
        sans = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
        actual = set(sans.get_values_for_type(x509.DNSName))
        actual.update(str(value) for value in sans.get_values_for_type(x509.IPAddress))
        return expiry > datetime.now(timezone.utc) + timedelta(days=30) and set(names) == actual
    except (OSError, ValueError, x509.ExtensionNotFound):
        return False


def _issue_server_certificate(
    key_path: Path,
    cert_path: Path,
    ca_key: object,
    ca_cert: x509.Certificate,
    names: tuple[str, ...],
) -> None:
    now = datetime.now(timezone.utc)
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    cert = (
        x509.CertificateBuilder()
        .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, names[0])]))
        .issuer_name(ca_cert.subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=5))
        .not_valid_after(now + timedelta(days=825))
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(x509.SubjectAlternativeName(_general_names(names)), critical=False)
        .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()), critical=False)
        .add_extension(
            x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()), critical=False
        )
        .add_extension(
            x509.KeyUsage(
                digital_signature=True, key_encipherment=True, key_cert_sign=False,
                key_agreement=False, content_commitment=False, data_encipherment=False,
                encipher_only=False, decipher_only=False, crl_sign=False,
            ),
            critical=True,
        )
        .sign(ca_key, hashes.SHA256())
    )
    _write_private(
        key_path,
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ),
    )
    _write_public(cert_path, cert.public_bytes(serialization.Encoding.PEM))


def prepare_tls(settings: Settings) -> TLSMaterial:
    if settings.tls_mode == "generated":
        generated_dir = settings.data_dir / "tls"
        generated_dir.mkdir(parents=True, exist_ok=True)
        ca_key_path = generated_dir / "ca.key"
        ca_cert_path = generated_dir / "ca.crt"
        server_key_path = generated_dir / "server.key"
        server_cert_path = generated_dir / "server.crt"
        ca_key, ca_cert = _load_or_generate_ca(ca_key_path, ca_cert_path)
        if not server_key_path.exists() or not _certificate_is_current(server_cert_path, settings.tls_server_names):
            _issue_server_certificate(
                server_key_path, server_cert_path, ca_key, ca_cert, settings.tls_server_names
            )
        generated = True
    else:
        server_cert_path = settings.ssl_dir / settings.tls_certificate
        server_key_path = settings.ssl_dir / settings.tls_private_key
        ca_cert_path = settings.ssl_dir / settings.tls_ca_certificate
        for path, label in ((server_cert_path, "certificate"), (server_key_path, "private key")):
            if not path.is_file():
                raise ValueError(f"custom TLS {label} does not exist: {path}")
        if not ca_cert_path.is_file():
            ca_cert_path = None
        generated = False

    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.options |= ssl.OP_NO_COMPRESSION
    context.load_cert_chain(certfile=server_cert_path, keyfile=server_key_path)
    ca_sha256 = None
    if ca_cert_path is not None:
        certificate = x509.load_pem_x509_certificate(ca_cert_path.read_bytes())
        ca_sha256 = hashlib.sha256(certificate.public_bytes(serialization.Encoding.DER)).hexdigest()
    return TLSMaterial(context, ca_cert_path, ca_sha256, generated)
