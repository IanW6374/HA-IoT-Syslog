"""RFC 5424 parsing and RFC 6587 octet-counted framing."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


SEVERITY_NAMES = {
    0: "emergency",
    1: "alert",
    2: "critical",
    3: "error",
    4: "warning",
    5: "notice",
    6: "info",
    7: "debug",
}

FACILITY_NAMES = {
    0: "kernel", 1: "user", 2: "mail", 3: "daemon", 4: "auth",
    5: "syslog", 6: "printer", 7: "news", 8: "uucp", 9: "clock",
    10: "authpriv", 11: "ftp", 16: "local0", 17: "local1", 18: "local2",
    19: "local3", 20: "local4", 21: "local5", 22: "local6", 23: "local7",
}


@dataclass(frozen=True)
class SyslogEvent:
    received_at: str
    event_time: str | None
    facility: int
    severity: int
    hostname: str
    app_name: str
    procid: str
    msgid: str
    structured_data: str
    message: str
    raw: str
    transport: str
    peer: str


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _nil(value: str) -> str:
    return "" if value == "-" else value


def _timestamp(value: str) -> str | None:
    if value == "-":
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    except ValueError:
        return None


def _split_structured_data(rest: str) -> tuple[str, str]:
    if rest == "-":
        return "-", ""
    if rest.startswith("- "):
        return "-", rest[2:]
    if not rest.startswith("["):
        return "-", rest

    quoted = False
    escaped = False
    depth = 0
    index = 0
    while index < len(rest):
        char = rest[index]
        if escaped:
            escaped = False
        elif char == "\\" and quoted:
            escaped = True
        elif char == '"':
            quoted = not quoted
        elif not quoted and char == "[":
            depth += 1
        elif not quoted and char == "]":
            depth -= 1
            if depth == 0:
                next_index = index + 1
                if next_index < len(rest) and rest[next_index] == "[":
                    index = next_index
                else:
                    structured = rest[:next_index]
                    message = rest[next_index + 1:] if rest[next_index:next_index + 1] == " " else rest[next_index:]
                    return structured, message
        index += 1
    return "-", rest


def parse_rfc5424(payload: bytes, transport: str, peer: str) -> SyslogEvent:
    raw = payload.decode("utf-8", errors="replace").strip("\x00\r\n")
    received_at = utc_now()
    priority = 13
    body = raw
    if raw.startswith("<"):
        closing = raw.find(">", 1, 6)
        if closing > 1 and raw[1:closing].isdigit():
            candidate = int(raw[1:closing])
            if 0 <= candidate <= 191:
                priority = candidate
                body = raw[closing + 1:]

    parts = body.split(" ", 6)
    if len(parts) == 7 and parts[0] == "1":
        _, timestamp, hostname, app_name, procid, msgid, rest = parts
        structured, message = _split_structured_data(rest)
        event_time = _timestamp(timestamp)
    else:
        hostname = ""
        app_name = ""
        procid = ""
        msgid = ""
        structured = "-"
        message = body
        event_time = None

    return SyslogEvent(
        received_at=received_at,
        event_time=event_time,
        facility=priority // 8,
        severity=priority % 8,
        hostname=_nil(hostname)[:255],
        app_name=_nil(app_name)[:128],
        procid=_nil(procid)[:128],
        msgid=_nil(msgid)[:128],
        structured_data=structured[:8192],
        message=message,
        raw=raw,
        transport=transport,
        peer=peer[:128],
    )


class OctetCountedFramer:
    def __init__(self, max_frame_bytes: int):
        self.max_frame_bytes = max_frame_bytes
        self.buffer = bytearray()

    def feed(self, data: bytes) -> list[bytes]:
        self.buffer.extend(data)
        frames = []
        while self.buffer:
            separator = self.buffer.find(b" ")
            if separator < 0:
                if len(self.buffer) > 12:
                    raise ValueError("invalid RFC 6587 length prefix")
                break
            prefix = bytes(self.buffer[:separator])
            if not prefix.isdigit() or len(prefix) > 10:
                raise ValueError("invalid RFC 6587 length prefix")
            length = int(prefix)
            if length < 1 or length > self.max_frame_bytes:
                raise ValueError("RFC 6587 frame length is outside the configured limit")
            frame_end = separator + 1 + length
            if len(self.buffer) < frame_end:
                break
            frames.append(bytes(self.buffer[separator + 1:frame_end]))
            del self.buffer[:frame_end]
        return frames
