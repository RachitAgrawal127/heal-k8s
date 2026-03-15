from kubernetes import client, config
import logging

# Configure module logging.
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def load_kube_config():
    """
    Load Kubernetes credentials.
    Try in-cluster configuration first, then fall back to the local kubeconfig.
    """
    try:
        config.load_incluster_config()
        logger.info("Loaded in-cluster config")
    except:
        config.load_kube_config()
        logger.info("Loaded local kubeconfig (minikube)")

def get_pod_status(pod_name: str, namespace: str = "default") -> dict:
    """
    Return the current pod phase, termination reason, and restart count.
    """
    load_kube_config()
    v1 = client.CoreV1Api()

    try:
        pod = v1.read_namespaced_pod(name=pod_name, namespace=namespace)
        
        phase = pod.status.phase

        # Inspect container state history for the most recent termination reason.
        last_reason = None
        restart_count = 0
        
        for cs in pod.status.container_statuses or []:
            restart_count = cs.restart_count
            if cs.last_state.terminated:
                last_reason = cs.last_state.terminated.reason
        
        return {
            "phase": phase,
            "last_reason": last_reason,
            "restart_count": restart_count
        }

    except client.exceptions.ApiException as e:
        if e.status == 404:
            return {"phase": "NotFound", "last_reason": None, "restart_count": 0}
        return {"phase": "Error", "error": str(e), "last_reason": None, "restart_count": 0}
    

def restart_pod(pod_name: str, namespace: str = "default") -> dict:
    """
    Delete a pod and rely on Kubernetes to recreate it.
    """
    load_kube_config()
    v1 = client.CoreV1Api()

    try:
        v1.delete_namespaced_pod(name=pod_name, namespace=namespace)
        
        logger.info(f"Deleted pod {pod_name} — Kubernetes will recreate it")
        
        return {
            "status": "success",
            "action": f"Deleted {pod_name}",
            "message": "Pod will be recreated automatically by Kubernetes"
        }

    except client.exceptions.ApiException as e:
        if e.status == 404:
            return {"status": "error", "message": f"Pod {pod_name} not found"}
        
        logger.error(f"Failed to delete pod: {e}")
        return {"status": "error", "message": str(e)}
    
def get_pod_logs(pod_name: str, namespace: str = "default", tail: int = 50) -> str:
    """
    Fetches the last N lines of logs from a pod.
    The signature engine uses these logs for failure classification.
    """
    load_kube_config()
    v1 = client.CoreV1Api()

    try:
        logs = v1.read_namespaced_pod_log(
            name=pod_name,
            namespace=namespace,
            tail_lines=tail
        )
        return logs if logs else "No logs available"

    except client.exceptions.ApiException as e:
        # Some pod states do not expose logs.
        return f"Could not fetch logs: {e.reason}"


def list_pods(namespace: str = "default") -> list:
    """
    Return all pods in a namespace with their current status.
    """
    load_kube_config()
    v1 = client.CoreV1Api()

    try:
        pods = v1.list_namespaced_pod(namespace=namespace)
        
        result = []
        for pod in pods.items:
            result.append({
                "name": pod.metadata.name,
                "phase": pod.status.phase,
                "restart_count": sum(
                    cs.restart_count 
                    for cs in (pod.status.container_statuses or [])
                )
            })
        return result

    except client.exceptions.ApiException as e:
        return [{"error": str(e)}]