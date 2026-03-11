# Heal-K8s — Infrastructure (Person A)

This folder contains everything needed to run a local Kubernetes cluster, simulate a crashing pod, and execute fixes programmatically.

---

## What This Does

- Spins up a local Kubernetes cluster using Minikube
- Deploys a pod that leaks memory and crashes (simulates a real OOMKilled failure)
- Exposes a FastAPI server with endpoints the dashboard and backend can call to read pod status and execute fixes

---

## Prerequisites

Make sure these are installed on your machine before anything else:

| Tool | Version Used | Install |
|------|-------------|---------|
| Docker Desktop | 29.x | https://www.docker.com/products/docker-desktop |
| Minikube | v1.37+ | https://minikube.sigs.k8s.io/docs/start |
| kubectl | v1.34+ | https://kubernetes.io/docs/tasks/tools |
| Helm | v4.x | https://helm.sh/docs/intro/install |
| Python | 3.11+ | https://www.python.org/downloads |

---

## Setup — Run This Once

### 1. Start Docker Desktop
Open Docker Desktop and wait for it to fully load (whale icon in taskbar stops animating).

### 2. Start Minikube
```bash
minikube start --driver=docker
```
Verify it's running:
```bash
kubectl get nodes
# Expected: minikube   Ready   control-plane
```

### 3. Install Python dependencies
```bash
pip install -r requirements.txt
```

### 4. Install Prometheus (monitoring)
```bash
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update
helm install prometheus prometheus-community/kube-prometheus-stack \
  --namespace monitoring \
  --create-namespace
```
Wait for all pods to be Running:
```bash
kubectl --namespace monitoring get pods -w
# Wait until all show Running
```

---

## Deploy the Leaky Pod

This pod leaks memory at ~5MB/second and crashes at 100MB (OOMKilled). It auto-restarts, simulating a real crash loop.

```bash
kubectl apply -f infrastructure/leak-pod.yaml
kubectl get pods -w
# You'll see: Running → OOMKilled → CrashLoopBackOff → Running (repeating)
```

To stop it:
```bash
kubectl delete pod leaky-pod
```

---

## Run the API Server

This exposes your Kubernetes executor over HTTP so the dashboard and backend can call it.

```bash
python -m uvicorn infrastructure.api:app --reload --port 8000
```

### Available Endpoints

#### `GET /health`
Confirms the API is running.
```json
{"status": "ok"}
```

#### `GET /system-status`
Returns current pod health. Person C polls this every 2 seconds.
```json
{
  "pod_status": "Running",
  "last_reason": "OOMKilled",
  "restart_count": 3,
  "all_pods": [{"name": "leaky-pod", "phase": "Running", "restart_count": 3}]
}
```

#### `POST /execute`
Restarts a pod. Called when engineer clicks Approve on the dashboard.

Request body:
```json
{"pod_name": "leaky-pod", "namespace": "default"}
```
Response:
```json
{
  "status": "success",
  "action": "Deleted leaky-pod",
  "message": "Pod will be recreated automatically by Kubernetes"
}
```

---

## View Metrics in Prometheus (Optional)

```bash
kubectl port-forward -n monitoring svc/prometheus-kube-prometheus-prometheus 9090:9090
```
Open http://localhost:9090 and query:
```
container_memory_working_set_bytes{pod="leaky-pod"}
```
Switch to Graph tab to see the sawtooth crash pattern.

---

## File Structure

```
infrastructure/
├── __init__.py          # Makes this a Python package — required for imports
├── api.py               # FastAPI server — /health, /system-status, /execute
├── k8s_executor.py      # Kubernetes Python client — reads and fixes pods
├── leaky_app.py         # Memory leak simulator (for local testing only)
└── leak-pod.yaml        # Kubernetes blueprint for the leaky pod
```

---

## How Other Team Members Use This

### Person B (Backend)
Import the executor directly into your FastAPI backend:
```python
from infrastructure.k8s_executor import restart_pod, get_pod_status, get_pod_logs, list_pods
```

Available functions:
```python
get_pod_status(pod_name, namespace)   # Returns phase, last_reason, restart_count
restart_pod(pod_name, namespace)      # Deletes pod — K8s recreates it fresh
get_pod_logs(pod_name, namespace)     # Returns last 50 log lines
list_pods(namespace)                  # Returns all pods with health summary
```

### Person C (Frontend)
Poll `GET /system-status` every 2 seconds for live pod data.
Call `POST /execute` with `{"pod_name": "leaky-pod", "namespace": "default"}` when Approve is clicked.

### Person D (Memory/QA)
The leaky pod will be running and crashing continuously — use it for end-to-end testing of the memory engine and confidence scoring.

---

## Troubleshooting

**Minikube won't start**
Make sure Docker Desktop is fully running first, then retry `minikube start --driver=docker`.

**Pod not found error from /execute**
The pod is in CrashLoopBackOff with a long backoff delay. Delete and redeploy:
```bash
kubectl delete pod leaky-pod
kubectl apply -f infrastructure/leak-pod.yaml
```

**uvicorn not recognized**
Use `python -m uvicorn` instead of just `uvicorn` on Windows.

**Prometheus pods stuck in ContainerCreating**
Wait 3-5 minutes — they're pulling Docker images. Run `kubectl --namespace monitoring get pods -w` to watch progress.