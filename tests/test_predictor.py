"""
Person D owns this file — QA tests for Person B's predictor.
Person B builds predictor.py. Person D writes tests against the agreed interface.
"""
import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# These imports will work once Person B creates backend/predictor.py
from backend.predictor import (
    is_sustained_growth,
    calculate_rate_of_change,
)


class TestCalculateRateOfChange:
    def test_steady_growth_returns_positive_rate(self):
        # 10 readings, each 5 MB apart, 10s interval = 0.5 MB/s
        readings = [100 + (i * 5) for i in range(10)]
        rate = calculate_rate_of_change(readings, interval_seconds=10)
        assert rate > 0

    def test_flat_memory_returns_near_zero_rate(self):
        readings = [100.0] * 10
        rate = calculate_rate_of_change(readings, interval_seconds=10)
        assert abs(rate) < 0.01

    def test_dropping_memory_returns_negative_rate(self):
        readings = [200 - (i * 5) for i in range(10)]
        rate = calculate_rate_of_change(readings, interval_seconds=10)
        assert rate < 0

    def test_requires_at_least_two_readings(self):
        with pytest.raises((ValueError, IndexError)):
            calculate_rate_of_change([100], interval_seconds=10)


class TestIsSustainedGrowth:
    def test_sustained_growth_above_threshold_returns_true(self):
        # 6+ consecutive rising readings at > 0.5 MB/s sustained over 45s
        readings = [100 + (i * 1.5) for i in range(10)]  # ~0.15 MB per reading
        result = is_sustained_growth(readings, interval_seconds=10, min_rate_mb_per_s=0.1, window_seconds=45)
        assert result is True

    def test_short_spike_returns_false(self):
        # Spike then drop — GC pattern
        readings = [100, 100, 150, 200, 100, 100, 100, 100, 100, 100]
        result = is_sustained_growth(readings, interval_seconds=10, min_rate_mb_per_s=0.5, window_seconds=45)
        assert result is False

    def test_flat_memory_returns_false(self):
        readings = [128.0] * 10
        result = is_sustained_growth(readings, interval_seconds=10, min_rate_mb_per_s=0.5, window_seconds=45)
        assert result is False

    def test_slow_growth_below_threshold_returns_false(self):
        # Grows, but too slowly
        readings = [100 + (i * 0.01) for i in range(10)]
        result = is_sustained_growth(readings, interval_seconds=10, min_rate_mb_per_s=0.5, window_seconds=45)
        assert result is False

    def test_not_enough_consecutive_readings_returns_false(self):
        # Only 3 rising, then drops — not enough for the 6-reading rule
        readings = [100, 101, 102, 103, 99, 98, 97, 96, 95, 94]
        result = is_sustained_growth(readings, interval_seconds=10, min_rate_mb_per_s=0.1, window_seconds=45)
        assert result is False