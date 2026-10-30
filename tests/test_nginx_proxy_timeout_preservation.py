"""Preservation baseline checks for the nginx reverse-proxy timeout fix.

Spec: .kiro/specs/nginx-proxy-timeout-increase/

This module captures the OBSERVED baseline behavior of the reverse proxy for
every input where the bug condition does NOT hold, and asserts that behavior.
It is written BEFORE the fix (observation-first methodology): the baselines are
recorded on the UNFIXED proxy and MUST PASS there, confirming the behavior that
the fix must preserve. The SAME checks are re-run after the fix (task 3.4); they
must still pass, proving the additive ``proxy_*_timeout`` edit changed nothing
but the slow-request ceiling.

Bug condition (isBugCondition), from bugfix.md / design.md::

    FUNCTION isBugCondition(X)
      RETURN X.upstream = "backend"
             AND X.backendResponseTime > 60 seconds
             AND X.backendResponseTime <= 600 seconds

Property 2 (Preservation - Non-buggy requests unchanged):
  For any request where isBugCondition does NOT hold -- fast (<60s) backend
  requests, preflight ``OPTIONS`` on ``/api/``, and all non-backend locations
  (frontend SPA at ``location /``, ``/docs``, ``/openapi.json``, ``/health``) --
  the fixed proxy SHALL produce the same result as the original proxy,
  preserving the upstream target, forwarded headers (``Host``, ``X-Real-IP``,
  ``X-Forwarded-For``, ``X-Forwarded-Proto``), CORS/preflight behavior, TLS, and
  the ``client_max_body_size 100M`` limit.

Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5

Why a self-contained harness
----------------------------
The behavior under preservation lives in the nginx config
(``conf/nginx.conf.template``), not in application code, so the FastAPI
``TestClient`` never crosses the proxy and cannot observe it. Following the
task-1 harness style, this module stands up the REAL proxy behavior directly:

  * a ``backend`` stub echoes back the request method, path and the forwarded
    headers nginx attached, so Case 1 / Case 2 can assert ``proxy_pass
    http://backend`` routing and the ``proxy_set_header`` values;
  * a ``frontend`` stub plays the SPA upstream for ``location /`` (Case 3);
  * nginx is rendered from a config whose upstreams, CORS ``map`` + ``OPTIONS``
    handling, forwarded headers, body-size limit and non-backend locations are
    copied from ``conf/nginx.conf.template`` verbatim. TLS directives and the
    public ``server_name`` are dropped only because a rootless test cannot bind
    443 or ship certs; the 100M ``client_max_body_size`` that governs body-size
    preservation (Requirement 3.5) is kept and exercised directly.

Config renderer and the fix
----------------------------
``_render_preservation_conf`` propagates any ``proxy_*_timeout`` directives it
finds in the real template into the server block. On UNFIXED code none exist, so
none are emitted and these baselines run against the original proxy. Once task
3.x adds the three ``600s`` directives to the template, the renderer picks them
up and the SAME baselines run against the fixed proxy -- which is the whole
point: a higher-but-unreached timeout must leave every fast / non-backend
response byte-for-byte identical.
"""
import json
import re
import shutil
import socket
import subprocess
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
import urllib.error
import urllib.request

# Repository root: tests/ lives directly under the project root.
REPO_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_PATH = REPO_ROOT / "conf" / "nginx.conf.template"

# The public Origin the template's CORS add_header lines echo. Copied verbatim
# from conf/nginx.conf.template so the preflight assertions match the real CORS
# contract regardless of the host the test binds to.
CORS_ORIGIN = "https://ai-shai-web-interface.fr"
CORS_METHODS = "GET, POST, PUT, DELETE, OPTIONS"
CORS_HEADERS = "Authorization, Content-Type"

# The template's body-size ceiling. Requirement 3.5 preservation: an upload up
# to this size must still succeed through the proxy.
CLIENT_MAX_BODY_MB = 100

pytestmark = [pytest.mark.integration]

_NGINX_BIN = shutil.which("nginx")

requires_nginx = pytest.mark.skipif(
    _NGINX_BIN is None,
    reason="nginx binary not available to exercise the reverse-proxy layer",
)


