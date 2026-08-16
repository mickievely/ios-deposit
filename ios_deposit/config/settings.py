import json
import os
from dataclasses import dataclass, field
from typing import List, Optional
from urllib.parse import urlparse

from ios_deposit.data.store import DB_NAME


def _strip_host(value: str) -> str:
    return (value or "").split(",")[0].strip().split(":")[0].lower().rstrip(".")


def _safe_webhook_url(url: str) -> str:
    if not url:
        return ""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return ""
    return url


def _as_int(value, default: int, lo: int, hi: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = default
    return max(lo, min(hi, number))


def _as_float(value, default: float, lo: float, hi: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = default
    return max(lo, min(hi, number))


@dataclass
class Settings:
    host: str = "0.0.0.0"
    port: int = 8088
    domain: str = ""
    https: bool = False
    base_path: str = ""
    allowed_hosts: List[str] = field(default_factory=list)
    trust_proxy: bool = True
    api_key: str = ""
    webhook_url: str = ""
    webhook_api_key: str = ""
    webhook_timeout: float = 10
    data_dir: str = "data/charge_api"
    rate_limit: int = 40
    rate_window: int = 60
    auth_fail_limit: int = 8
    auth_fail_window: int = 300
    auth_ban_seconds: int = 600
    max_body_bytes: int = 50000
    handler_timeout: float = 15
    request_timeout: float = 15
    request_queue: int = 64

    @classmethod
    def from_dict(cls, cfg: dict, *, data_dir: Optional[str] = None) -> "Settings":
        raw_domain = str(cfg.get("domain") or cfg.get("public_url") or "").strip()
        domain, inferred_https, inferred_path = parse_domain_input(raw_domain)

        https_cfg = cfg.get("https")
        if https_cfg is None:
            https = True if inferred_https is None and domain else bool(inferred_https)
        else:
            https = bool(https_cfg)

        base_path = str(cfg.get("base_path") or inferred_path or "").strip()
        if base_path and not base_path.startswith("/"):
            base_path = "/" + base_path
        base_path = base_path.rstrip("/")

        allowed = cfg.get("allowed_hosts") or []
        if isinstance(allowed, str):
            allowed = [part.strip() for part in allowed.split(",") if part.strip()]
        allowed = [_strip_host(item) for item in allowed if item]
        if domain and _strip_host(domain) not in allowed:
            allowed.append(_strip_host(domain))

        return cls(
            host=str(cfg.get("host", "0.0.0.0")),
            port=_as_int(cfg.get("port", 8088), 8088, 1, 65535),
            domain=domain,
            https=https,
            base_path=base_path,
            allowed_hosts=allowed,
            trust_proxy=bool(cfg.get("trust_proxy", bool(domain))),
            api_key=str(cfg.get("api_key", "") or ""),
            webhook_url=_safe_webhook_url(str(cfg.get("webhook_url", "") or "").strip()),
            webhook_api_key=str(cfg.get("webhook_api_key", "") or "").strip(),
            webhook_timeout=_as_float(cfg.get("webhook_timeout", 10), 10, 1, 120),
            data_dir=data_dir if data_dir is not None else str(cfg.get("data_dir", "data/charge_api")),
            rate_limit=_as_int(cfg.get("rate_limit", 40), 40, 1, 10000),
            rate_window=_as_int(cfg.get("rate_window", 60), 60, 1, 86400),
            auth_fail_limit=_as_int(cfg.get("auth_fail_limit", 8), 8, 1, 1000),
            auth_fail_window=_as_int(cfg.get("auth_fail_window", 300), 300, 1, 86400),
            auth_ban_seconds=_as_int(cfg.get("auth_ban_seconds", 600), 600, 1, 86400),
            max_body_bytes=_as_int(cfg.get("max_body_bytes", 50000), 50000, 1024, 1_000_000),
            handler_timeout=_as_float(
                cfg.get("handler_timeout", cfg.get("timeout", 15)), 15, 1, 120
            ),
            request_timeout=_as_float(cfg.get("request_timeout", 15), 15, 1, 120),
            request_queue=_as_int(cfg.get("request_queue", 64), 64, 8, 1024),
        )

    @property
    def db_path(self) -> str:
        return os.path.join(self.data_dir, DB_NAME)

    @property
    def public_url(self) -> str:
        if self.domain:
            scheme = "https" if self.https else "http"
            return f"{scheme}://{self.domain}{self.base_path}"
        display = "127.0.0.1" if self.host in ("0.0.0.0", "::") else self.host
        return f"http://{display}:{self.port}{self.base_path}"

    @property
    def charge_url(self) -> str:
        return f"{self.public_url}/charge"

    @property
    def health_url(self) -> str:
        return f"{self.public_url}/health"

    def host_allowed(self, headers) -> bool:
        if not self.domain and not self.allowed_hosts:
            return True
        host = request_hostname(headers, self.trust_proxy)
        if not host:
            return True
        if host in ("localhost", "127.0.0.1", "::1"):
            return True
        allowed = set(self.allowed_hosts)
        if self.domain:
            allowed.add(_strip_host(self.domain))
        return host in allowed


def parse_domain_input(raw: str):
    value = (raw or "").strip()
    if not value:
        return "", None, ""

    inferred_https = None
    if "://" not in value:
        value = "http://" + value
    else:
        inferred_https = value.lower().startswith("https://")

    parsed = urlparse(value)
    host = parsed.netloc or parsed.path
    host = host.split("@")[-1]
    if host.endswith(":443") and inferred_https:
        host = host[:-4]
    if host.endswith(":80") and inferred_https is False:
        host = host[:-3]
    path = parsed.path if parsed.netloc else ""
    if path == "/":
        path = ""
    return host, inferred_https, path


def request_hostname(headers, trust_proxy: bool) -> str:
    if trust_proxy:
        forwarded = headers.get("X-Forwarded-Host") or headers.get("X-Forwarded-Server") or ""
        if forwarded:
            return _strip_host(forwarded)
    return _strip_host(headers.get("Host", ""))


def load_settings(path: str, *, data_dir: Optional[str] = None) -> Settings:
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    if data_dir is None:
        base = os.path.dirname(os.path.abspath(path))
        data_dir = os.path.join(base, str(raw.get("data_dir", "data/charge_api")))
    return Settings.from_dict(raw, data_dir=data_dir)
