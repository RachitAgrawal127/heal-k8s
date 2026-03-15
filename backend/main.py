
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import time
import asyncio
import httpx
import os
from collections import defaultdict

from backend.predictor import PredictiveEngine
from backend.signature_engine import SignatureEngine

# ── Kubernetes executor ──
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

# ── Incident memory module ──
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

# Allow the static dashboard to call the API when opened directly in the browser.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

PROMETHEUS_URL = os.getenv("PROMETHEUS_URL", "http://localhost:9090")
ENABLE_PROMETHEUS_POLLING = os.getenv("ENABLE_PROMETHEUS_POLLING", "false").lower() == "true"
ENABLE_K8S_EXECUTION = os.getenv("ENABLE_K8S_EXECUTION", "false").lower() == "true"
pod_memory_history = defaultdict(list)
MAX_HISTORY_LEN = 30  # Keep the most recent five minutes of samples.


predictor = PredictiveEngine()
signature_engine = SignatureEngine()

# ── Shared in-memory dashboard state ──
current_state = {
    "pod_status": "Healthy",
    "memory_readings": [],
    "prediction_seconds": None,
    "badge_type": None,
    "failure_type": None,   # Canonical failure label used for memory lookups.
    "diagnosis": None,
    "confidence": None,
    "kubectl_command": None,
    "memory_hit": False,
}


# ── Request / response models ──


class AlertPayload(BaseModel):
    pod_name: str
    namespace: str = "default"
    logs: str
    metrics: dict  # Example: {"memory_usage": 0.95, "restart_count": 0}


class PredictionPayload(BaseModel):
    pod_name: str
    namespace: str = "default"
    memory_readings: list[float]  # Example: [120, 145, 178, 210, 255, 301, 355, 410]
    memory_limit_mb: float  # Example: 512


class ExecutePayload(BaseModel):
    kubectl_command: str


# ── Background polling loop ──

async def prometheus_polling_loop():
    """
    Poll Prometheus on a fixed interval and feed samples into the predictive engine.
    """
    print(f"Starting Prometheus polling loop against {PROMETHEUS_URL}...")

    # Give the application a brief startup window before polling begins.
    await asyncio.sleep(5)
    
    async with httpx.AsyncClient(timeout=5.0) as client:
        while True:
            try:
                # Query current per-pod memory usage in megabytes.
                query_usage = 'sum(container_memory_working_set_bytes{namespace="default", pod!=""}) by (pod) / 1024 / 1024'
                res_usage = await client.get(f"{PROMETHEUS_URL}/api/v1/query", params={"query": query_usage})
                res_usage.raise_for_status()
                usage_data = res_usage.json()

                # Query configured per-pod memory limits in megabytes.
                query_limits = 'sum(kube_pod_container_resource_limits_memory_bytes{namespace="default", pod!=""}) by (pod) / 1024 / 1024'
                res_limits = await client.get(f"{PROMETHEUS_URL}/api/v1/query", params={"query": query_limits})
                # Fall back to a default limit when no explicit limit is available.
                limit_data = res_limits.json() if res_limits.status_code == 200 else {}

                # Build a pod-to-limit lookup for the current polling interval.
                limits_lookup = {}
                if 'data' in limit_data and 'result' in limit_data['data']:
                    for item in limit_data['data']['result']:
                        pod = item['metric'].get('pod')
                        val = float(item['value'][1])
                        if pod and val > 0:
                            limits_lookup[pod] = val

                # Process memory samples for each pod returned by Prometheus.
                if 'data' in usage_data and 'result' in usage_data['data']:
                    for item in usage_data['data']['result']:
                        pod_name = item['metric'].get('pod')
                        if not pod_name:
                            continue
                            
                        mem_mb = float(item['value'][1])
                        limit_mb = limits_lookup.get(pod_name, 512.0)

                        # Append the latest sample to the rolling history.
                        pod_memory_history[pod_name].append(mem_mb)
                        if len(pod_memory_history[pod_name]) > MAX_HISTORY_LEN:
                            pod_memory_history[pod_name].pop(0)

                        # Wait until the rolling window is large enough for analysis.
                        if len(pod_memory_history[pod_name]) < predictor.MIN_CONSECUTIVE_RISES:
                            continue

                        # Run the predictive engine on the current rolling window.
                        result = predictor.analyze(pod_memory_history[pod_name], limit_mb)
                        
                        if result["alert"]:
                            print(f"[PREDICTION ALERT] Pod {pod_name} is leaking: {result['diagnosis']}")
                            kubectl_cmd = f"kubectl delete pod {pod_name} -n default"
                            # Update dashboard state with the predicted incident.
                            _update_state(
                                pod_status="Warning",
                                memory_readings=list(pod_memory_history[pod_name]),
                                prediction_seconds=result["predicted_seconds_to_oom"],
                                badge_type="prediction",
                                diagnosis=result["diagnosis"],
                                confidence=result["confidence"],
                                kubectl_command=kubectl_cmd,
                                memory_hit=False,
                            )
                        else:
                            # Keep live memory readings visible during nominal operation.
                            _update_state(
                                pod_status="Healthy",
                                memory_readings=list(pod_memory_history[pod_name]),
                                prediction_seconds=None,
                                badge_type=None,
                                diagnosis="System nominal. Monitoring memory.",
                                confidence=None,
                                kubectl_command=None,
                                memory_hit=False,
                            )
                
            except Exception as e:
                print(f"[Prometheus Polling] Error: {e}")
            
            # Match the polling interval to the configured sample interval.
            await asyncio.sleep(predictor.SAMPLE_INTERVAL_SECONDS)


