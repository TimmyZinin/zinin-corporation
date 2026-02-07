"""Safety systems for Yuki SMM bot — circuit breaker + autonomy."""

import logging
import time
from typing import Optional

logger = logging.getLogger(__name__)


# ── Circuit Breaker ─────────────────────────────────────────────────────────

class CircuitBreaker:
    """Stops auto-operations after N consecutive failures."""

    def __init__(self, threshold: int = 3, cooldown_sec: int = 1800):
        self.threshold = threshold
        self.cooldown_sec = cooldown_sec
        self._failures: list[float] = []
        self._open_since: Optional[float] = None

    @property
    def is_open(self) -> bool:
        """True = circuit is OPEN (broken), operations should stop."""
        if self._open_since is None:
            return False
        # Auto-close after cooldown
        if time.time() - self._open_since > self.cooldown_sec:
            self.reset()
            return False
        return True

    @property
    def status(self) -> str:
        if self.is_open:
            remaining = int(self.cooldown_sec - (time.time() - self._open_since))
            return f"OPEN (сброс через {remaining}s)"
        return f"CLOSED ({len(self._failures)}/{self.threshold} ошибок)"

    def record_success(self):
        """Record a successful operation — resets failure count."""
        self._failures.clear()

    def record_failure(self):
        """Record a failed operation. Opens circuit if threshold reached."""
        self._failures.append(time.time())
        # Keep only recent failures (last 10 min)
        cutoff = time.time() - 600
        self._failures = [t for t in self._failures if t > cutoff]

        if len(self._failures) >= self.threshold:
            self._open_since = time.time()
            logger.warning(
                f"Circuit breaker OPENED: {len(self._failures)} failures in 10 min"
            )

    def reset(self):
        """Manually reset the circuit breaker."""
        self._failures.clear()
        self._open_since = None
        logger.info("Circuit breaker RESET")


# ── Autonomy ────────────────────────────────────────────────────────────────

class Autonomy:
    """2-level autonomy: manual (default) or auto."""

    MANUAL = 1  # All posts require approval
    AUTO = 2    # Auto-publish if confidence >= threshold

    LABELS = {1: "Manual", 2: "Auto"}

    def __init__(self, level: int = 1, confidence_threshold: float = 0.8):
        self.level = level
        self.confidence_threshold = confidence_threshold

    def should_auto_publish(self, confidence: float) -> bool:
        """Check if post should be auto-published."""
        if self.level < self.AUTO:
            return False
        return confidence >= self.confidence_threshold

    @property
    def status(self) -> str:
        label = self.LABELS.get(self.level, "?")
        if self.level == self.AUTO:
            return f"{label} (авто-публикация при confidence ≥ {self.confidence_threshold})"
        return f"{label} (все посты через одобрение)"


# ── Global instances ────────────────────────────────────────────────────────

circuit_breaker = CircuitBreaker(threshold=3, cooldown_sec=1800)
autonomy = Autonomy(level=Autonomy.MANUAL)
