"""Price table, per-call costing and a hard spend cap.

Prices are USD and are deliberately kept in one place so the README can quote them.
`list_price` is what a call would cost at the published paid rate; `cost` is what we
actually pay (0 on a free tier). Both are recorded so free-tier runs still report
what they would have cost to reproduce commercially.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field

from .models import Usage


class SpendCapExceeded(RuntimeError):
    pass


# $ per million tokens (input, output)
TEXT_PRICES_PER_MTOK: dict[str, tuple[float, float]] = {
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-opus-5-5": (4.00, 20.00),
    "claude-haiku-5-5": (0.10, 0.50),
    "gemini-2.5-flash": (0.30, 2.50),
    "gemini-2.5-flash-lite": (0.10, 0.40),
    "gpt-5-mini": (0.25, 2.00),
    "gpt-5": (1.25, 10.00),
}

# $ per generated image at roughly 1024px
IMAGE_PRICES_PER_IMAGE: dict[str, float] = {
    "gemini-2.5-flash-image": 0.039,
    "flux-1-schnell": 0.003,  # Replicate / Cloudflare list price
    "black-forest-labs/flux-schnell": 0.003,
    "black-forest-labs/flux-dev": 0.025,
    "@cf/black-forest-labs/flux-1-schnell": 0.003,
    "gpt-image-1-mini": 0.011,
    "gpt-image-1": 0.042,
    "mock": 0.0,
}


def text_list_price(model: str, input_tokens: int, output_tokens: int) -> float:
    base = model.split("@")[0]
    if base not in TEXT_PRICES_PER_MTOK:
        # unknown model: be conservative, assume Sonnet-class pricing
        inp, out = TEXT_PRICES_PER_MTOK["claude-sonnet-5-5"]
    else:
        inp, out = TEXT_PRICES_PER_MTOK[base]
    return (input_tokens * inp + output_tokens * out) / 1_000_000


def image_list_price(model: str, images: int = 1) -> float:
    return IMAGE_PRICES_PER_IMAGE.get(model, 0.04) * images


@dataclass
class SpendTracker:
    """Process-wide running total with a hard cap. Thread safe.

    Call `reserve(estimate)` before a paid call so the cap is enforced before money moves,
    then `commit(usage)` with the real figure afterwards.
    """

    cap_usd: float
    total_usd: float = 0.0
    total_list_usd: float = 0.0
    calls: int = 0
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def reserve(self, estimate_usd: float) -> None:
        with self._lock:
            if self.total_usd + estimate_usd > self.cap_usd:
                raise SpendCapExceeded(
                    f"Spend cap {self.cap_usd:.2f} USD would be exceeded: "
                    f"spent {self.total_usd:.4f}, next call ~{estimate_usd:.4f}. "
                    "Raise TELEPHONE_SPEND_CAP_USD to continue."
                )

    def commit(self, usage: Usage) -> None:
        with self._lock:
            self.total_usd += usage.cost_usd
            self.total_list_usd += usage.list_price_usd
            self.calls += 1

    def remaining(self) -> float:
        return max(0.0, self.cap_usd - self.total_usd)


_tracker: SpendTracker | None = None
_tracker_lock = threading.Lock()


def get_tracker(cap_usd: float | None = None) -> SpendTracker:
    """Singleton per process. First caller sets the cap (or it comes from settings)."""
    global _tracker
    with _tracker_lock:
        if _tracker is None:
            if cap_usd is None:
                from .config import get_settings

                cap_usd = get_settings().telephone_spend_cap_usd
            _tracker = SpendTracker(cap_usd=cap_usd)
        return _tracker


def reset_tracker(cap_usd: float) -> SpendTracker:
    global _tracker
    with _tracker_lock:
        _tracker = SpendTracker(cap_usd=cap_usd)
        return _tracker