# ---------------------------------------------------------------------------
# Backend stub -- stands in for the `backend` upstream (backend-component:8000).
# It echoes method/path and the forwarded headers nginx attached so the
# preservation checks can assert the proxy_pass target and proxy_set_header
# values survived the fix (Requirements 3.1, 3.2). It also reports the received
# body length so the 100M body-size preservation (Requirement 3.5) is testable.
# ---------------------------------------------------------------------------
class _BackendEchoHandler(BaseHTTPRequestHandler):
    server_version = "BackendEchoStub/1.0"

    def _echo(self):
        length = int(self.headers.get("Content-Length") or 0)
        body_in = self.rfile.read(length) if length else b""
        payload = {
            "upstream": "backend",
            "method": self.command,
            "path": self.path,
            "received_body_len": len(body_in),
            "forwarded": {
                "host": self.headers.get("Host"),
                "x_real_ip": self.headers.get("X-Real-IP"),
                "x_forwarded_for": self.headers.get("X-Forwarded-For"),
                "x_forwarded_proto": self.headers.get("X-Forwarded-Proto"),
            },
        }
        body = json.dumps(payload).encode()
        try:
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("X-Backend-Stub", "true")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    do_GET = _echo
    do_POST = _echo

    def log_message(self, *args):
        pass


# ---------------------------------------------------------------------------
# Frontend stub -- stands in for the `frontend` upstream (SPA at location /).
# ---------------------------------------------------------------------------
class _FrontendHandler(BaseHTTPRequestHandler):
    server_version = "FrontendStub/1.0"

    def do_GET(self):
        body = b"<!doctype html><html><body>OPCP SPA</body></html>"
        try:
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("X-Frontend-Stub", "true")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def log_message(self, *args):
        pass


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


# ---------------------------------------------------------------------------
# Render a runnable nginx.conf that mirrors conf/nginx.conf.template's
# non-timeout behavior: both upstreams, the CORS map + OPTIONS 204 preflight,
# the forwarded headers, the 100M body-size limit, and the /api//docs/
# openapi.json//health/ (backend) and / (frontend) locations. Any
# proxy_*_timeout directives present in the real template are propagated so the
# SAME baselines validate the fixed proxy after task 3.x.
# ---------------------------------------------------------------------------
def _extract_proxy_timeouts() -> str:
    """Return the template's proxy_*_timeout directives, or '' when absent.

    UNFIXED code has none (the bug) -> returns ''. After the fix adds the three
    600s directives this returns them, so the rendered preservation config
    matches the fixed proxy and the baselines re-run unchanged.
    """
    text = TEMPLATE_PATH.read_text(encoding="utf-8")
    directives = re.findall(
        r"proxy_(?:connect|send|read)_timeout\s+\S+\s*;", text
    )
    seen = []
    for directive in directives:
        if directive not in seen:
            seen.append(directive)
    return "\n        ".join(seen)


def _render_preservation_conf(
    tmp_dir: Path, listen_port: int, backend_port: int, frontend_port: int
) -> Path:
    prefix = tmp_dir
    (prefix / "logs").mkdir(parents=True, exist_ok=True)

    timeout_block = _extract_proxy_timeouts()

    conf = f"""
daemon off;
worker_processes 1;
pid {prefix / "nginx.pid"};
error_log {prefix / "logs" / "error.log"} warn;

events {{
    worker_connections 64;
}}

http {{
    access_log off;
    client_body_temp_path {prefix / "client_body"};
    proxy_temp_path {prefix / "proxy"};
    fastcgi_temp_path {prefix / "fastcgi"};
    uwsgi_temp_path {prefix / "uwsgi"};
    scgi_temp_path {prefix / "scgi"};

    upstream frontend {{
        server 127.0.0.1:{frontend_port};
    }}

    upstream backend {{
        server 127.0.0.1:{backend_port};
    }}

    # CORS map copied verbatim from conf/nginx.conf.template.
    map $request_method $cors_method {{
        OPTIONS 11;
        default 0;
    }}

    server {{
        listen 127.0.0.1:{listen_port};
        server_name localhost;

        client_max_body_size {CLIENT_MAX_BODY_MB}M;
        {timeout_block}

        # /api/ block copied from conf/nginx.conf.template (CORS + preflight +
        # forwarded headers). This is the only location affected by the fix.
        location /api/ {{
            add_header Access-Control-Allow-Origin {CORS_ORIGIN} always;
            add_header Access-Control-Allow-Methods "{CORS_METHODS}" always;
            add_header Access-Control-Allow-Headers "{CORS_HEADERS}" always;
            add_header Access-Control-Allow-Credentials true always;
            if ($request_method = OPTIONS) {{
                add_header Access-Control-Allow-Origin {CORS_ORIGIN} always;
                add_header Access-Control-Allow-Methods "{CORS_METHODS}" always;
                add_header Access-Control-Allow-Headers "{CORS_HEADERS}" always;
                add_header Access-Control-Allow-Credentials true always;
                return 204;
            }}
            proxy_pass http://backend;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }}

        location /docs {{
            proxy_pass http://backend;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }}

        location /openapi.json {{
            proxy_pass http://backend;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }}

        location /health {{
            proxy_pass http://backend/health;
            access_log off;
        }}

        location / {{
            proxy_pass http://frontend;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }}
    }}
}}
"""
    conf_path = prefix / "nginx.conf"
    conf_path.write_text(conf, encoding="utf-8")
    return conf_path


