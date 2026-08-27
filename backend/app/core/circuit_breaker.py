"""Circuit Breaker Pattern for Upstream Gateway Services (e.g., Razorpay API).

Prevents cascading failures by failing fast when downstream services are unhealthy.
States:
- CLOSED: Normal operation. Requests flow through. Consecutive failures are tracked.
- OPEN: Tripped. Requests fail fast with CircuitBreakerOpenException without invoking upstream.
- HALF_OPEN: Cooldown period elapsed. A limited number of probe requests are allowed to test recovery.
"""

import time
import enum
import logging
import threading
from typing import Callable, Any, Optional

logger = logging.getLogger("agentpay.circuit_breaker")


class CircuitState(str, enum.Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class CircuitBreakerOpenException(Exception):
    """Raised when an operation is attempted while the circuit breaker is OPEN."""

    def __init__(self, message: str = "Circuit breaker is OPEN. Upstream gateway unavailable."):
        super().__init__(message)


class CircuitBreaker:
    """Thread-safe / async-safe Circuit Breaker."""

    def __init__(
        self,
        name: str = "razorpay_gateway",
        failure_threshold: int = 3,
        recovery_timeout_seconds: float = 30.0,
        half_open_success_threshold: int = 1,
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout_seconds = recovery_timeout_seconds
        self.half_open_success_threshold = half_open_success_threshold

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._consecutive_successes = 0
        self._last_failure_time: Optional[float] = None
        self._last_state_change = time.time()
        self._lock = threading.Lock()

    @property
    def state(self) -> CircuitState:
        with self._lock:
            if self._state == CircuitState.OPEN and self._last_failure_time:
                # Check if cooldown has elapsed
                if time.time() - self._last_failure_time >= self.recovery_timeout_seconds:
                    self._state = CircuitState.HALF_OPEN
                    self._consecutive_successes = 0
                    self._last_state_change = time.time()
                    logger.info(f"[CircuitBreaker:{self.name}] State transition: OPEN -> HALF_OPEN (Testing recovery)")
            return self._state

    def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute a callable wrapped by the circuit breaker."""
        current_state = self.state

        if current_state == CircuitState.OPEN:
            logger.warning(
                f"[CircuitBreaker:{self.name}] Call rejected — Circuit is OPEN (Fail-fast). Cooldown remaining: "
                f"{max(0, round(self.recovery_timeout_seconds - (time.time() - (self._last_failure_time or 0)), 1))}s"
            )
            raise CircuitBreakerOpenException(
                f"Gateway '{self.name}' circuit is OPEN. Failing fast to prevent hangs."
            )

        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as exc:
            # If it's not a circuit breaker exception, record failure
            if not isinstance(exc, CircuitBreakerOpenException):
                self._on_failure(exc)
            raise exc

    def _on_success(self):
        with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._consecutive_successes += 1
                if self._consecutive_successes >= self.half_open_success_threshold:
                    self._state = CircuitState.CLOSED
                    self._failure_count = 0
                    self._consecutive_successes = 0
                    self._last_state_change = time.time()
                    logger.info(f"[CircuitBreaker:{self.name}] State transition: HALF_OPEN -> CLOSED (Service restored)")
            elif self._state == CircuitState.CLOSED:
                self._failure_count = 0

    def _on_failure(self, exc: Exception):
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()
            logger.warning(
                f"[CircuitBreaker:{self.name}] Failure recorded ({self._failure_count}/{self.failure_threshold}): {exc}"
            )

            if self._state in (CircuitState.CLOSED, CircuitState.HALF_OPEN):
                if self._failure_count >= self.failure_threshold or self._state == CircuitState.HALF_OPEN:
                    self._state = CircuitState.OPEN
                    self._last_state_change = time.time()
                    logger.error(f"[CircuitBreaker:{self.name}] State transition -> OPEN (Tripped after failures)")

    def get_status(self) -> dict:
        """Return diagnostic metrics."""
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self._failure_count,
            "failure_threshold": self.failure_threshold,
            "recovery_timeout_seconds": self.recovery_timeout_seconds,
            "last_failure_time": self._last_failure_time,
            "last_state_change": self._last_state_change,
        }

    def reset(self):
        """Force reset circuit breaker to CLOSED."""
        with self._lock:
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._consecutive_successes = 0
            self._last_failure_time = None
            self._last_state_change = time.time()
