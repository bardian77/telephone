"""Per-provider token-bucket rate limiting. Free tiers are tight (Gemini: 15 requests per minute)."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field


@dataclass
class TokenBucket:
    rate_per_minute: float
    burst: int = 1
    _tokens: float = field(default=0.0, init=False)
    _updated: float = field(default_factory=time.monotonic, init=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)

    def __post_init__(self) -> None:
        self._tokens = float(self.burst)

    def acquire(self) -> float:
        """Block until a token is available. Returns seconds waited."""
        waited = 0.0
        while True:
            with self._lock:
                now = time.monotonic()
                self._tokens = min(
                    self.burst, self._tokens + (now - self._updated) * self.rate_per_minute / 60
                )
                self._updated = now
                if self._tokens >= 1:
                    self._tokens -= 1
                    return waited
                need = (1 - self._tokens) * 60 / self.rate_per_minute
            time.sleep(need)
            waited += need


DEFAULT_RPM: dict[str, float] = {
    "gemini": 12,  # free tier is 15 rpm; leave headroom
    "gemini-image": 8,
    "cloudflare": 30,
    "anthropic": 50,
    "openai": 30,
    "replicate": 30,
    "mock": 100000,
}

_buckets: dict[str, TokenBucket] = {}
_buckets_lock = threading.Lock()


def bucket_for(provider: str, rpm: float | None = None) -> TokenBucket:
    with _buckets_lock:
        if provider not in _buckets:
            _buckets[provider] = TokenBucket(
                rate_per_minute=rpm or DEFAULT_RPM.get(provider, 30), burst=1
            )
        return _buckets[provider]


def wait_for(provider: str) -> float:
    return bucket_for(provider).acquire()
