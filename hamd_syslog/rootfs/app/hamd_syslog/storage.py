"""SQLite persistence, filtering, and retention."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

from .protocol import FACILITY_NAMES, SEVERITY_NAMES, SyslogEvent


EVENT_COLUMNS = (
    "received_at", "event_time", "facility", "severity", "hostname", "app_name",
    "procid", "msgid", "structured_data", "message", "raw", "transport", "peer",
)


class EventStore:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA journal_mode=WAL")
        self.connection.execute("PRAGMA synchronous=NORMAL")
        self.connection.execute("PRAGMA busy_timeout=5000")
        self.connection.execute("PRAGMA auto_vacuum=INCREMENTAL")
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                received_at TEXT NOT NULL,
                event_time TEXT,
                facility INTEGER NOT NULL,
                severity INTEGER NOT NULL,
                hostname TEXT NOT NULL,
                app_name TEXT NOT NULL,
                procid TEXT NOT NULL,
                msgid TEXT NOT NULL,
                structured_data TEXT NOT NULL,
                message TEXT NOT NULL,
                raw TEXT NOT NULL,
                transport TEXT NOT NULL,
                peer TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS events_received_at_idx ON events(received_at DESC);
            CREATE INDEX IF NOT EXISTS events_hostname_idx ON events(hostname, received_at DESC);
            CREATE INDEX IF NOT EXISTS events_app_idx ON events(app_name, received_at DESC);
            CREATE INDEX IF NOT EXISTS events_severity_idx ON events(severity, received_at DESC);
            """
        )
        self.connection.commit()

    def insert_many(self, events: Iterable[SyslogEvent]) -> int:
        rows = [tuple(getattr(event, column) for column in EVENT_COLUMNS) for event in events]
        if not rows:
            return 0
        placeholders = ",".join("?" for _ in EVENT_COLUMNS)
        self.connection.executemany(
            f"INSERT INTO events ({','.join(EVENT_COLUMNS)}) VALUES ({placeholders})", rows
        )
        self.connection.commit()
        return len(rows)

    @staticmethod
    def _where(filters: dict[str, object]) -> tuple[str, list[object]]:
        clauses = []
        values: list[object] = []
        text = str(filters.get("q", "")).strip()
        if text:
            pattern = f"%{text.replace('%', r'\%').replace('_', r'\_')}%"
            clauses.append(
                "(message LIKE ? ESCAPE '\\' OR raw LIKE ? ESCAPE '\\' "
                "OR hostname LIKE ? ESCAPE '\\' OR app_name LIKE ? ESCAPE '\\')"
            )
            values.extend([pattern] * 4)
        mappings = (("hostname", "hostname"), ("app", "app_name"), ("transport", "transport"))
        for key, column in mappings:
            value = str(filters.get(key, "")).strip()
            if value:
                clauses.append(f"{column} = ?")
                values.append(value)
        source = str(filters.get("source", "")).strip().lower()
        if source == "audit":
            clauses.append("LOWER(app_name) = 'hamd-audit'")
        elif source == "device":
            clauses.append("LOWER(app_name) <> 'hamd-audit'")
        severity = filters.get("severity")
        if severity not in (None, ""):
            clauses.append("severity = ?")
            values.append(int(severity))
        start = str(filters.get("start", "")).strip()
        if start:
            clauses.append("received_at >= ?")
            values.append(start)
        end = str(filters.get("end", "")).strip()
        if end:
            clauses.append("received_at <= ?")
            values.append(end)
        return (" WHERE " + " AND ".join(clauses) if clauses else ""), values

    def search(self, filters: dict[str, object], limit: int = 100, offset: int = 0) -> dict:
        limit = max(1, min(500, int(limit)))
        offset = max(0, int(offset))
        where, values = self._where(filters)
        total = self.connection.execute(f"SELECT COUNT(*) FROM events{where}", values).fetchone()[0]
        rows = self.connection.execute(
            f"SELECT * FROM events{where} ORDER BY received_at DESC, id DESC LIMIT ? OFFSET ?",
            [*values, limit, offset],
        ).fetchall()
        events = []
        for row in rows:
            item = dict(row)
            item["severity_name"] = SEVERITY_NAMES.get(item["severity"], str(item["severity"]))
            item["facility_name"] = FACILITY_NAMES.get(item["facility"], str(item["facility"]))
            item["source"] = "audit" if item["app_name"].lower() == "hamd-audit" else "device"
            events.append(item)
        return {"events": events, "total": total, "limit": limit, "offset": offset}

    def facets(self) -> dict:
        def values(column: str) -> list[str]:
            return [
                row[0]
                for row in self.connection.execute(
                    f"SELECT DISTINCT {column} FROM events WHERE {column} <> '' ORDER BY {column}"
                )
            ]

        row = self.connection.execute(
            "SELECT COUNT(*), MIN(received_at), MAX(received_at) FROM events"
        ).fetchone()
        return {
            "hostnames": values("hostname"),
            "applications": values("app_name"),
            "transports": values("transport"),
            "count": row[0],
            "oldest": row[1],
            "newest": row[2],
        }

    def purge(self, retention_days: int, now: datetime | None = None) -> int:
        current = now or datetime.now(timezone.utc)
        cutoff = (current - timedelta(days=retention_days)).isoformat(timespec="milliseconds").replace(
            "+00:00", "Z"
        )
        cursor = self.connection.execute("DELETE FROM events WHERE received_at < ?", (cutoff,))
        removed = cursor.rowcount
        self.connection.commit()
        if removed:
            self.connection.execute("PRAGMA incremental_vacuum(2000)")
        return removed

    def close(self) -> None:
        self.connection.close()