@app.on_event("startup")
async def startup_event():
    if ENABLE_PROMETHEUS_POLLING:
        asyncio.create_task(prometheus_polling_loop())
    else:
        print("Prometheus polling disabled. Set ENABLE_PROMETHEUS_POLLING=true to enable live polling.")

# ── API endpoints ──

@app.get("/")
def root():
    return {"service": "Heal-K8s", "status": "running", "version": "0.1.0"}


@app.post("/trigger-alert")
def trigger_alert(payload: AlertPayload):
    """
    Receives a real Prometheus alert webhook (or manual trigger).
    Runs the full diagnosis pipeline:
            1. Check incident memory for a known fix
            2. Match the incident against the signature engine
            3. Fall back to Gemini for unknown failures
    """
        # Resolve the canonical failure label before looking up prior incidents.
    sig_result = signature_engine.diagnose(
        payload.logs, payload.metrics,
        pod_name=payload.pod_name, namespace=payload.namespace
    )
    failure_type = sig_result["failure_type"]

    memory_result = lookup_pattern(failure_type)
    if memory_result and memory_result.get("confidence", 0) >= 0.95 and failure_type != "unknown":
        _update_state(
            pod_status="Warning",
            badge_type="memory_hit",
            failure_type=failure_type,
            diagnosis=f"Memory hit: {memory_result['fix']} (confidence {memory_result['confidence']:.0%})",
            confidence=memory_result["confidence"],
            kubectl_command=memory_result["fix"],
            memory_hit=True,
        )
        return {"source": "memory", "result": current_state}

    # Return the signature engine result for known failure patterns.
    if failure_type != "unknown":
        _update_state(
            pod_status="Warning",
            badge_type="signature",
            failure_type=failure_type,
            diagnosis=sig_result["diagnosis"],
            confidence=sig_result["confidence"],
            kubectl_command=sig_result["kubectl_command"],
            memory_hit=False,
        )
        return {"source": "signature", "result": current_state}

    # Use the LLM fallback only when no known pattern matches.
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
        failure_type=llm_result.get("failure_type", "unknown"),
        diagnosis=llm_result["diagnosis"],
        confidence=llm_result["confidence"],
        kubectl_command=llm_result["kubectl_command"],
        memory_hit=False,
    )
    return {"source": "llm_fallback", "result": current_state}


@app.post("/trigger-fake-alert")
def trigger_fake_alert(payload: AlertPayload):
    """
    Manual alert trigger that mirrors the live alert path.
    """
    return trigger_alert(payload)


@app.post("/trigger-fake-prediction")
def trigger_fake_prediction(payload: PredictionPayload):
    """
    Manual prediction trigger for the predictive engine.
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
    Dashboard polls this periodically.
    """
    return current_state


@app.post("/execute")
def execute_command(payload: ExecutePayload):
    """
    Execute an approved kubectl command.
    Uses restart_pod() from infrastructure.k8s_executor.
    """
    # Restrict execution to a small set of approved kubectl command prefixes.
    allowed_prefixes = ["kubectl delete pod", "kubectl rollout restart", "kubectl scale"]
    if not any(payload.kubectl_command.startswith(prefix) for prefix in allowed_prefixes):
        raise HTTPException(
            status_code=400,
            detail=f"Command not allowed. Must start with one of: {allowed_prefixes}",
        )

    # Extract pod name and namespace from the command string when present.
    pod_name = "leaky-pod"
    namespace = "default"
    try:
        parts = payload.kubectl_command.split()
        if "-n" in parts:
            namespace = parts[parts.index("-n") + 1]
        # The pod name is the token after the "pod" keyword.
        if "pod" in parts:
            pod_name = parts[parts.index("pod") + 1]
    except (ValueError, IndexError):
        pass

    if not ENABLE_K8S_EXECUTION:
        result = {
            "status": "mock_success",
            "message": "Demo mode: fix approved and simulated successfully.",
        }
    else:
        # Attempt real execution when Kubernetes access is enabled.
        try:
            result = restart_pod(pod_name, namespace)
        except Exception as e:
            result = {
                "status": "k8s_unavailable",
                "message": f"Kubernetes not reachable — is Minikube running? Error: {str(e)[:80]}",
            }

    # Persist the outcome under the canonical failure label for future lookups.
    if current_state["diagnosis"]:
        store_outcome(
            failure_type=current_state.get("failure_type") or current_state.get("badge_type") or "unknown",
            fix=payload.kubectl_command,
            # Treat demo-mode execution as a successful outcome for memory learning.
            success=result.get("status") in ("success", "mock_success"),
        )

    # Clear the active incident from the dashboard after execution completes.
    _update_state(
        pod_status="Healthy",
        memory_readings=[],
        prediction_seconds=None,
        badge_type=None,
        failure_type=None,
        diagnosis=None,
        confidence=None,
        kubectl_command=None,
        memory_hit=False,
    )

    return {"status": "executed", "command": payload.kubectl_command, "result": result, "k8s_available": K8S_AVAILABLE}


@app.get("/incident-history")
def incident_history():
    """
    Returns past incidents with fix outcomes and confidence scores.
    Uses get_all_incidents() from memory.memory.
    """
    return {"incidents": get_all_incidents()}


# ── Internal helpers ──


def _update_state(**kwargs):
    """Update the shared in-memory state dict."""
    for key, value in kwargs.items():
        if key in current_state:
            current_state[key] = value
