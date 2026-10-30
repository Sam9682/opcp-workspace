"""Bug condition exploration check for the nginx reverse-proxy 504 timeout.

Spec: .kiro/specs/nginx-proxy-timeout-increase/

This check encodes the EXPECTED (fixed) behavior for the bug condition. It is
written BEFORE the fix and is EXPECTED TO FAIL on the unfixed proxy -- its
failure (a ~60s ``504 Gateway Time-out``) confirms the bug exists.

Bug condition (isBugCondition), from bugfix.md / design.md::

    FUNCTION isBugCondition(X)
      RETURN X.upstream = "backend"
             AND X.backendResponseTime > 60 seconds
             AND X.backendResponseTime <= 600 seconds

Property 1 (Bug Condition - Backend requests complete up to 600s):
  For any request where isBugCondition holds, the proxy SHALL forward the real
  backend response to the client WITHOUT substituting an HTTP 504 Gateway
  Time-out (``NOT isGatewayTimeout(result)``).

Validates: Requirements 1.1, 1.2, 1.3 (2.1, 2.2, 2.3 after fix)

Scoped PBT approach
-------------------
The bug is deterministic: nginx aborts *every* backend-proxied request whose
response exceeds the implicit 60s default, so the
"for all X where isBugCondition(X)" quantifier collapses to a few concrete
failing cases inside the ``(60s, 600s]`` window rather than sampling the whole
range. To keep the check fast while still exercising the >60s cliff, the stub's
"long" sleep is capped (default ~75s, overridable). The key observable is the
same regardless of the exact sleep: the UNFIXED proxy returns a proxy-origin
504 at ~60s instead of the backend body.

How the proxy layer is exercised
--------------------------------
The defect lives in the nginx config (``conf/nginx.conf.template``), not in
application code, so the FastAPI ``TestClient`` harness cannot see it -- it
never crosses a proxy. This check therefore stands up the REAL unfixed proxy
behavior directly:

  * a slow Python HTTP stub plays the ``backend`` upstream
    (``backend-component:8000``): it sleeps for a requested number of seconds
    and then returns a JSON body, exactly like a slow ``/api/...`` call;
  * nginx is run from a config whose backend ``location`` blocks are copied
    verbatim from ``conf/nginx.conf.template`` -- crucially WITHOUT any
    ``proxy_connect_timeout`` / ``proxy_send_timeout`` / ``proxy_read_timeout``
    -- so nginx applies its built-in 60s default, reproducing the production
    behavior;
  * requests are driven through nginx and the elapsed time, status,
    ``Content-Type`` and ``Server`` headers are inspected.

A guard asserts the generated proxy config contains NO ``proxy_*_timeout``
directive, so the check genuinely exercises the "unfixed" state. After the fix
(task 3.x adds the three ``600s`` directives to the template), re-running this
check with the fixed config lets the slow calls complete and the assertions
pass -- which is why the check encodes the fixed-behavior assertions now.

DO NOT "fix" this check (or the nginx config) when it fails on the unfixed
proxy -- the ~60s 504 failure IS the expected counterexample that documents the
bug.
"""
import os
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

# nginx's built-in default for every proxy_*_timeout phase.
NGINX_DEFAULT_TIMEOUT_S = 60

# Backend "long" response time used to trigger the bug. It must sit inside the
# bug window (60s, 600s]; kept modestly above 60s so the unfixed check fails
# quickly (~60s) while still being unambiguously past the cliff. Override with
# NGINX_BUG_SLEEP_S for a fuller ~90s document-adapter-style reproduction.
LONG_SLEEP_S = int(os.environ.get("NGINX_BUG_SLEEP_S", "75"))

# A sub-60s boundary request (Case D) that should complete even on the unfixed
# proxy -- used to locate the 60s cliff.
SHORT_SLEEP_S = int(os.environ.get("NGINX_OK_SLEEP_S", "5"))

# Generous ceiling for the client's own wait so WE never time out before nginx
# does; must exceed both LONG_SLEEP_S and the 60s nginx default.
CLIENT_WAIT_S = max(LONG_SLEEP_S, NGINX_DEFAULT_TIMEOUT_S) + 30

# This whole module drives a real nginx process and multi-minute waits.
pytestmark = [pytest.mark.integration]

_NGINX_BIN = shutil.which("nginx")

requires_nginx = pytest.mark.skipif(
    _NGINX_BIN is None,
    reason="nginx binary not available to exercise the reverse-proxy layer",
)


