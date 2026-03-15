"""
Heal-K8s — Signature Engine
Skeleton + regex pattern dictionary

Matches known Kubernetes failure patterns against pod logs and metrics.
No LLM. Instant diagnosis. 95-99% confidence on known patterns.

Supported failure types:
  - OOMKilled (99% confidence)
  - CrashLoopBackOff (95% confidence)
  - ImagePullBackOff (99% confidence)
  - PodPending / Unschedulable (90% confidence)
"""

import re


# ── Failure Signature Dictionary ──
# Each entry: { patterns: [regex], confidence: float, diagnosis: str, fix_hint: str }
FAILURE_SIGNATURES = {
    "OOMKilled": {
        "patterns": [
            r"OOMKilled",
            r"Out of memory",
            r"Killed process",
            r"memory cgroup out of memory",
            r"container exceeded memory limit",
        ],
        "confidence": 0.99,
        "diagnosis": "Container killed due to exceeding memory limit (OOMKilled).",
        "fix_hint": "delete_pod",
    },
    "CrashLoopBackOff": {
        "patterns": [
            r"CrashLoopBackOff",
            r"Back-off restarting",
            r"back-off.*restarting failed container",
        ],
        "confidence": 0.95,
        "diagnosis": "Pod is crash-looping — repeatedly crashing and restarting.",
        "fix_hint": "delete_pod",
    },
    "ImagePullBackOff": {
        "patterns": [
            r"ImagePullBackOff",
            r"ErrImagePull",
            r"Failed to pull image",
            r"image.*not found",
        ],
        "confidence": 0.99,
        "diagnosis": "Container image could not be pulled — verify the image name, tag, and registry credentials. "
                     "Deleting the pod re-triggers the pull but will NOT resolve the root cause until "
                     "the image reference in the pod spec is corrected.",
        "fix_hint": "check_image",
    },
    "PodPending": {
        "patterns": [
            r"Insufficient memory",
            r"Insufficient cpu",
            r"Unschedulable",
            r"0/\d+ nodes are available",
            r"FailedScheduling",
        ],
        "confidence": 0.90,
        "diagnosis": "Pod cannot be scheduled — cluster has insufficient resources.",
        "fix_hint": "scale_resources",
    },
}


class SignatureEngine:
    """Regex-based failure signature matching engine."""

    def __init__(self):
        # Pre-compile patterns for performance
        self.compiled_signatures = {}
        for failure_type, sig in FAILURE_SIGNATURES.items():
            compiled = [re.compile(pattern, re.IGNORECASE) for pattern in sig["patterns"]]
            self.compiled_signatures[failure_type] = {
                "patterns": compiled,
                "confidence": sig["confidence"],
                "diagnosis": sig["diagnosis"],
                "fix_hint": sig["fix_hint"],
            }

    def diagnose(
        self,
        logs: str,
        metrics: dict | None = None,
        pod_name: str = "unknown-pod",
        namespace: str = "default",
    ) -> dict:
        """
        Match pod logs against known failure signatures.

        Always returns a dict — never None.
        Check result["failure_type"] == "unknown" to detect no-match / LLM fallback needed.

        Args:
            logs: Raw pod log text or event reason string.
            metrics: Optional metrics dict.
            pod_name: Used to build the kubectl_command suggestion.
            namespace: Kubernetes namespace.

        Returns:
            dict with keys: failure_type, diagnosis, confidence, fix_hint, kubectl_command
        """
        for failure_type, sig in self.compiled_signatures.items():
            for pattern in sig["patterns"]:
                if pattern.search(logs):
                    confidence = sig["confidence"]
                    if metrics:
                        confidence = self._adjust_confidence(failure_type, confidence, metrics)

                    return {
                        "failure_type": failure_type,
                        "diagnosis": sig["diagnosis"],
                        "confidence": round(confidence, 2),
                        "fix_hint": sig["fix_hint"],
                        "kubectl_command": f"kubectl delete pod {pod_name} -n {namespace}",
                    }

        # No match — caller should trigger LLM fallback
        return {
            "failure_type": "unknown",
            "diagnosis": "No known failure pattern matched. LLM fallback required.",
            "confidence": 0.4,
            "fix_hint": "llm_fallback",
            "kubectl_command": f"kubectl delete pod {pod_name} -n {namespace}",
        }

    @staticmethod
    def _adjust_confidence(failure_type: str, base_confidence: float, metrics: dict) -> float:
        """Slightly boost or reduce confidence based on supporting metrics."""
        confidence = base_confidence

        if failure_type == "OOMKilled":
            mem_usage = metrics.get("memory_usage", 0)
            if mem_usage > 0.9:
                confidence = min(1.0, confidence + 0.005)
            elif mem_usage < 0.5:
                confidence = max(0.7, confidence - 0.05)

        if failure_type == "CrashLoopBackOff":
            restart_count = metrics.get("restart_count", 0)
            if restart_count >= 3:
                confidence = min(1.0, confidence + 0.02)

        return confidence


# ── Module-level function ──
_engine = SignatureEngine()


def diagnose(logs: str, metrics: dict | None = None, pod_name: str = "unknown-pod", namespace: str = "default") -> dict:
    """
    Module-level wrapper around SignatureEngine.diagnose().
    Always returns a dict — never None.
    Check result["failure_type"] == "unknown" for LLM fallback trigger.
    """
    return _engine.diagnose(logs=logs, metrics=metrics, pod_name=pod_name, namespace=namespace)


# ── Standalone test ──
if __name__ == "__main__":
    engine = SignatureEngine()

    test_cases = [
        ("OOMKilled: container exceeded memory limit", {"memory_usage": 0.95, "restart_count": 0}),
        ("Back-off restarting failed container", {"memory_usage": 0.3, "restart_count": 5}),
        ("Failed to pull image nginx:latestt", {}),
        ("0/3 nodes are available: Insufficient memory", {}),
        ("Some totally unknown error we've never seen", {}),
    ]

    for logs, metrics in test_cases:
        result = engine.diagnose(logs, metrics)
        print(f"Logs: {logs[:60]}...")
        if result:
            print(f"  -> {result['failure_type']} | Confidence: {result['confidence']} | {result['diagnosis']}")
        else:
            print("  -> No match -- LLM fallback would trigger")
        print()
