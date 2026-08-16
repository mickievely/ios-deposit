import hashlib
import json
from http.server import BaseHTTPRequestHandler
from typing import Any, Callable, Optional

from ios_deposit.auth.api_key import header_authorized
from ios_deposit.auth.rate_limit import RateLimiter, client_ip
from ios_deposit.config.settings import Settings
from ios_deposit.data.store import RequestStore
from ios_deposit.handler import call_handler
from ios_deposit.parse.deposit import (
    UNSUPPORTED_ACCOUNT,
    is_supported_kakao_account,
    parse_deposit_message,
)
from ios_deposit.router.routes import CHARGE_PATHS, HEALTH_PATH, resolve_path


def build_charge_api_handler(
    handler: Callable[..., Any],
    *,
    api_key: str = "",
    data_dir: str = "data/charge_api",
    loop=None,
    timeout: float = 15.0,
    settings: Settings = None,
):
    cfg = settings or Settings(api_key=api_key, data_dir=data_dir)
    store = RequestStore(cfg.data_dir)
    limiter = RateLimiter(
        req_limit=cfg.rate_limit,
        req_window=cfg.rate_window,
        fail_limit=cfg.auth_fail_limit,
        fail_window=cfg.auth_fail_window,
        ban_seconds=cfg.auth_ban_seconds,
    )
    handler_timeout = cfg.handler_timeout if settings is not None else timeout

    class ChargeAPIHandler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"
        timeout = cfg.request_timeout

        def log_message(self, format, *args):
            pass

        def _send_json(self, status: int, payload: dict, retry_after: Optional[int] = None):
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Connection", "close")
            if retry_after:
                self.send_header("Retry-After", str(max(1, int(retry_after))))
            self.end_headers()
            self.wfile.write(body)

        def _send_empty(self, status: int):
            self.send_response(status)
            self.send_header("Content-Length", "0")
            self.send_header("Connection", "close")
            self.end_headers()

        def _path(self) -> str:
            return resolve_path(self.path, cfg.base_path)

        def do_HEAD(self):
            if self._path() == HEALTH_PATH:
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", "0")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Connection", "close")
                self.end_headers()
                return
            self._send_empty(404)

        def do_GET(self):
            if self._path() == HEALTH_PATH:
                self._send_json(200, {"ok": True, "service": "ios-deposit"})
                return
            self._send_empty(404)

        def _client_ip(self) -> str:
            return client_ip(self, cfg.trust_proxy)

        def _reject_auth(self, ip: str):
            banned = limiter.fail_auth(ip)
            if banned:
                self._send_json(
                    429,
                    {"ok": False, "error": "TOO_MANY_ATTEMPTS"},
                    retry_after=cfg.auth_ban_seconds,
                )
                return
            self._send_json(401, {"ok": False, "error": "UNAUTHORIZED"})

        def do_POST(self):
            if self._path() not in CHARGE_PATHS:
                self._send_empty(404)
                return

            ip = self._client_ip()
            blocked, retry = limiter.blocked(ip)
            if blocked:
                self._send_json(
                    429,
                    {"ok": False, "error": "TOO_MANY_REQUESTS"},
                    retry_after=retry,
                )
                return
            if limiter.hit(ip):
                self._send_json(
                    429,
                    {"ok": False, "error": "TOO_MANY_REQUESTS"},
                    retry_after=cfg.rate_window,
                )
                return

            if not cfg.host_allowed(self.headers):
                self._send_json(403, {"ok": False, "error": "HOST_NOT_ALLOWED"})
                return

            if not header_authorized(self.headers, cfg.api_key):
                self._reject_auth(ip)
                return

            content_type = self.headers.get("Content-Type", "")
            if "application/json" not in content_type.split(";")[0].strip().lower():
                self._send_json(400, {"ok": False, "error": "Content-Type must be application/json"})
                return

            try:
                length = int(self.headers.get("Content-Length", 0))
            except ValueError:
                length = 0
            if length <= 0 or length > cfg.max_body_bytes:
                self._send_json(400, {"ok": False, "error": "Invalid body size"})
                return

            try:
                body = self.rfile.read(length).decode("utf-8")
                data = json.loads(body)
            except Exception:
                self._send_json(400, {"ok": False, "error": "Invalid JSON"})
                return

            if not isinstance(data, dict):
                self._send_json(400, {"ok": False, "error": "Invalid JSON"})
                return

            limiter.clear_fails(ip)

            message = data.get("message") or data.get("content") or ""
            if not isinstance(message, str):
                self._send_json(400, {"ok": False, "error": "Empty message"})
                return
            msg_stripped = message.strip()
            if not msg_stripped:
                self._send_json(400, {"ok": False, "error": "Empty message"})
                return

            msg_hash = hashlib.sha256(msg_stripped.encode("utf-8")).hexdigest()
            print(f"[ios-deposit] 수신 {len(msg_stripped)}자")

            if not store.claim(msg_hash):
                store.record(message=msg_stripped, msg_hash=msg_hash, result="DUPLICATE")
                self._send_json(200, {"ok": False, "duplicate": True})
                return

            if not is_supported_kakao_account(msg_stripped):
                store.record(
                    message=msg_stripped,
                    msg_hash=msg_hash,
                    result="UNSUPPORTED",
                    detail=UNSUPPORTED_ACCOUNT,
                )
                self._send_json(200, {"ok": False, "error": UNSUPPORTED_ACCOUNT})
                return

            parsed = parse_deposit_message(msg_stripped)

            try:
                ok_result, uid, alert_message = call_handler(
                    handler, msg_stripped, loop=loop, timeout=handler_timeout
                )
                store.record(
                    message=msg_stripped,
                    msg_hash=msg_hash,
                    result="OK" if ok_result else "NO_MATCH",
                    detail="approved" if ok_result else "no match",
                    parsed=parsed,
                    user_id=uid,
                )
            except Exception:
                store.record(
                    message=msg_stripped,
                    msg_hash=msg_hash,
                    result="ERROR",
                    detail="handler",
                    parsed=parsed,
                )
                self._send_json(200, {"ok": False, "error": "HANDLER_ERROR", "parsed": parsed})
                return

            resp = {"ok": ok_result, "parsed": parsed}
            if uid is not None:
                resp["user_id"] = uid
            if ok_result and alert_message:
                resp["message"] = alert_message
            self._send_json(200, resp)

    return ChargeAPIHandler
