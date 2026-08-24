"""Application option loading and validation."""

from __future__ import annotations

import ipaddress
import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    ssl_dir: Path
    udp_enabled: bool
    udp_port: int
    tls_enabled: bool
    tls_port: int
    tls_mode: str
    tls_server_names: tuple[str, ...]
    tls_certificate: str
    tls_private_key: str
    tls_ca_certificate: str
    retention_days: int
    purge_interval_hours: int
    max_message_bytes: int
    web_port: int = 8099

    @property
    def database_path(self) -> Path:
        return self.data_dir / "syslog.db"


def _bounded_int(options: dict, key: str, default: int, low: int, high: int) -> int:
    try:
        value = int(options.get(key, default))
    except (TypeError, ValueError) as error:
        raise ValueError(f"{key} must be an integer") from error
    if not low <= value <= high:
        raise ValueError(f"{key} must be between {low} and {high}")
    return value


def _safe_relative_file(value: object, key: str) -> str:
    text = str(value or "").strip()
    candidate = Path(text)
    if not text or candidate.is_absolute() or ".." in candidate.parts:
        raise ValueError(f"{key} must be a relative file beneath /ssl")
    return text


def _server_names(value: object) -> tuple[str, ...]:
    names = []
    for item in str(value or "homeassistant.local").split(","):
        name = item.strip().lower().rstrip(".")
        if not name or len(name) > 253 or any(char.isspace() for char in name):
            raise ValueError("tls_server_names contains an invalid DNS name or IP address")
        try:
            ipaddress.ip_address(name)
        except ValueError:
            labels = name.split(".")
            if any(not label or len(label) > 63 or label.startswith("-") or label.endswith("-") for label in labels):
                raise ValueError("tls_server_names contains an invalid DNS name")
            if any(not all(char.isalnum() or char == "-" for char in label) for label in labels):
                raise ValueError("tls_server_names contains an invalid DNS name")
        if name not in names:
            names.append(name)
    if not names:
        raise ValueError("tls_server_names must contain at least one name")
    return tuple(names)


def load_settings(
    options_path: Path = Path("/data/options.json"),
    data_dir: Path = Path("/data"),
    ssl_dir: Path = Path("/ssl"),
) -> Settings:
    try:
        options = json.loads(options_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        options = {}
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"cannot read {options_path}: {error}") from error
    if not isinstance(options, dict):
        raise ValueError("options.json must contain an object")

    tls_mode = str(options.get("tls_mode", "generated")).strip().lower()
    if tls_mode not in {"generated", "custom"}:
        raise ValueError("tls_mode must be generated or custom")

    return Settings(
        data_dir=data_dir,
        ssl_dir=ssl_dir,
        udp_enabled=options.get("udp_enabled", False) is True,
        udp_port=_bounded_int(options, "udp_port", 514, 1, 65535),
        tls_enabled=options.get("tls_enabled", True) is True,
        tls_port=_bounded_int(options, "tls_port", 6514, 1, 65535),
        tls_mode=tls_mode,
        tls_server_names=_server_names(options.get("tls_server_names")),
        tls_certificate=_safe_relative_file(
            options.get("tls_certificate", "fullchain.pem"), "tls_certificate"
        ),
        tls_private_key=_safe_relative_file(
            options.get("tls_private_key", "privkey.pem"), "tls_private_key"
        ),
        tls_ca_certificate=_safe_relative_file(
            options.get("tls_ca_certificate", "iot-ca-root.pem"), "tls_ca_certificate"
        ),
        retention_days=_bounded_int(options, "retention_days", 30, 1, 3650),
        purge_interval_hours=_bounded_int(options, "purge_interval_hours", 6, 1, 168),
        max_message_bytes=_bounded_int(options, "max_message_kib", 64, 1, 1024) * 1024,
    )