# ---------------------------------------------------------------------------
# Slow backend stub -- stands in for the `backend` upstream (backend-component:8000).
# ---------------------------------------------------------------------------
class _SlowBackendHandler(BaseHTTPRequestHandler):
    """Sleep ``?sleep=<secs>`` seconds, then return a recognizable JSON body.

    The body and headers are distinctly BACKEND-produced so the assertions can
    tell a real backend response apart from nginx's own 504 HTML error page.
    """

    server_version = "SlowBackendStub/1.0"

    def _handle(self):
        match = re.search(r"[?&]sleep=(\d+)", self.path)
        sleep_s = int(match.group(1)) if match else 0
        time.sleep(sleep_s)
        body = (
            b'{"result":"backend-adaptation-result","slept":%d}' % sleep_s
        )
        try:
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("X-Backend-Stub", "true")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            # nginx closed the upstream connection after its 60s default -- this
            # is exactly the server side of the bug. Swallow it quietly.
            pass

    do_GET = _handle
    do_POST = _handle

    def log_message(self, *args):  # silence the default stderr access log
        pass


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


# ---------------------------------------------------------------------------
# Build an "unfixed" nginx config that mirrors conf/nginx.conf.template's
# backend proxying (no proxy_*_timeout directives) and points `backend` at the
# slow stub. TLS, CORS maps and the frontend upstream are omitted -- they are
# irrelevant to the timeout bug and keep the rootless test config minimal.
# ---------------------------------------------------------------------------
def _template_declares_proxy_timeouts() -> bool:
    """True if conf/nginx.conf.template already sets any proxy_*_timeout.

    On UNFIXED code this is False (the bug). It flips True once task 3.x adds the
    600s directives; the check then exercises the fixed proxy.
    """
    text = TEMPLATE_PATH.read_text(encoding="utf-8")
    return re.search(r"proxy_(connect|send|read)_timeout", text) is not None


