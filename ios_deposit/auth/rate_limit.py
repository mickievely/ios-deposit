import time
import threading
from collections import defaultdict, deque


class RateLimiter:
    def __init__(
        self,
        req_limit: int = 40,
        req_window: int = 60,
        fail_limit: int = 8,
        fail_window: int = 300,
        ban_seconds: int = 600,
    ):
        self.req_limit = max(1, int(req_limit))
        self.req_window = max(1, int(req_window))
        self.fail_limit = max(1, int(fail_limit))
        self.fail_window = max(1, int(fail_window))
        self.ban_seconds = max(1, int(ban_seconds))
        self._lock = threading.Lock()
        self._requests = defaultdict(deque)
        self._fails = defaultdict(deque)
        self._banned_until = {}

    def _prune(self, bucket: deque, window: int, now: float):
        while bucket and now - bucket[0] > window:
            bucket.popleft()

    def blocked(self, ip: str):
        now = time.time()
        with self._lock:
            until = self._banned_until.get(ip, 0)
            if until > now:
                return True, int(until - now)
            if until:
                self._banned_until.pop(ip, None)
            return False, 0

    def hit(self, ip: str) -> bool:
        now = time.time()
        with self._lock:
            bucket = self._requests[ip]
            self._prune(bucket, self.req_window, now)
            if len(bucket) >= self.req_limit:
                return True
            bucket.append(now)
            return False

    def fail_auth(self, ip: str) -> bool:
        now = time.time()
        with self._lock:
            bucket = self._fails[ip]
            self._prune(bucket, self.fail_window, now)
            bucket.append(now)
            if len(bucket) >= self.fail_limit:
                self._banned_until[ip] = now + self.ban_seconds
                bucket.clear()
                return True
            return False

    def clear_fails(self, ip: str):
        with self._lock:
            self._fails.pop(ip, None)
            self._banned_until.pop(ip, None)


def client_ip(handler, trust_proxy: bool) -> str:
    if trust_proxy:
        forwarded = handler.headers.get("X-Forwarded-For") or handler.headers.get("X-Real-IP") or ""
        if forwarded:
            return forwarded.split(",")[0].strip() or handler.client_address[0]
    return handler.client_address[0]
