"""
Heal-K8s Backend — FastAPI Application
Person B — Backend Lead

All API contract endpoints are defined here.
Person A's infrastructure.k8s_executor is now wired in (real K8s execution).
Person D's memory.memory module is now wired in (real incident memory).
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import time

from backend.predictor import PredictiveEngine
from backend.signature_engine import SignatureEngine

# ── Person A's real K8s executor (wired in) ──
try:
    from infrastructure.k8s_executor import restart_pod, get_pod_logs, get_pod_status
    K8S_AVAILABLE = True
except Exception:
    K8S_AVAILABLE = False
    def restart_pod(pod_name: str, namespace: str = "default") -> dict:
        return {"status": "mock_success", "message": f"K8s not available — mock restart of {pod_name}"}
    def get_pod_logs(pod_name: str, namespace: str = "default", tail: int = 50) -> str:
        return "K8s not available — no real logs"
    def get_pod_status(pod_name: str, namespace: str = "default") -> dict:
        return {"phase": "Unknown", "last_reason": None, "restart_count": 0}

# ── Person D's real memory module (wired in) ──
try:
    from memory.memory import lookup_pattern, store_outcome, get_all_incidents
except Exception:
    def lookup_pattern(failure_type: str) -> Optional[dict]:
        return None
    def store_outcome(failure_type: str, fix: str, success: bool) -> None:
        pass
    def get_all_incidents() -> list:
        return []

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
      1. Check incident memory for known fix (Person D's module)
      2. Run signature engine for pattern match (Person B)
      3. Fall back to LLM via Gemini for unknown failures (Person B)
    """
    # Step 1 — Check memory for known past fix (Person D)
    # First run the signature engine to get the failure_type label for the memory lookup
    sig_result = signature_engine.diagnose(
        payload.logs, payload.metrics,
        pod_name=payload.pod_name, namespace=payload.namespace
    )
    failure_type = sig_result["failure_type"]  # e.g. "OOMKilled" or "unknown"

    memory_result = lookup_pattern(failure_type)
    if memory_result and memory_result.get("confidence", 0) >= 0.95 and failure_type != "unknown":
        _update_state(
            pod_status="Warning",
            badge_type="memory_hit",
            diagnosis=f"Memory hit: {memory_result['fix']} (confidence {memory_result['confidence']:.0%})",
            confidence=memory_result["confidence"],
            kubectl_command=memory_result["fix"],
            memory_hit=True,
        )
        return {"source": "memory", "result": current_state}

    # Step 2 — Signature engine matched a known pattern
    if failure_type != "unknown":
        _update_state(
            pod_status="Warning",
            badge_type="signature",
            diagnosis=sig_result["diagnosis"],
            confidence=sig_result["confidence"],
            kubectl_command=sig_result["kubectl_command"],
            memory_hit=False,
        )
        return {"source": "signature", "result": current_state}

    # Step 3 — Unknown failure → LLM fallback via Gemini
    from backend.llm_fallback import LLMFallback
    llm = LLMFallback()
    llm_result = llm.diagnose(
        pod_name=payload.pod_name,
        namespace=payload.namespace,
        logs=payload.logs,
        metrics=payload.metrics,
    )
    _update_state(
        pod_status="Critical",
        badge_type="llm_fallback",
        diagnosis=llm_result["diagnosis"],
        confidence=llm_result["confidence"],
        kubectl_command=llm_result["kubectl_command"],
        memory_hit=False,
    )
    return {"source": "llm_fallback", "result": current_state}


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
    Uses Person A's real restart_pod() from infrastructure.k8s_executor.
    """
    # Safety: only allow whitelisted command prefixes
    allowed_prefixes = ["kubectl delete pod", "kubectl rollout restart", "kubectl scale"]
    if not any(payload.kubectl_command.startswith(prefix) for prefix in allowed_prefixes):
        raise HTTPException(
            status_code=400,
            detail=f"Command not allowed. Must start with one of: {allowed_prefixes}",
        )

    # Parse pod name and namespace from the kubectl command string
    # Expected format: "kubectl delete pod <pod-name> -n <namespace>"
    pod_name = "leaky-pod"  # safe default
    namespace = "default"
    try:
        parts = payload.kubectl_command.split()
        if "-n" in parts:
            namespace = parts[parts.index("-n") + 1]
        # pod name is the token after "pod" keyword
        if "pod" in parts:
            pod_name = parts[parts.index("pod") + 1]
    except (ValueError, IndexError):
        pass  # use defaults if parsing fails

    # Call Person A's real K8s executor
    # Gracefully handles the case when Minikube is not running
    try:
        result = restart_pod(pod_name, namespace)
    except Exception as e:
        result = {
            "status": "k8s_unavailable",
            "message": f"Kubernetes not reachable — is Minikube running? Error: {str(e)[:80]}",
        }

    # Store outcome in memory (Person D's module)
    if current_state["diagnosis"]:
        store_outcome(
            failure_type=current_state.get("badge_type") or "unknown",
            fix=payload.kubectl_command,
            success=result.get("status") == "success",
        )

    # Reset state after execution
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

    return {"status": "executed", "command": payload.kubectl_command, "result": result, "k8s_available": K8S_AVAILABLE}


@app.get("/incident-history")
def incident_history():
    """
    Returns past incidents with fix outcomes and confidence scores.
    Uses Person D's real get_all_incidents() from memory.memory.
    """
    return {"incidents": get_all_incidents()}


# ── Internal Helpers ──


def _update_state(**kwargs):
    """Update the shared in-memory state dict."""
    for key, value in kwargs.items():
        if key in current_state:
            current_state[key] = value
