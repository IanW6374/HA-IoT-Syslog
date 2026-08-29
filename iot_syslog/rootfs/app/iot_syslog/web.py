"""Ingress-only search interface and JSON API."""

from __future__ import annotations

import csv
import io
import ssl
from pathlib import Path

from aiohttp import web

from .ingest import EventIngestor
from .storage import EventStore
from .tls import TLSMaterial


FILTER_KEYS = ("q", "hostname", "app", "source", "transport", "severity", "start", "end")


def _filters(request: web.Request) -> dict[str, object]:
    result: dict[str, object] = {}
    for key in FILTER_KEYS:
        value = request.query.get(key, "").strip()
        if value:
            result[key] = value
    if "severity" in result:
        try:
            severity = int(result["severity"])
        except (TypeError, ValueError) as error:
            raise web.HTTPBadRequest(text="severity must be an integer") from error
        if not 0 <= severity <= 7:
            raise web.HTTPBadRequest(text="severity must be between 0 and 7")
        result["severity"] = severity
    return result


def _integer_query(request: web.Request, key: str, default: int, low: int, high: int) -> int:
    try:
        value = int(request.query.get(key, default))
    except (TypeError, ValueError) as error:
        raise web.HTTPBadRequest(text=f"{key} must be an integer") from error
    if not low <= value <= high:
        raise web.HTTPBadRequest(text=f"{key} must be between {low} and {high}")
    return value


@web.middleware
async def security_headers(request: web.Request, handler):
    response = await handler(request)
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; style-src 'self'; script-src 'self'; "
        "img-src 'self' data:; connect-src 'self'; frame-ancestors 'self'"
    )
    return response


class WebInterface:
    def __init__(
        self,
        store: EventStore,
        ingestor: EventIngestor,
        tls_material: TLSMaterial | None,
        retention_days: int,
        server_names: tuple[str, ...],
        static_dir: Path,
    ):
        self.store = store
        self.ingestor = ingestor
        self.tls_material = tls_material
        self.retention_days = retention_days
        self.server_names = server_names
        self.static_dir = static_dir
        self.runner: web.AppRunner | None = None
        self.site: web.TCPSite | None = None

    async def start(self, port: int) -> int:
        app = web.Application(middlewares=[security_headers], client_max_size=1024 * 1024)
        app.router.add_get("/", self.index)
        app.router.add_get("/events", self.index)
        app.router.add_get("/settings", self.index)
        app.router.add_get("/app.js", self.javascript)
        app.router.add_get("/styles.css", self.styles)
        app.router.add_get("/api/events", self.events)
        app.router.add_get("/api/facets", self.facets)
        app.router.add_get("/api/status", self.status)
        app.router.add_get("/api/export.csv", self.export_csv)
        app.router.add_get("/api/ca.der", self.ca_certificate_der)
        app.router.add_get("/api/ca.pem", self.ca_certificate_pem)
        self.runner = web.AppRunner(app, access_log=None)
        await self.runner.setup()
        self.site = web.TCPSite(self.runner, "0.0.0.0", port)
        await self.site.start()
        sockets = self.site._server.sockets if self.site._server else []
        return int(sockets[0].getsockname()[1]) if sockets else port

    async def index(self, request: web.Request) -> web.Response:
        page = request.path.strip("/") or "overview"
        body = (self.static_dir / "index.html").read_text().replace(
            '<body>', '<body data-page="' + page + '">', 1
        )
        return web.Response(text=body, content_type="text/html")

    async def javascript(self, _request: web.Request) -> web.FileResponse:
        return web.FileResponse(self.static_dir / "app.js")

    async def styles(self, _request: web.Request) -> web.FileResponse:
        return web.FileResponse(self.static_dir / "styles.css")

    async def events(self, request: web.Request) -> web.Response:
        result = self.store.search(
            _filters(request),
            limit=_integer_query(request, "limit", 100, 1, 500),
            offset=_integer_query(request, "offset", 0, 0, 10_000_000),
        )
        return web.json_response(result)

    async def facets(self, _request: web.Request) -> web.Response:
        return web.json_response(self.store.facets())

    async def status(self, _request: web.Request) -> web.Response:
        stored = self.store.facets()["count"]
        return web.json_response(
            {
                "stored": stored,
                "accepted": self.ingestor.accepted,
                "persisted": self.ingestor.persisted,
                "dropped": self.ingestor.dropped,
                "queued": self.ingestor.queue.qsize(),
                "retention_days": self.retention_days,
                "tls": self.tls_material is not None,
                "tls_generated": bool(self.tls_material and self.tls_material.generated),
                "tls_ca_sha256": self.tls_material.ca_sha256 if self.tls_material else None,
                "tls_server_names": self.server_names if self.tls_material else [],
                "ca_download": bool(self.tls_material and self.tls_material.ca_certificate),
            }
        )

    def _ca_pem(self) -> bytes:
        if not self.tls_material or not self.tls_material.ca_certificate:
            raise web.HTTPNotFound(text="No CA certificate is available in the current TLS mode")
        return self.tls_material.ca_certificate.read_bytes()

    async def ca_certificate_der(self, _request: web.Request) -> web.Response:
        pem = self._ca_pem().decode("ascii")
        return web.Response(
            body=ssl.PEM_cert_to_DER_cert(pem),
            content_type="application/pkix-cert",
            headers={"Content-Disposition": 'attachment; filename="iot-syslog-ca.der"'},
        )

    async def ca_certificate_pem(self, _request: web.Request) -> web.Response:
        return web.Response(
            body=self._ca_pem(),
            content_type="application/x-pem-file",
            headers={"Content-Disposition": 'attachment; filename="iot-syslog-ca.pem"'},
        )

    async def export_csv(self, request: web.Request) -> web.Response:
        result = self.store.search(_filters(request), limit=500, offset=0)
        output = io.StringIO()
        columns = (
            "received_at", "event_time", "hostname", "source", "app_name", "severity_name",
            "facility_name", "transport", "peer", "message", "raw",
        )
        writer = csv.DictWriter(output, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(result["events"])
        return web.Response(
            text=output.getvalue(),
            content_type="text/csv",
            headers={"Content-Disposition": 'attachment; filename="iot-syslog.csv"'},
        )

    async def close(self) -> None:
        if self.runner:
            await self.runner.cleanup()
