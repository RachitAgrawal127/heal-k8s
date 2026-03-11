"""
Heal-K8s Backend — FastAPI Application
Person B — Day 1: Core endpoints + mock implementations

All API contract endpoints are defined here.
Mock functions are used for Person A (k8s executor) and Person D (memory)
until Integration Day (Day 5).
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import time

from backend.predictor import PredictiveEngine
from backend.signature_engine import SignatureEngine

# ──────────────────────────────────────────────
# MOCK — replace Day 5 with: from infrastructure.k8s_executor import restart_pod
def restart_pod(pod_name: str, namespace: str) -> dict:
    """Mock K8s executor — returns fake success."""
    return {"status": "mock_success", "message": f"Mock restart of {pod_name} in {namespace}"}

# MOCK — replace Day 5 with: from memory.memory import lookup_pattern, store_outcome
def lookup_pattern(failure_type: str) -> Optional[dict]:
    """Mock memory lookup — returns None (no memory yet)."""
    return None

def store_outcome(failure_type: str, fix: str, success: bool) -> None:
    """Mock memory store — does nothing."""
    pass
# ──────────────────────────────────────────────

app = FastAPI(
    title="Heal-K8s",
    description="Predictive + Self-Healing Kubernetes Agent",
    version="0.1.0",
)

# Allow frontend (index.html opened via file://) to call the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize engines
predictor = PredictiveEngine()
signature_engine = SignatureEngine()

# ── Shared in-memory state (replaced by real K8s polling later) ──
current_state = {
    "pod_status": "Healthy",
    "memory_readings": [],
    "prediction_seconds": None,
    "badge_type": None,
    "diagnosis": None,
    "confidence": None,
    "kubectl_command": None,
    "memory_hit": False,
}


# ── Request / Response Models ──


class AlertPayload(BaseModel):
    pod_name: str
    namespace: str = "default"
    logs: str
    metrics: dict  # e.g. {"memory_usage": 0.95, "restart_count": 0}


class PredictionPayload(BaseModel):
    pod_name: str
    namespace: str = "default"
    memory_readings: list[float]  # e.g. [120, 145, 178, 210, 255, 301, 355, 410]
    memory_limit_mb: float  # e.g. 512


class ExecutePayload(BaseModel):
    kubectl_command: str


# ── API Endpoints ──


@app.get("/")
def root():
    return {"service": "Heal-K8s", "status": "running", "version": "0.1.0"}


@app.post("/trigger-alert")
def trigger_alert(payload: AlertPayload):
    """
    Receives a real Prometheus alert webhook (or manual trigger).
    Runs the full diagnosis pipeline:
      1. Check incident memory for known fix
      2. Run signature engine for pattern match
      3. Fall back to LLM if nothing matches
    """
    # Step 1 — Check memory for known fix
    memory_result = lookup_pattern(payload.logs)
    if memory_result and memory_result.get("confidence", 0) >= 0.95:
        _update_state(
            pod_status="Warning",
            badge_type="memory_hit",
            diagnosis=memory_result["diagnosis"],
            confidence=memory_result["confidence"],
            kubectl_command=memory_result["fix"],
            memory_hit=True,
        )
        return {"source": "memory", "result": current_state}

    # Step 2 — Signature engine
    sig_result = signature_engine.diagnose(payload.logs, payload.metrics)
    if sig_result:
        kubectl_cmd = f"kubectl delete pod {payload.pod_name} -n {payload.namespace}"
        _update_state(
            pod_status="Warning",
            badge_type="signature",
            diagnosis=sig_result["diagnosis"],
            confidence=sig_result["confidence"],
            kubectl_command=kubectl_cmd,
            memory_hit=False,
        )
        return {"source": "signature", "result": current_state}

    # Step 3 — LLM fallback (Day 3-4, skeleton for now)
    kubectl_cmd = f"kubectl delete pod {payload.pod_name} -n {payload.namespace}"
    _update_state(
        pod_status="Critical",
        badge_type="llm_fallback",
        diagnosis=f"Unknown failure in pod {payload.pod_name}. LLM analysis pending.",
        confidence=0.60,
        kubectl_command=kubectl_cmd,
        memory_hit=False,
    )
    return {"source": "llm_fallback_placeholder", "result": current_state}


@app.post("/trigger-fake-alert")
def trigger_fake_alert(payload: AlertPayload):
    """
    Manual test trigger — works exactly like /trigger-alert.
    Use this when Prometheus is not configured yet.
    """
    return trigger_alert(payload)


@app.post("/trigger-fake-prediction")
def trigger_fake_prediction(payload: PredictionPayload):
    """
    Manual prediction test — simulates the predictive engine flow.
    Accepts a list of memory readings and a memory limit.
    """
    result = predictor.analyze(payload.memory_readings, payload.memory_limit_mb)

    if result["alert"]:
        kubectl_cmd = f"kubectl delete pod {payload.pod_name} -n {payload.namespace}"
        _update_state(
            pod_status="Warning",
            memory_readings=payload.memory_readings,
            prediction_seconds=result["predicted_seconds_to_oom"],
            badge_type="prediction",
            diagnosis=result["diagnosis"],
            confidence=result["confidence"],
            kubectl_command=kubectl_cmd,
            memory_hit=False,
        )
        return {"source": "prediction", "alert": True, "result": current_state}
    else:
        _update_state(
            pod_status="Healthy",
            memory_readings=payload.memory_readings,
            prediction_seconds=None,
            badge_type=None,
            diagnosis=result["diagnosis"],
            confidence=None,
            kubectl_command=None,
            memory_hit=False,
        )
        return {"source": "prediction", "alert": False, "result": current_state}


@app.get("/system-status")
def system_status():
    """
    Returns the current pod status, memory readings, diagnosis, confidence, etc.
    Person C's dashboard polls this every 2 seconds.
    """
    return current_state


@app.post("/execute")
def execute_command(payload: ExecutePayload):
    """
    Execute an approved kubectl command.
    Person C's Approve button calls this.
    """
    # Safety: only allow whitelisted command prefixes
    allowed_prefixes = ["kubectl delete pod", "kubectl rollout restart", "kubectl scale"]
    if not any(payload.kubectl_command.startswith(prefix) for prefix in allowed_prefixes):
        raise HTTPException(
            status_code=400,
            detail=f"Command not allowed. Must start with one of: {allowed_prefixes}",
        )

    # MOCK — replace Day 5 with actual K8s executor call
    # For now, extract pod name and namespace from the command
    result = restart_pod("mock-pod", "default")

    # Store outcome in memory
    if current_state["diagnosis"]:
        store_outcome(
            failure_type=current_state.get("badge_type", "unknown"),
            fix=payload.kubectl_command,
            success=True,
        )

    # Reset state after successful execution
    _update_state(
        pod_status="Healthy",
        memory_readings=[],
        prediction_seconds=None,
        badge_type=None,
        diagnosis=f"Fix applied: {payload.kubectl_command}",
        confidence=None,
        kubectl_command=None,
        memory_hit=False,
    )

    return {"status": "executed", "command": payload.kubectl_command, "result": result}


@app.get("/incident-history")
def incident_history():
    """
    Returns past incidents with fix outcomes and confidence scores.
    Person D builds the real implementation — this is a mock for Day 1.
    """
    # MOCK — replace Day 5 with: from memory.memory import get_history
    return {
        "incidents": [
            {
                "id": 1,
                "failure_type": "OOMKilled",
                "signature_matched": "OOMKilled",
                "fix_applied": "kubectl delete pod leaky-app-7x -n default",
                "success": True,
                "confidence": 0.99,
                "count": 3,
                "last_seen": "2025-03-09T03:42:11",
            }
        ]
    }


# ── Internal Helpers ──


def _update_state(**kwargs):
    """Update the shared in-memory state dict."""
    for key, value in kwargs.items():
        if key in current_state:
            current_state[key] = value
