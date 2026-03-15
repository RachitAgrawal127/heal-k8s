import os
import sys
import pytest

# Add the project root to the import path for tests.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from memory.memory import (
    lookup_pattern,
    store_outcome,
    update_confidence,
    get_all_incidents,
    init_db,
    DB_PATH,
)

import sqlite3


@pytest.fixture(autouse=True)
def clean_db():
    """Wipe the incidents table before every test for isolation."""
    init_db()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM incidents")
        conn.commit()
    yield
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM incidents")
        conn.commit()


class TestLookupPattern:
    def test_returns_none_for_unknown_failure(self):
        result = lookup_pattern("SomethingNewAndUnknown")
        assert result is None

    def test_returns_record_after_store(self):
        store_outcome("OOMKilled", "kubectl rollout restart deployment/myapp", success=True)
        result = lookup_pattern("OOMKilled")
        assert result is not None
        assert result["failure_type"] == "OOMKilled"
        assert result["fix"] == "kubectl rollout restart deployment/myapp"

    def test_confidence_present_in_result(self):
        store_outcome("CrashLoopBackOff", "kubectl delete pod myapp-xyz", success=True)
        result = lookup_pattern("CrashLoopBackOff")
        assert "confidence" in result
        assert 0.0 <= result["confidence"] <= 1.0

    def test_returns_none_for_empty_db(self):
        assert lookup_pattern("OOMKilled") is None


class TestStoreOutcome:
    def test_new_success_creates_record(self):
        store_outcome("OOMKilled", "kubectl rollout restart deployment/app", success=True)
        result = lookup_pattern("OOMKilled")
        assert result is not None
        assert result["success_count"] == 1
        assert result["failure_count"] == 0

    def test_new_failure_creates_record_with_low_confidence(self):
        store_outcome("ImagePullBackOff", "kubectl delete pod stuck-pod", success=False)
        result = lookup_pattern("ImagePullBackOff")
        assert result is not None
        assert result["confidence"] < 0.5

    def test_repeated_successes_increase_confidence(self):
        for _ in range(5):
            store_outcome("OOMKilled", "kubectl rollout restart deployment/app", success=True)
        result = lookup_pattern("OOMKilled")
        assert result["confidence"] >= 0.8

    def test_mixed_outcomes_adjusts_confidence(self):
        store_outcome("CrashLoopBackOff", "kubectl delete pod myapp-xyz", success=True)
        store_outcome("CrashLoopBackOff", "kubectl delete pod myapp-xyz", success=True)
        store_outcome("CrashLoopBackOff", "kubectl delete pod myapp-xyz", success=False)
        result = lookup_pattern("CrashLoopBackOff")
        assert 0.60 <= result["confidence"] <= 0.70

    def test_failure_updates_failure_count(self):
        store_outcome("OOMKilled", "kubectl rollout restart deployment/app", success=True)
        store_outcome("OOMKilled", "kubectl rollout restart deployment/app", success=False)
        result = lookup_pattern("OOMKilled")
        assert result["failure_count"] >= 1

    def test_fix_command_is_updated_on_new_success(self):
        store_outcome("OOMKilled", "old-fix-command", success=True)
        store_outcome("OOMKilled", "new-better-fix-command", success=True)
        result = lookup_pattern("OOMKilled")
        assert result["fix"] == "new-better-fix-command"

    def test_different_failure_types_stored_independently(self):
        store_outcome("OOMKilled", "fix-a", success=True)
        store_outcome("CrashLoopBackOff", "fix-b", success=False)
        assert lookup_pattern("OOMKilled")["fix"] == "fix-a"
        assert lookup_pattern("CrashLoopBackOff")["fix"] == "fix-b"


class TestUpdateConfidence:
    def test_confidence_is_ratio_of_successes(self):
        # Insert a record manually to test update_confidence in isolation.
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("""
                INSERT INTO incidents (failure_type, fix, success_count, failure_count, confidence)
                VALUES ('TestFailure', 'some-fix', 4, 1, 0.5)
            """)
            conn.commit()

        update_confidence("TestFailure", success=True)
        result = lookup_pattern("TestFailure")
        expected = 5 / 6
        assert abs(result["confidence"] - expected) < 0.02

    def test_all_failures_gives_zero_confidence(self):
        store_outcome("BadFailure", "fix", success=False)
        store_outcome("BadFailure", "fix", success=False)
        store_outcome("BadFailure", "fix", success=False)
        result = lookup_pattern("BadFailure")
        assert result["confidence"] == 0.0

    def test_all_successes_gives_full_confidence(self):
        for _ in range(4):
            store_outcome("GoodFailure", "good-fix", success=True)
        result = lookup_pattern("GoodFailure")
        assert result["confidence"] == 1.0


class TestGetAllIncidents:
    def test_returns_empty_list_when_no_incidents(self):
        result = get_all_incidents()
        assert result == []

    def test_returns_all_stored_incidents(self):
        store_outcome("OOMKilled", "fix-a", success=True)
        store_outcome("CrashLoopBackOff", "fix-b", success=True)
        result = get_all_incidents()
        failure_types = [r["failure_type"] for r in result]
        assert "OOMKilled" in failure_types
        assert "CrashLoopBackOff" in failure_types

    def test_result_has_required_keys(self):
        store_outcome("OOMKilled", "kubectl rollout restart deployment/app", success=True)
        result = get_all_incidents()
        assert len(result) == 1
        record = result[0]
        for key in ["failure_type", "fix", "confidence", "success_count", "failure_count", "last_seen"]:
            assert key in record

    def test_returns_sorted_by_most_recent(self):
        store_outcome("OOMKilled", "fix-a", success=True)
        store_outcome("CrashLoopBackOff", "fix-b", success=True)
        result = get_all_incidents()
        assert result[0]["failure_type"] == "CrashLoopBackOff"