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
        max_tracked: int = 20000,
    ):
        self.req_limit = max(1, int(req_limit))
        self.req_window = max(1, int(req_window))
        self.fail_limit = max(1, int(fail_limit))
        self.fail_window = max(1, int(fail_window))
        self.ban_seconds = max(1, int(ban_seconds))
        self.max_tracked = max(256, int(max_tracked))
        self._lock = threading.Lock()
        self._requests = defaultdict(deque)
        self._fails = defaultdict(deque)
        self._banned_until = {}
        self._ops = 0

    def _prune(self, bucket: deque, window: int, now: float):
        while bucket and now - bucket[0] > window:
            bucket.popleft()

    def _sweep(self, now: float):
        stale = [ip for ip, until in self._banned_until.items() if until <= now]
        for ip in stale:
            self._banned_until.pop(ip, None)

        for store, window in (
            (self._requests, self.req_window),
            (self._fails, self.fail_window),
        ):
            empty = []
            for ip, bucket in store.items():
                self._prune(bucket, window, now)
                if not bucket:
                    empty.append(ip)
            for ip in empty:
                del store[ip]
            while len(store) > self.max_tracked:
                store.pop(next(iter(store)))

        while len(self._banned_until) > self.max_tracked:
            self._banned_until.pop(next(iter(self._banned_until)))

    def _touch_gc(self, now: float):
        self._ops += 1
        if self._ops % 128 == 0:
            self._sweep(now)

    def blocked(self, ip: str):
        now = time.time()
        with self._lock:
            self._touch_gc(now)
            until = self._banned_until.get(ip, 0)
            if until > now:
                return True, int(until - now)
            if until:
                self._banned_until.pop(ip, None)
            return False, 0

    def hit(self, ip: str) -> bool:
        now = time.time()
        with self._lock:
            self._touch_gc(now)
            bucket = self._requests[ip]
            self._prune(bucket, self.req_window, now)
            if len(bucket) >= self.req_limit:
                return True
            bucket.append(now)
            return False

    def fail_auth(self, ip: str) -> bool:
        now = time.time()
        with self._lock:
            self._touch_gc(now)
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
