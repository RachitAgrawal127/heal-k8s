"""
QA tests for the signature engine.
"""
import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend.signature_engine import diagnose


class TestDiagnose:
    def test_oomkilled_detected_from_logs(self):
        logs = "Back-off restarting failed container — OOMKilled"
        result = diagnose(logs=logs, metrics={})
        assert result["failure_type"] == "OOMKilled"
        assert result["confidence"] >= 0.99
        assert "kubectl" in result["kubectl_command"]

    def test_crashloopbackoff_detected(self):
        logs = "Warning: Back-off restarting failed container — CrashLoopBackOff"
        result = diagnose(logs=logs, metrics={})
        assert result["failure_type"] == "CrashLoopBackOff"
        assert result["confidence"] >= 0.95

    def test_imagepullbackoff_detected(self):
        logs = "Failed to pull image: ImagePullBackOff"
        result = diagnose(logs=logs, metrics={})
        assert result["failure_type"] == "ImagePullBackOff"

    def test_podpending_detected(self):
        logs = "0/1 nodes available: insufficient memory. PodPending"
        result = diagnose(logs=logs, metrics={})
        assert result["failure_type"] == "PodPending"

    def test_unknown_failure_returns_unknown(self):
        logs = "Some completely new and unrecognized error xj9alpha"
        result = diagnose(logs=logs, metrics={})
        assert result["failure_type"] == "unknown"
        assert result["confidence"] < 0.5

    def test_result_always_has_required_keys(self):
        result = diagnose(logs="OOMKilled", metrics={})
        for key in ["failure_type", "confidence", "kubectl_command"]:
            assert key in result

    def test_case_insensitive_matching(self):
        logs = "oomkilled — container terminated"
        result = diagnose(logs=logs, metrics={})
        assert result["failure_type"] == "OOMKilled"