def _write_proxy_config(tmp_dir: Path, listen_port: int, backend_port: int) -> Path:
    """Render a runnable nginx.conf reproducing the template's backend proxying.

    If the real template declares proxy_*_timeout directives (post-fix), they are
    propagated into the server block so this same check validates the fix. When
    the template has none (unfixed), none are emitted and nginx uses its 60s
    default -- reproducing the bug.
    """
    prefix = tmp_dir
    (prefix / "logs").mkdir(parents=True, exist_ok=True)

    timeout_block = ""
    if _template_declares_proxy_timeouts():
        # Mirror whatever the fixed template declares so the fixed run passes.
        template_text = TEMPLATE_PATH.read_text(encoding="utf-8")
        directives = re.findall(
            r"proxy_(?:connect|send|read)_timeout\s+\S+\s*;", template_text
        )
        # De-duplicate while preserving order.
        seen = []
        for directive in directives:
            if directive not in seen:
                seen.append(directive)
        timeout_block = "\n            ".join(seen)

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

    upstream backend {{
        server 127.0.0.1:{backend_port};
    }}

    server {{
        listen 127.0.0.1:{listen_port};
        server_name localhost;

        client_max_body_size 100M;
        {timeout_block}

        # Backend-proxied location copied from conf/nginx.conf.template's
        # /api/ block: no proxy_*_timeout -> nginx applies its 60s default.
        location /api/ {{
            proxy_pass http://backend;
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
        # Validate the config first (mirrors the `nginx -t` step in the spec).
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
        # Wait for the listener to accept connections.
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

    def __init__(self, status_code, headers, body, elapsed):
        self.status_code = status_code
        self.headers = headers
        self.body = body
        self.elapsed = elapsed

    @property
    def content_type(self) -> str:
        return (self.headers.get("Content-Type") or "").lower()

    @property
    def server_header(self) -> str:
        return self.headers.get("Server") or ""


def isGatewayTimeout(result: "_ProxyResult") -> bool:
    """A proxy-origin 504 Gateway Time-out (nginx's default HTML error page).

    Distinguishes nginx's own 504 from any backend-produced body: the status is
    504, the body is served as ``text/html`` by nginx, and it carries no
    backend marker header.
    """
    return (
        result.status_code == 504
        and "text/html" in result.content_type
        and result.headers.get("X-Backend-Stub") is None
    )


def _drive(listen_port: int, sleep_s: int, method: str = "GET") -> _ProxyResult:
    """Send one backend-proxied request through nginx and capture the outcome."""
    url = f"http://127.0.0.1:{listen_port}/api/slow?sleep={sleep_s}"
    data = b"{}" if method == "POST" else None
    req = urllib.request.Request(url, data=data, method=method)
    if method == "POST":
        req.add_header("Content-Type", "application/json")
    start = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=CLIENT_WAIT_S) as resp:
            body = resp.read()
            elapsed = time.monotonic() - start
            return _ProxyResult(resp.status, dict(resp.headers), body, elapsed)
    except urllib.error.HTTPError as http_err:
        # nginx returns the 504 as an HTTP error response -> captured here.
        elapsed = time.monotonic() - start
        body = http_err.read()
        return _ProxyResult(http_err.code, dict(http_err.headers), body, elapsed)


def _write_proxy_config_with_timeout(
    tmp_dir: Path, listen_port: int, backend_port: int, read_timeout: str
) -> Path:
    """Render a runnable nginx.conf with an EXPLICIT ``proxy_read_timeout``.

    Used only for the >600s ceiling (Case E / Requirement 2.3): a literal 605s
    wait is impractical, so the ceiling is verified in a *time-scaled* manner.
    This emits a short ``proxy_read_timeout`` (e.g. ``2s``) and drives a backend
    that sleeps past it. The proxy then produces exactly the same proxy-origin
    504 it would at the real 600s ceiling -- proving the timeout is *raised, not
    removed*: a backend still too slow for the configured ceiling continues to
    yield a 504. The 600s production value is independently asserted from the
    template text by ``test_template_now_declares_600s_proxy_timeouts_confirms_fix``.
    """
    prefix = tmp_dir
    (prefix / "logs").mkdir(parents=True, exist_ok=True)

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

    upstream backend {{
        server 127.0.0.1:{backend_port};
    }}

    server {{
        listen 127.0.0.1:{listen_port};
        server_name localhost;

        client_max_body_size 100M;

        # Explicit, short ceiling to time-scale the >600s boundary: a backend
        # exceeding it must still yield a proxy-origin 504 (Requirement 2.3).
        proxy_connect_timeout {read_timeout};
        proxy_send_timeout {read_timeout};
        proxy_read_timeout {read_timeout};

        location /api/ {{
            proxy_pass http://backend;
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


@pytest.fixture()
def proxy_env():
    """Start the slow backend stub + an nginx proxy over the unfixed config."""
    backend_port = _free_port()
    listen_port = _free_port()

    httpd = ThreadingHTTPServer(("127.0.0.1", backend_port), _SlowBackendHandler)
    httpd.daemon_threads = True
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()

    tmp = Path(tempfile.mkdtemp(prefix="nginx_timeout_bug_"))
    conf_path = _write_proxy_config(tmp, listen_port, backend_port)
    try:
        with _NginxProxy(conf_path, tmp, listen_port):
            yield listen_port, conf_path
    finally:
        httpd.shutdown()
        httpd.server_close()
        shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------------------
# Guard: the fix (task 3.1) has added the three proxy_*_timeout directives.
#
# HISTORY: on the UNFIXED proxy this guard was
# ``test_template_currently_has_no_proxy_timeouts_documents_root_cause`` and
# asserted the ABSENCE of every proxy_*_timeout directive -- that absence is the
# root cause (nginx falls back to its 60s default and aborts the slow
# /api/document-adapter/adapt call). As task 1 noted, once the fix adds the
# three 600s directives that root-cause guard flips to failing, which is the
# signal to update/retire it. Task 3.3 retires it here and replaces it with its
# post-fix counterpart: the template now MUST declare all three directives at
# 600s. Only this root-cause guard is updated -- the fixed-behavior assertions
# (Cases A/B/C/D) are left untouched.
# ---------------------------------------------------------------------------
def test_template_now_declares_600s_proxy_timeouts_confirms_fix():
    """conf/nginx.conf.template declares the three proxy_*_timeout at 600s.

    This is the post-fix counterpart of the retired root-cause guard. With
    proxy_connect_timeout / proxy_send_timeout / proxy_read_timeout all present
    and set to 600s at server scope, nginx no longer applies its 60s default to
    backend-proxied locations, so the slow /api/document-adapter/adapt call can
    complete (Requirements 2.1, 2.2). The 600s value also preserves the ceiling
    (Requirement 2.3 -- timeout raised, not removed).

    EXPECTED-ON-FIX: passes (all three directives present at 600s).
    """
    text = TEMPLATE_PATH.read_text(encoding="utf-8")
    for directive in ("proxy_connect_timeout", "proxy_send_timeout", "proxy_read_timeout"):
        assert re.search(rf"{directive}\s+600s\s*;", text), (
            f"{directive} must be declared at 600s in conf/nginx.conf.template "
            "after the fix; the backend proxy ceiling is raised from the 60s "
            "default to 600s."
        )


# ---------------------------------------------------------------------------
# Case A -- Document-adapter-style slow POST: the real reported symptom.
#
# EXPECTED-ON-FIX: returns the real backend JSON, NOT a 504.
# EXPECTED-ON-UNFIXED: fails -- ~60s `504 Gateway Time-out`, text/html.
# ---------------------------------------------------------------------------
@requires_nginx
def test_case_a_document_adapter_slow_post_completes(proxy_env):
    """POST /api/... with ~75s backend work must return the adaptation result."""
    listen_port, _ = proxy_env
    result = _drive(listen_port, LONG_SLEEP_S, method="POST")

    # Property 1: the client receives the real backend response, not a 504.
    assert not isGatewayTimeout(result), (
        "BUG REPRODUCED: POST /api/document-adapter-style call returned a "
        f"proxy-origin 504 after {result.elapsed:.1f}s "
        f"(Content-Type={result.content_type!r}, Server={result.server_header!r}) "
        "instead of the backend adaptation result. The missing proxy_read_timeout "
        "(60s default) aborted the upstream read."
    )
    assert result.status_code == 200, (
        f"expected backend 200 after the fix, got {result.status_code}"
    )
    assert b"backend-adaptation-result" in result.body, (
        "expected the backend-produced body to reach the client"
    )


# ---------------------------------------------------------------------------
# Case B -- Generic slow backend location (stub sleeps > 60s).
#
# EXPECTED-ON-FIX: backend JSON returned.
# EXPECTED-ON-UNFIXED: fails -- ~60s 504.
# ---------------------------------------------------------------------------
@requires_nginx
def test_case_b_generic_slow_backend_location_completes(proxy_env):
    """A GET to a backend location that sleeps > 60s must complete, not 504."""
    listen_port, _ = proxy_env
    result = _drive(listen_port, LONG_SLEEP_S, method="GET")

    assert not isGatewayTimeout(result), (
        "BUG REPRODUCED: backend-proxied GET sleeping "
        f"{LONG_SLEEP_S}s returned a proxy-origin 504 after {result.elapsed:.1f}s "
        "instead of the backend response."
    )
    assert result.status_code == 200
    assert b"backend-adaptation-result" in result.body


# ---------------------------------------------------------------------------
# Case C -- Timing / headers: prove the PROXY (not the backend) closed the
# connection, and that it did so at ~60s with nginx's default 504 HTML page.
#
# EXPECTED-ON-FIX: no 504 -> this assertion's precondition never triggers and it
# asserts the backend response instead.
# EXPECTED-ON-UNFIXED: fails on the `not isGatewayTimeout` assertion with a rich
# counterexample (elapsed ~60s, text/html, Server: nginx/...).
# ---------------------------------------------------------------------------
@requires_nginx
def test_case_c_timeout_originates_at_proxy_around_60s(proxy_env):
    """The 504 must come from nginx at ~60s (text/html, Server: nginx/...)."""
    listen_port, _ = proxy_env
    result = _drive(listen_port, LONG_SLEEP_S, method="POST")

    if isGatewayTimeout(result):
        # Document the counterexample precisely before failing. These are the
        # exact proxy-origin markers from the spec's expected counterexample.
        assert result.elapsed >= NGINX_DEFAULT_TIMEOUT_S - 5, (
            f"504 arrived at {result.elapsed:.1f}s; expected ~60s cliff"
        )
        assert "text/html" in result.content_type, (
            f"expected nginx default 504 page (text/html); got {result.content_type!r}"
        )
        assert result.server_header.lower().startswith("nginx"), (
            f"expected Server: nginx/...; got {result.server_header!r}"
        )
        pytest.fail(
            "BUG REPRODUCED (proxy-origin 504): elapsed="
            f"{result.elapsed:.1f}s status=504 Content-Type={result.content_type!r} "
            f"Server={result.server_header!r} -- the reverse proxy, not the "
            "backend, closed the connection at nginx's 60s default. Confirms the "
            "missing proxy_read_timeout is operative (proxy_connect_timeout / "
            "proxy_send_timeout also absent)."
        )

    # Reached only after the fix: the backend response came through.
    assert result.status_code == 200
    assert result.headers.get("X-Backend-Stub") == "true", (
        "a non-timeout response must carry the backend marker header"
    )


# ---------------------------------------------------------------------------
# Case D -- Boundary near/below 60s: locates the cliff. A sub-60s backend call
# completes even on the UNFIXED proxy, proving the abort is specifically the
# >60s window and not a general proxy failure.
#
# EXPECTED on BOTH unfixed and fixed: passes (backend response returned).
# ---------------------------------------------------------------------------
@requires_nginx
def test_case_d_sub_60s_request_passes_on_both(proxy_env):
    """A sub-60s backend request returns normally even on the unfixed proxy."""
    listen_port, _ = proxy_env
    result = _drive(listen_port, SHORT_SLEEP_S, method="GET")

    assert not isGatewayTimeout(result), (
        f"a {SHORT_SLEEP_S}s (sub-60s) backend request must NOT 504 on either "
        f"proxy; got 504 after {result.elapsed:.1f}s"
    )
    assert result.status_code == 200
    assert b"backend-adaptation-result" in result.body
    assert result.elapsed < NGINX_DEFAULT_TIMEOUT_S, (
        f"sub-60s request took {result.elapsed:.1f}s; expected under the 60s cliff"
    )


# A short, explicit ceiling used to time-scale the >600s boundary so the check
# stays fast. Overridable, but a literal 605s wait is impractical in CI.
CEILING_TIMEOUT_S = int(os.environ.get("NGINX_CEILING_TIMEOUT_S", "2"))


@pytest.fixture()
def scaled_ceiling_env():
    """nginx with a SHORT explicit proxy_*_timeout, over the slow backend stub.

    Stands in for the real 600s ceiling in a time-scaled way so the >600s
    boundary (Requirement 2.3) is verifiable without a literal 10-minute wait.
    """
    backend_port = _free_port()
    listen_port = _free_port()

    httpd = ThreadingHTTPServer(("127.0.0.1", backend_port), _SlowBackendHandler)
    httpd.daemon_threads = True
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()

    tmp = Path(tempfile.mkdtemp(prefix="nginx_timeout_ceiling_"))
    conf_path = _write_proxy_config_with_timeout(
        tmp, listen_port, backend_port, f"{CEILING_TIMEOUT_S}s"
    )
    try:
        with _NginxProxy(conf_path, tmp, listen_port):
            yield listen_port
    finally:
        httpd.shutdown()
        httpd.server_close()
        shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------------------
# Case E -- >600s ceiling boundary (Requirement 2.3: timeout raised, NOT removed).
#
# A literal 605s wait is impractical, so the ceiling is verified time-scaled:
# nginx runs with a short explicit proxy_read_timeout and the backend sleeps
# past it. A backend still too slow for the configured ceiling must continue to
# return a proxy-origin 504 -- exactly the behavior a >600s request gets against
# the production 600s config. The production 600s value itself is asserted from
# the template text by test_template_now_declares_600s_proxy_timeouts_confirms_fix.
#
# EXPECTED (fixed proxy, raised-not-removed ceiling): proxy-origin 504.
# ---------------------------------------------------------------------------
@requires_nginx
def test_case_e_backend_past_ceiling_still_returns_504(scaled_ceiling_env):
    """A backend exceeding the configured proxy ceiling must still 504."""
    listen_port = scaled_ceiling_env
    # Sleep well past the short ceiling to model the >600s case.
    over_ceiling_s = CEILING_TIMEOUT_S + 3
    result = _drive(listen_port, over_ceiling_s, method="POST")

    assert isGatewayTimeout(result), (
        "ceiling NOT enforced: a backend sleeping "
        f"{over_ceiling_s}s past the {CEILING_TIMEOUT_S}s proxy ceiling returned "
        f"status={result.status_code} Content-Type={result.content_type!r} "
        f"after {result.elapsed:.1f}s instead of a proxy-origin 504. Requirement "
        "2.3 requires the timeout be raised, not removed."
    )
    assert result.status_code == 504
    # The proxy closed the connection at ~the ceiling, not after the full sleep.
    assert result.elapsed < over_ceiling_s, (
        f"504 arrived after {result.elapsed:.1f}s; expected near the "
        f"{CEILING_TIMEOUT_S}s ceiling, well before the backend's "
        f"{over_ceiling_s}s sleep completed"
    )
