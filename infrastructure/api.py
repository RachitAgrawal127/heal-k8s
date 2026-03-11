from fastapi import FastAPI
from pydantic import BaseModel
from infrastructure.k8s_executor import restart_pod, get_pod_status, list_pods

app = FastAPI()

# This defines the shape of the request body for /execute
class ExecuteRequest(BaseModel):
    pod_name: str
    namespace: str = "default"

class ExecuteCommand(BaseModel):
    kubectl_command: str  # e.g. "kubectl delete pod leaky-pod -n default"

@app.get("/health")
def health():
    """Simple check to confirm API is running."""
    return {"status": "ok"}

@app.get("/system-status")
def system_status():
    """
    Person C polls this every 2 seconds.
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
    Person C's Approve button calls this.
    Receives pod name, calls restart_pod(), returns result.
    """
    result = restart_pod(
        pod_name=request.pod_name,
        namespace=request.namespace
    )
    return result