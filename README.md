# 🛠️ Heal-K8s
### Predictive + Self-Healing Kubernetes Agent

> *"It predicts crashes. It prevents them. If it misses — it fixes them. Gets smarter every time."*

[![Python](https://img.shields.io/badge/Python-3.10+-blue?style=flat-square&logo=python)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green?style=flat-square&logo=fastapi)](https://fastapi.tiangolo.com)
[![Kubernetes](https://img.shields.io/badge/Kubernetes-1.27+-blue?style=flat-square&logo=kubernetes)](https://kubernetes.io)
[![License](https://img.shields.io/badge/License-MIT-yellow?style=flat-square)](LICENSE)
[![Devpost](https://img.shields.io/badge/Devpost-Dev%20Season%20of%20Code-003E54?style=flat-square)](https://devpost.com)

---

## 📌 What Is Heal-K8s?

Heal-K8s is an **open-source, human-in-the-loop Kubernetes self-healing agent** that watches your cluster, predicts crashes before they happen, and fixes them with a single click — no 3 AM pages, no manual log reading.

Unlike enterprise tools like Komodor (paid, closed-source) or CLI tools like K8sGPT (no visual UI, no prediction), Heal-K8s gives every team the **complete experience — free and self-hostable.**

---

## 🚨 The Problem

Every team running Kubernetes has lived this:

```
3:00 AM — PagerDuty fires
Engineer wakes up, SSHs in
Reads 500 lines of logs
Figures out it's OOMKilled (again)
Types kubectl commands to fix it
Goes back to bed at 4:30 AM
```

This happens **multiple times per week** for common, diagnosable failures.  
Heal-K8s eliminates it.

---

## ✨ How It Works — Three Layers

```
Prometheus Metrics
       │
       ▼
┌─────────────────────────────────┐
│  Layer 1: Predictive Engine     │  ← Predicts crash BEFORE it happens
│  (Time-series rate-of-change)   │    No LLM. Pure math.
└────────────────┬────────────────┘
                 │ (if crash happens anyway)
                 ▼
┌─────────────────────────────────┐
│  Layer 2: Signature Engine      │  ← Matches known failure patterns
│  (Regex + rule dictionary)      │    No LLM. Instant. 95-99% accurate.
└────────────────┬────────────────┘
                 │ (if unknown failure)
                 ▼
┌─────────────────────────────────┐
│  Layer 3: LLM Fallback          │  ← Gemini last resort only
│  (Structured JSON output)       │    ~10% of real incidents
└────────────────┬────────────────┘
                 │
                 ▼
       Human Approval UI
    (Engineer clicks Approve)
                 │
                 ▼
    Kubernetes Python Client
      (Safe execution + log)
                 │
                 ▼
       Incident Memory
    (SQLite — learns over time)
```

---

## 🎬 Demo — Three Scenarios

| Scenario | What Happens |
|---|---|
| **1 — Prediction** | Memory leaks slowly → predictor confirms sustained growth → dashboard shows countdown → engineer approves → pod fixed **before crash** |
| **2 — Signature Fix** | Sudden OOMKill → signature engine identifies pattern instantly → no LLM call → 99% confidence → one click fix |
| **3 — False Positive** | GC spike detected → 45-second confirmation window NOT filled → no alert fires → system stays calm |

---

## 🏗️ Architecture

```
heal-k8s/
├── infrastructure/       # Person A — Minikube, Prometheus, K8s executor
│   ├── leaky_app.py      # Intentional memory leak for demo
│   ├── leak-pod.yaml     # Kubernetes pod manifest
│   ├── k8s_executor.py   # Kubernetes Python Client execution engine
│   ├── api.py            # FastAPI server for infrastructure endpoints
│   └── prometheus/
│       └── values.yaml   # Prometheus Helm config
│
├── backend/              # Person B — FastAPI + Engines
│   ├── main.py           # FastAPI app + all API endpoints
│   ├── predictor.py      # Time-series predictive engine
│   ├── signature_engine.py  # Regex-based failure signature matching
│   └── llm_fallback.py   # Gemini fallback for unknown failures
│
├── frontend/             # Person C — Dashboard
│   ├── index.html        # Main dashboard page
│   ├── app.js            # Real-time polling + Chart.js + approval UI
│   └── style.css         # Styling
│
├── memory/               # Person D — Incident Memory
│   ├── memory.py         # store, lookup, update_confidence
│   ├── models.py         # SQLite schema
│   └── incident_memory.db  # Auto-created on first run
│
├── tests/                # Person D — QA
│   ├── test_predictor.py
│   ├── test_signature.py
│   └── test_memory.py
│
├── requirements.txt
├── .env.example
└── README.md
```

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| Infrastructure | Minikube (local Kubernetes) |
| Monitoring | Prometheus via Helm |
| Backend | FastAPI (Python) |
| Predictive Engine | Pure Python — time-series rate-of-change math |
| Signature Engine | Python — regex + rule dictionary |
| LLM Fallback | Google Gemini 2.0 Flash — free tier |
| Incident Memory | SQLite (Python standard library) |
| Execution Engine | Kubernetes Python Client |
| Dashboard | Vanilla JS + Chart.js |

---

## ⚡ Quick Start

### Prerequisites

- Python 3.10+
- [Minikube](https://minikube.sigs.k8s.io/docs/start/)
- [kubectl](https://kubernetes.io/docs/tasks/tools/)
- [Helm](https://helm.sh/docs/intro/install/)
- A free Gemini API key from [aistudio.google.com](https://aistudio.google.com/app/apikey)

### 1. Clone the repo

```bash
git clone https://github.com/yourteam/heal-k8s.git
cd heal-k8s
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Set up environment variables

```bash
cp .env.example .env
# Edit .env and add your free Gemini API key:
# GEMINI_API_KEY=your_key_here
```

### 4. Start Minikube

```bash
minikube start
```

### 5. Install Prometheus via Helm

```bash
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update
helm install prometheus prometheus-community/kube-prometheus-stack --namespace monitoring --create-namespace
```

### 6. Deploy the leaky pod

```bash
kubectl apply -f infrastructure/leak-pod.yaml
```

### 7. Start the backend

```bash
uvicorn backend.main:app --reload --port 8000
```

### 8. Open the dashboard

```bash
# Just open it manually in Chrome
open frontend/index.html
```

---

## 🧪 Testing the Golden Loop (Without Prometheus)

If Prometheus is not configured yet, you can test the **full AI agent workflow** with a single curl command:

```bash
# Trigger a fake OOMKilled alert
curl -X POST http://localhost:8000/trigger-fake-alert \
  -H "Content-Type: application/json" \
  -d '{
    "pod_name": "leaky-app-7x",
    "namespace": "default",
    "logs": "OOMKilled: container exceeded memory limit",
    "metrics": {"memory_usage": 0.95, "restart_count": 0}
  }'
```

```bash
# Trigger a fake prediction alert (before crash)
curl -X POST http://localhost:8000/trigger-fake-prediction \
  -H "Content-Type: application/json" \
  -d '{
    "pod_name": "leaky-app-7x",
    "namespace": "default",
    "memory_readings": [120, 145, 178, 210, 255, 301, 355, 410],
    "memory_limit_mb": 512
  }'
```

---

## 🔌 Infrastructure API (Person A)

The infrastructure exposes its own FastAPI server for direct K8s operations:

```bash
python -m uvicorn infrastructure.api:app --reload --port 8001
```

| Endpoint | Method | Description |
|---|---|---|
| `/health` | GET | Confirms the API is running |
| `/system-status` | GET | Returns current pod health — phase, last_reason, restart_count |
| `/execute` | POST | Restarts a pod directly by name |

**K8s Executor functions available for import:**
```python
from infrastructure.k8s_executor import restart_pod, get_pod_status, get_pod_logs, list_pods

get_pod_status(pod_name, namespace)   # Returns phase, last_reason, restart_count
restart_pod(pod_name, namespace)      # Deletes pod — K8s recreates it fresh
get_pod_logs(pod_name, namespace)     # Returns last 50 log lines
list_pods(namespace)                  # Returns all pods with health summary
```

---

## 📡 API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/trigger-alert` | POST | Receives Prometheus alert webhook |
| `/trigger-fake-alert` | POST | Manual test trigger (no Prometheus needed) |
| `/trigger-fake-prediction` | POST | Manual prediction test |
| `/system-status` | GET | Current pod status, memory readings, diagnosis, confidence |
| `/execute` | POST | Execute an approved kubectl command |
| `/incident-history` | GET | Past incidents with fix outcomes and confidence scores |

### `/system-status` Response Shape

```json
{
  "pod_status": "Warning",
  "memory_readings": [120, 145, 178, 210, 255, 301],
  "prediction_seconds": 74,
  "badge_type": "prediction",
  "diagnosis": "Sustained memory growth detected — OOMKill predicted in 74 seconds",
  "confidence": 0.91,
  "kubectl_command": "kubectl delete pod leaky-app-7x -n default",
  "memory_hit": false
}
```

`badge_type` values: `"prediction"` | `"signature"` | `"memory_hit"` | `"llm_fallback"`

---

## 🔍 Signature Engine — Supported Failure Types

| Failure | Log Pattern Matched | Confidence |
|---|---|---|
| `OOMKilled` | `OOMKilled`, `Out of memory`, `Killed process` | 99% |
| `CrashLoopBackOff` | `CrashLoopBackOff`, `Back-off restarting` | 95% |
| `ImagePullBackOff` | `ImagePullBackOff`, `ErrImagePull` | 99% |
| `PodPending` | `Insufficient memory`, `Unschedulable` | 90% |
| `Unknown` | No pattern matched → LLM Fallback triggered | Varies |

---

## 🔮 Predictive Engine — How False Positives Are Prevented

The engine requires **all three conditions** before firing an alert:

```
✅ Growth sustained for 45+ seconds (not a spike)
✅ Growth rate above 0.5 MB/s minimum
✅ At least 6 consecutive rising readings
```

A Python garbage collector spike lasts 2-3 seconds and fails condition 1.  
A real memory leak is sustained and passes all three.  
This eliminates ~90% of false positives with zero ML models.

---

## 💾 Incident Memory

Every approved fix is stored in SQLite:

```python
{
  "id": 1,
  "failure_type": "OOMKilled",
  "signature_matched": "OOMKilled",
  "fix_applied": "kubectl delete pod leaky-app-7x -n default",
  "success": True,
  "confidence": 0.95,
  "count": 4,
  "last_seen": "2025-03-09T03:42:11"
}
```

On repeat failures — memory is checked **before** the signature engine runs.  
At 95%+ confidence, the fix is suggested instantly with a green **Memory Hit** badge.

---

## 🔐 Safety Design

- The agent **never executes without human approval** — every action requires one click
- Only **pre-validated kubectl commands** are ever executed — no arbitrary code
- Every action is **fully logged** with timestamp, command, pod name, and outcome
- A **read-only diagnostic mode** is available — diagnose without any execution permissions
- The LLM only outputs structured JSON — **prevents hallucinated commands**

---

## 🆚 How We Compare

| Feature | Komodor | K8sGPT | kagent | Heal-K8s |
|---|---|---|---|---|
| Predictive crash prevention | ✅ | ❌ | ❌ | ✅ |
| Visual real-time dashboard | ✅ | ❌ | Basic | ✅ |
| Human approval UI | ✅ | ❌ | ❌ | ✅ |
| Incident memory | ✅ | ❌ | ❌ | ✅ |
| Free & open source | ❌ | ✅ | ✅ | ✅ |
| Works in 15 minutes | ❌ | Moderate | ❌ | ✅ |

---

## 🏃 Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_predictor.py -v
pytest tests/test_signature.py -v
pytest tests/test_memory.py -v
```

---

## 🔧 Troubleshooting

**Minikube won't start**  
Make sure Docker Desktop is fully running first, then retry `minikube start --driver=docker`.

**Pod not found error from /execute**  
The pod is in CrashLoopBackOff with a long backoff delay. Delete and redeploy:
```bash
kubectl delete pod leaky-pod
kubectl apply -f infrastructure/leak-pod.yaml
```

**uvicorn not recognized on Windows**  
Use `python -m uvicorn` instead of just `uvicorn`.

**Prometheus pods stuck in ContainerCreating**  
Wait 3-5 minutes — they're pulling Docker images. Run `kubectl --namespace monitoring get pods -w` to watch progress.

---

## 🗺️ Roadmap

- [ ] AWS CloudWatch + Azure Monitor support
- [ ] Slack / PagerDuty approval notifications
- [ ] Multi-cluster support with RBAC
- [ ] Support for additional failure types (CPU throttling, disk pressure)
- [ ] Predictive model trained on historical incident data

---

## 📄 License

MIT License — free to use, modify, and deploy.

---

<p align="center">
  <i>Built for the engineers who deserve to sleep through the night. 🌙</i>
</p>
