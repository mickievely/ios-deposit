import datetime
import json
import urllib.error
import urllib.request
from typing import Any, Tuple
from urllib.parse import urlparse

from ios_deposit.parse.deposit import parse_deposit_message


def _assert_http_url(url: str):
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise RuntimeError("webhook_url 은 http(s) 주소만 됩니다")


def forward_to_webhook(
    message: str,
    webhook_url: str,
    *,
    api_key: str = "",
    timeout: float = 10.0,
) -> Tuple[bool, Any, str]:
    _assert_http_url(webhook_url)
    parsed = parse_deposit_message(message)
    payload = {
        "message": message,
        "parsed": parsed,
        "received_at": datetime.datetime.now().isoformat(timespec="seconds"),
    }
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        webhook_url,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "Content-Length": str(len(body)),
            "Connection": "close",
        },
    )
    if api_key:
        req.add_header("X-API-Key", api_key)

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            try:
                data = json.loads(raw) if raw.strip() else {}
            except json.JSONDecodeError:
                data = {"raw": raw[:500]}
            ok = bool(data.get("ok", data.get("matched", resp.status == 200)))
            return ok, data.get("user_id"), str(data.get("message", data.get("detail", "") or ""))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")[:300]
        raise RuntimeError(f"webhook HTTP {e.code}: {detail}") from e


def create_webhook_handler(webhook_url: str, api_key: str = "", timeout: float = 10.0):
    def handler(message: str):
        return forward_to_webhook(message, webhook_url, api_key=api_key, timeout=timeout)

    return handler
