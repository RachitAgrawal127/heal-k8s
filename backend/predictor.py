"""
Heal-K8s — Predictive Engine
Person B — Day 1: Core rate-of-change calculator

Predicts OOMKill crashes BEFORE they happen using time-series analysis.
No ML. No LLM. Pure math.

Three conditions must ALL be met before an alert fires:
  1. Growth sustained for 45+ seconds (not a spike)
  2. Growth rate above 0.5 MB/s minimum
  3. At least 6 consecutive rising readings
"""


class PredictiveEngine:
    """Time-series rate-of-change calculator for memory leak detection."""

    # ── Tuning Parameters ──
    MIN_SUSTAINED_SECONDS = 45       # Growth must last this long
    MIN_GROWTH_RATE_MB_S = 0.5       # Minimum MB/s to be considered a leak
    MIN_CONSECUTIVE_RISES = 6        # Minimum consecutive rising readings
    SAMPLE_INTERVAL_SECONDS = 10     # Prometheus scrape interval

    def analyze(self, memory_readings: list[float], memory_limit_mb: float) -> dict:
        """
        Analyze a list of memory readings (in MB) against a memory limit.

        Args:
            memory_readings: List of memory values in MB, sampled every SAMPLE_INTERVAL_SECONDS.
            memory_limit_mb: The pod's memory limit in MB (e.g. 512).

        Returns:
            dict with keys: alert (bool), diagnosis (str), confidence (float),
                            predicted_seconds_to_oom (int or None)
        """
        if len(memory_readings) < self.MIN_CONSECUTIVE_RISES:
            return self._no_alert("Insufficient data — need at least "
                                  f"{self.MIN_CONSECUTIVE_RISES} readings.")

        # Count consecutive rising readings from the end
        consecutive_rises = 0
        for i in range(len(memory_readings) - 1, 0, -1):
            if memory_readings[i] > memory_readings[i - 1]:
                consecutive_rises += 1
            else:
                break

        # Condition 3: At least MIN_CONSECUTIVE_RISES consecutive rises
        if consecutive_rises < self.MIN_CONSECUTIVE_RISES:
            return self._no_alert(
                f"Only {consecutive_rises} consecutive rising readings — "
                f"need {self.MIN_CONSECUTIVE_RISES}. Likely a transient spike."
            )

        # Calculate growth rate over the sustained window
        window_start_idx = len(memory_readings) - 1 - consecutive_rises
        window_start_mb = memory_readings[window_start_idx]
        window_end_mb = memory_readings[-1]
        window_duration_seconds = consecutive_rises * self.SAMPLE_INTERVAL_SECONDS

        # Condition 1: Sustained for MIN_SUSTAINED_SECONDS
        if window_duration_seconds < self.MIN_SUSTAINED_SECONDS:
            return self._no_alert(
                f"Growth window is only {window_duration_seconds}s — "
                f"need {self.MIN_SUSTAINED_SECONDS}s sustained. "
                "Likely a GC spike, not a leak."
            )

        growth_mb = window_end_mb - window_start_mb
        growth_rate_mb_per_s = growth_mb / window_duration_seconds

        # Condition 2: Growth rate above MIN_GROWTH_RATE_MB_S
        if growth_rate_mb_per_s < self.MIN_GROWTH_RATE_MB_S:
            return self._no_alert(
                f"Growth rate is {growth_rate_mb_per_s:.2f} MB/s — "
                f"below threshold of {self.MIN_GROWTH_RATE_MB_S} MB/s."
            )

        # ── ALL THREE CONDITIONS MET — predict time to OOM ──
        remaining_mb = memory_limit_mb - window_end_mb
        if remaining_mb <= 0:
            predicted_seconds = 0
        else:
            predicted_seconds = int(remaining_mb / growth_rate_mb_per_s)

        # Confidence scales with how many conditions are exceeded
        confidence = min(0.99, 0.70 + (consecutive_rises - self.MIN_CONSECUTIVE_RISES) * 0.03
                         + (growth_rate_mb_per_s - self.MIN_GROWTH_RATE_MB_S) * 0.05)

        return {
            "alert": True,
            "diagnosis": (
                f"Sustained memory growth detected — "
                f"{growth_rate_mb_per_s:.1f} MB/s over {window_duration_seconds}s. "
                f"OOMKill predicted in {predicted_seconds} seconds."
            ),
            "confidence": round(confidence, 2),
            "predicted_seconds_to_oom": predicted_seconds,
            "growth_rate_mb_per_s": round(growth_rate_mb_per_s, 2),
            "consecutive_rises": consecutive_rises,
        }

    @staticmethod
    def _no_alert(reason: str) -> dict:
        """Return a safe no-alert result."""
        return {
            "alert": False,
            "diagnosis": reason,
            "confidence": None,
            "predicted_seconds_to_oom": None,
        }


# ── Standalone test ──
if __name__ == "__main__":
    engine = PredictiveEngine()

    # Test 1: Real memory leak — should fire alert
    leak_readings = [120, 145, 178, 210, 255, 301, 355, 410]
    result = engine.analyze(leak_readings, memory_limit_mb=512)
    print("=== Test 1: Memory Leak ===")
    print(f"  Alert: {result['alert']}")
    print(f"  Diagnosis: {result['diagnosis']}")
    print(f"  Confidence: {result['confidence']}")
    print(f"  Seconds to OOM: {result['predicted_seconds_to_oom']}")
    print()

    # Test 2: GC spike — should NOT fire alert
    gc_spike = [120, 200, 280, 150, 120, 118, 122, 119]
    result = engine.analyze(gc_spike, memory_limit_mb=512)
    print("=== Test 2: GC Spike (False Positive Check) ===")
    print(f"  Alert: {result['alert']}")
    print(f"  Diagnosis: {result['diagnosis']}")
    print()

    # Test 3: Too few readings
    short = [100, 120, 140]
    result = engine.analyze(short, memory_limit_mb=512)
    print("=== Test 3: Insufficient Data ===")
    print(f"  Alert: {result['alert']}")
    print(f"  Diagnosis: {result['diagnosis']}")
