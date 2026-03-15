from fastapi import FastAPI
from pydantic import BaseModel
from infrastructure.k8s_executor import restart_pod, get_pod_status, list_pods

app = FastAPI()

class ExecuteRequest(BaseModel):
    pod_name: str
    namespace: str = "default"

class ExecuteCommand(BaseModel):
    kubectl_command: str  # Example: "kubectl delete pod leaky-pod -n default"

@app.get("/health")
def health():
    """Simple check to confirm API is running."""
    return {"status": "ok"}

@app.get("/system-status")
def system_status():
    """
    Dashboard polls this periodically.
    Returns current pod health for the dashboard.
    """
    status = get_pod_status("leaky-pod")
    pods = list_pods()
    
    return {
        "pod_status": status["phase"],
        "last_reason": status["last_reason"],
        "restart_count": status["restart_count"],
        "all_pods": pods
    }

@app.post("/execute")
def execute(request: ExecuteRequest):
    """
    Restart a pod through the Kubernetes executor.
    """
    result = restart_pod(
        pod_name=request.pod_name,
        namespace=request.namespace
    )
    return result