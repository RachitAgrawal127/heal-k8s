from kubernetes import client, config
import logging

# Sets up logging so we can see what's happening when functions run
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def load_kube_config():
    """
    Loads credentials to talk to Kubernetes.
    Tries in-cluster config first (if running inside a pod),
    falls back to local kubeconfig (our case — minikube on laptop).
    """
    try:
        config.load_incluster_config()
        logger.info("Loaded in-cluster config")
    except:
        config.load_kube_config()
        logger.info("Loaded local kubeconfig (minikube)")

def get_pod_status(pod_name: str, namespace: str = "default") -> dict:
    """
    Returns current status of a pod — phase, and whether it was OOMKilled.
    This is what the dashboard reads to show current pod health.
    """
    load_kube_config()
    v1 = client.CoreV1Api()  # V1 API handles core resources: pods, services, namespaces

    try:
        pod = v1.read_namespaced_pod(name=pod_name, namespace=namespace)
        
        phase = pod.status.phase  # "Running", "Pending", "Failed" etc.
        
        # Dig into container states to find OOMKilled
        last_reason = None
        restart_count = 0
        
        for cs in pod.status.container_statuses or []:
            restart_count = cs.restart_count
            if cs.last_state.terminated:
                last_reason = cs.last_state.terminated.reason  # "OOMKilled"
        
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
    Fixes a crashed pod by deleting it.
    Kubernetes automatically recreates it fresh from the original YAML spec.
    This is the standard K8s restart pattern — there's no 'restart' command.
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
    Person B's signature engine reads these to pattern-match failure types.
    e.g. logs containing 'OOMKilled' or 'ImagePullBackOff' trigger specific fixes.
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
        # Pod might be in a state where logs aren't accessible
        return f"Could not fetch logs: {e.reason}"


def list_pods(namespace: str = "default") -> list:
    """
    Returns all pods in a namespace with their current status.
    Useful for monitoring the full cluster health at a glance.
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