class _NginxProxy:
    """Context manager running a real nginx process against the given config."""

    def __init__(self, conf_path: Path, prefix: Path, listen_port: int):
        self.conf_path = conf_path
        self.prefix = prefix
        self.listen_port = listen_port
        self.proc = None

    def __enter__(self):
        check = subprocess.run(
            [_NGINX_BIN, "-p", str(self.prefix), "-c", str(self.conf_path), "-t"],
            capture_output=True,
            text=True,
        )
        assert check.returncode == 0, (
            f"generated nginx config failed `nginx -t`:\n{check.stderr}"
        )
        self.proc = subprocess.Popen(
            [_NGINX_BIN, "-p", str(self.prefix), "-c", str(self.conf_path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        deadline = time.time() + 10
        while time.time() < deadline:
            if self.proc.poll() is not None:
                _, err = self.proc.communicate()
                raise RuntimeError(f"nginx exited early: {err.decode(errors='replace')}")
            try:
                with socket.create_connection(("127.0.0.1", self.listen_port), timeout=0.5):
                    return self
            except OSError:
                time.sleep(0.1)
        raise RuntimeError("nginx did not start listening in time")

    def __exit__(self, *exc):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait(timeout=5)


class _ProxyResult:
    """Observable outcome of a request driven through nginx."""

    def __init__(self, status_code, headers, body):
        self.status_code = status_code
        self.headers = headers
        self.body = body

    @property
    def content_type(self) -> str:
        return (self.headers.get("Content-Type") or "").lower()

    def json(self):
        return json.loads(self.body.decode())


def _drive(
    listen_port: int,
    path: str,
    method: str = "GET",
    data: bytes | None = None,
    extra_headers: dict | None = None,
) -> _ProxyResult:
    """Send one request through nginx and capture status/headers/body."""
    url = f"http://127.0.0.1:{listen_port}{path}"
    req = urllib.request.Request(url, data=data, method=method)
    for key, value in (extra_headers or {}).items():
        req.add_header(key, value)
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return _ProxyResult(resp.status, dict(resp.headers), resp.read())
    except urllib.error.HTTPError as http_err:
        return _ProxyResult(http_err.code, dict(http_err.headers), http_err.read())


@pytest.fixture()
def proxy_env():
    """Start the backend echo stub + frontend stub + nginx over the config."""
    backend_port = _free_port()
    frontend_port = _free_port()
    listen_port = _free_port()

    backend = ThreadingHTTPServer(("127.0.0.1", backend_port), _BackendEchoHandler)
    backend.daemon_threads = True
    frontend = ThreadingHTTPServer(("127.0.0.1", frontend_port), _FrontendHandler)
    frontend.daemon_threads = True
    threading.Thread(target=backend.serve_forever, daemon=True).start()
    threading.Thread(target=frontend.serve_forever, daemon=True).start()

    tmp = Path(tempfile.mkdtemp(prefix="nginx_timeout_preserve_"))
    conf_path = _render_preservation_conf(tmp, listen_port, backend_port, frontend_port)
    try:
        with _NginxProxy(conf_path, tmp, listen_port):
            yield listen_port
    finally:
        backend.shutdown()
        backend.server_close()
        frontend.shutdown()
        frontend.server_close()
        shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------------------
# Case 1 -- Fast backend request preservation (Requirements 3.1, 3.2).
# A sub-60s backend GET/POST is forwarded to the `backend` upstream and the
# forwarded headers are attached exactly as the template declares.
# ---------------------------------------------------------------------------
@requires_nginx
@pytest.mark.parametrize("method", ["GET", "POST"])
def test_case_1_fast_backend_request_preserved(proxy_env, method):
    """A fast /api/ request reaches `backend` with all forwarded headers."""
    listen_port = proxy_env
    data = b'{"q":"hello"}' if method == "POST" else None
    headers = {"Content-Type": "application/json"} if method == "POST" else None
    result = _drive(listen_port, "/api/ping", method=method, data=data, extra_headers=headers)

    assert result.status_code == 200, (
        f"fast backend {method} must return the backend 200, got {result.status_code}"
    )
    # Baseline: routed to the backend upstream (proxy_pass http://backend).
    assert result.headers.get("X-Backend-Stub") == "true"
    payload = result.json()
    assert payload["upstream"] == "backend"
    assert payload["method"] == method
    assert payload["path"] == "/api/ping"

    # Baseline: the four forwarded headers from the template are present.
    forwarded = payload["forwarded"]
    assert forwarded["host"], "Host must be forwarded (proxy_set_header Host)"
    assert forwarded["x_real_ip"], "X-Real-IP must be forwarded"
    assert forwarded["x_forwarded_for"], "X-Forwarded-For must be forwarded"
    assert forwarded["x_forwarded_proto"] == "http", (
        "X-Forwarded-Proto must reflect the request scheme"
    )


# ---------------------------------------------------------------------------
# Case 2 -- CORS / preflight preservation (Requirement 3.3).
# OPTIONS /api/... returns 204 with the Access-Control-Allow-* headers and does
# NOT reach the backend (nginx short-circuits with `return 204`).
# ---------------------------------------------------------------------------
@requires_nginx
def test_case_2_cors_preflight_preserved(proxy_env):
    """OPTIONS /api/... -> 204 with the existing Access-Control-Allow-* headers."""
    listen_port = proxy_env
    result = _drive(
        listen_port,
        "/api/document-adapter/adapt",
        method="OPTIONS",
        extra_headers={
            "Origin": CORS_ORIGIN,
            "Access-Control-Request-Method": "POST",
        },
    )

    assert result.status_code == 204, (
        f"preflight OPTIONS must return 204, got {result.status_code}"
    )
    assert result.headers.get("Access-Control-Allow-Origin") == CORS_ORIGIN
    assert result.headers.get("Access-Control-Allow-Methods") == CORS_METHODS
    assert result.headers.get("Access-Control-Allow-Headers") == CORS_HEADERS
    assert result.headers.get("Access-Control-Allow-Credentials") == "true"
    # The preflight is short-circuited by nginx; it never hit the backend.
    assert result.headers.get("X-Backend-Stub") is None
    assert result.body == b""


# ---------------------------------------------------------------------------
# Case 3 -- Non-backend / backend-doc location preservation (Requirement 3.4).
# location / (frontend SPA) and the /docs, /openapi.json, /health locations
# behave exactly as before.
# ---------------------------------------------------------------------------
@requires_nginx
def test_case_3_frontend_spa_location_preserved(proxy_env):
    """location / is served by the `frontend` upstream, not the backend."""
    listen_port = proxy_env
    result = _drive(listen_port, "/", method="GET")

    assert result.status_code == 200
    assert result.headers.get("X-Frontend-Stub") == "true", (
        "location / must route to the frontend upstream"
    )
    assert result.headers.get("X-Backend-Stub") is None
    assert b"OPCP SPA" in result.body


@requires_nginx
@pytest.mark.parametrize("path", ["/docs", "/openapi.json"])
def test_case_3_backend_doc_locations_preserved(proxy_env, path):
    """/docs and /openapi.json still proxy to the `backend` upstream."""
    listen_port = proxy_env
    result = _drive(listen_port, path, method="GET")

    assert result.status_code == 200
    assert result.headers.get("X-Backend-Stub") == "true", (
        f"{path} must route to the backend upstream"
    )
    payload = result.json()
    assert payload["upstream"] == "backend"
    assert payload["path"] == path


@requires_nginx
def test_case_3_health_location_preserved(proxy_env):
    """/health proxies to the backend's /health (path rewritten by proxy_pass)."""
    listen_port = proxy_env
    result = _drive(listen_port, "/health", method="GET")

    assert result.status_code == 200
    assert result.headers.get("X-Backend-Stub") == "true"
    payload = result.json()
    assert payload["upstream"] == "backend"
    # `proxy_pass http://backend/health;` rewrites the upstream path to /health.
    assert payload["path"] == "/health"


# ---------------------------------------------------------------------------
# Case 4 -- Body-size preservation (Requirement 3.5).
# An upload UP TO client_max_body_size 100M succeeds; crossing the limit is
# rejected with 413 -- both behaviors are governed by the limit the fix leaves
# untouched. (TLS cert/cipher config cannot be exercised in a rootless harness;
# its preservation is covered by the unit-level config checks in task 3.2 that
# confirm the diff is limited to the three added lines.)
# ---------------------------------------------------------------------------
@requires_nginx
def test_case_4_upload_within_body_limit_preserved(proxy_env):
    """A ~1MB upload (well within 100M) is forwarded to the backend intact."""
    listen_port = proxy_env
    payload = b"x" * (1 * 1024 * 1024)  # 1 MiB, comfortably under the 100M cap
    result = _drive(
        listen_port,
        "/api/upload",
        method="POST",
        data=payload,
        extra_headers={"Content-Type": "application/octet-stream"},
    )

    assert result.status_code == 200, (
        f"a within-limit upload must succeed, got {result.status_code}"
    )
    body = result.json()
    assert body["upstream"] == "backend"
    assert body["received_body_len"] == len(payload), (
        "the full body must reach the backend unchanged"
    )


@requires_nginx
def test_case_4_body_size_limit_still_enforced():
    """client_max_body_size is honored: an over-limit upload is rejected (413).

    This proves the body-size ceiling is an active, enforced limit (not cosmetic)
    and that the fix leaves that enforcement behavior intact. Sending a >100M
    body would be wasteful, so a dedicated proxy with a tiny 1M cap exercises the
    over-limit path cheaply; the real template keeps the 100M value (asserted by
    ``test_template_preserves_non_timeout_directives`` and the within-limit case
    above). nginx rejects an over-limit body with 413 before it reaches the
    backend.
    """
    backend_port = _free_port()
    listen_port = _free_port()

    backend = ThreadingHTTPServer(("127.0.0.1", backend_port), _BackendEchoHandler)
    backend.daemon_threads = True
    threading.Thread(target=backend.serve_forever, daemon=True).start()

    tmp = Path(tempfile.mkdtemp(prefix="nginx_timeout_bodycap_"))
    (tmp / "logs").mkdir(parents=True, exist_ok=True)
    cap_mb = 1
    conf = f"""
daemon off;
worker_processes 1;
pid {tmp / "nginx.pid"};
error_log {tmp / "logs" / "error.log"} warn;

events {{ worker_connections 64; }}

http {{
    access_log off;
    client_body_temp_path {tmp / "client_body"};
    proxy_temp_path {tmp / "proxy"};
    fastcgi_temp_path {tmp / "fastcgi"};
    uwsgi_temp_path {tmp / "uwsgi"};
    scgi_temp_path {tmp / "scgi"};

    upstream backend {{ server 127.0.0.1:{backend_port}; }}

    server {{
        listen 127.0.0.1:{listen_port};
        server_name localhost;
        client_max_body_size {cap_mb}M;

        location /api/ {{
            proxy_pass http://backend;
            proxy_set_header Host $host;
        }}
    }}
}}
"""
    conf_path = tmp / "nginx.conf"
    conf_path.write_text(conf, encoding="utf-8")
    try:
        with _NginxProxy(conf_path, tmp, listen_port):
            oversized = b"x" * ((cap_mb * 1024 * 1024) + 4096)  # just over the cap
            result = _drive(
                listen_port,
                "/api/upload",
                method="POST",
                data=oversized,
                extra_headers={"Content-Type": "application/octet-stream"},
            )
            assert result.status_code == 413, (
                "an over-limit upload must be rejected with 413 by "
                f"client_max_body_size, got {result.status_code}"
            )
            # Rejected by nginx before reaching the backend.
            assert result.headers.get("X-Backend-Stub") is None
    finally:
        backend.shutdown()
        backend.server_close()
        shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------------------
# Guard: the preservation harness must mirror the template's non-timeout
# behavior. This anchors the baselines to the real config so a future accidental
# edit to upstreams / CORS / forwarded headers / body-size would be caught.
# ---------------------------------------------------------------------------
def test_template_preserves_non_timeout_directives():
    """The template keeps its upstreams, CORS/preflight, forwarded headers, and
    non-backend routing -- the surface the fix must not disturb."""
    text = TEMPLATE_PATH.read_text(encoding="utf-8")

    # Upstreams and backend target (Req 3.2, 3.4).
    assert "upstream backend" in text
    assert "upstream frontend" in text
    assert "proxy_pass http://backend" in text
    assert "proxy_pass http://frontend" in text

    # Forwarded headers (Req 3.2).
    for header in (
        "proxy_set_header Host $host",
        "proxy_set_header X-Real-IP $remote_addr",
        "proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for",
        "proxy_set_header X-Forwarded-Proto $scheme",
    ):
        assert header in text, f"forwarded header missing: {header}"

    # CORS / preflight (Req 3.3).
    assert "Access-Control-Allow-Origin" in text
    assert "return 204" in text

    # Non-backend / doc locations (Req 3.4).
    for location in ("location /docs", "location /openapi.json", "location /health", "location / {"):
        assert location in text, f"location missing: {location}"

    # TLS + body-size (Req 3.5).
    assert "ssl_certificate" in text
    assert "ssl_protocols" in text
    assert re.search(r"client_max_body_size\s+100M", text)
