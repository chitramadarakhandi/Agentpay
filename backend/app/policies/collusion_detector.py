"""Multi-Agent Collusion & Boundary-Probing Anomaly Detector.

Detects when AI Buyer Agents attempt to reverse-engineer or extract merchant discount
thresholds via automated binary-search probing or excessive repetitive bargaining.
"""

import time
import threading
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, field


@dataclass
class NegotiationProbeHistory:
    attempts: List[float] = field(default_factory=list)
    timestamps: List[float] = field(default_factory=list)
    last_updated: float = field(default_factory=time.time)


class CollusionDetector:
    """Detects multi-agent adversarial boundary extraction and collusion."""

    def __init__(
        self,
        max_attempts_per_session: int = 3,
        step_probing_threshold: int = 3,
        min_step_size: float = 0.5,
    ):
        self.max_attempts_per_session = max_attempts_per_session
        self.step_probing_threshold = step_probing_threshold
        self.min_step_size = min_step_size
        self._history: Dict[str, NegotiationProbeHistory] = {}
        self._lock = threading.Lock()

    def evaluate_negotiation_attempt(
        self,
        session_id: str,
        quote_id: str,
        requested_discount: float,
    ) -> Tuple[bool, Optional[str]]:
        """
        Evaluate if a negotiation request exhibits automated boundary probing or collusion patterns.
        
        Returns:
            (is_suspicious: bool, reason: Optional[str])
        """
        key = f"{session_id}:{quote_id}"
        now = time.time()

        with self._lock:
            if key not in self._history:
                self._history[key] = NegotiationProbeHistory()

            history = self._history[key]
            history.attempts.append(requested_discount)
            history.timestamps.append(now)
            history.last_updated = now

            attempt_count = len(history.attempts)

            # Rule 1: Excessive repeated negotiation turns on the same quote
            if attempt_count > self.max_attempts_per_session:
                return True, (
                    f"Excessive negotiation attempts ({attempt_count}/{self.max_attempts_per_session}) "
                    f"detected on quote '{quote_id}'. Negotiation halted to prevent policy exhaustion."
                )

            # Rule 2: Binary-search or fine-grained incremental probing detection
            if attempt_count >= self.step_probing_threshold:
                # Check for monotonic small-step increments (probing the ceiling)
                diffs = [
                    round(history.attempts[i] - history.attempts[i - 1], 2)
                    for i in range(1, len(history.attempts))
                ]
                
                # If all steps are positive and small (e.g. +1%, +0.5%), flag as boundary extraction
                is_step_probing = all(0.0 < d <= 2.0 for d in diffs[-2:])
                if is_step_probing:
                    return True, (
                        f"Automated boundary-probing attack detected: Agent is systematically stepping "
                        f"discounts {history.attempts} to reverse-engineer merchant policy margin."
                    )

            return False, None

    def reset_session(self, session_id: str, quote_id: str):
        key = f"{session_id}:{quote_id}"
        with self._lock:
            if key in self._history:
                del self._history[key]


# Global collusion detector instance
collusion_detector = CollusionDetector(max_attempts_per_session=3)
