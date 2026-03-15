# Heal-K8s
### Predictive + Self-Healing Kubernetes Incident Response

> 3:00 AM. PagerDuty fires. Same OOM incident. Same manual fix.
>
> Heal-K8s predicts failures before impact, proposes remediation with approval, and learns from each successful recovery.

[![Python](https://img.shields.io/badge/Python-3.10+-blue?style=flat-square&logo=python)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green?style=flat-square&logo=fastapi)](https://fastapi.tiangolo.com)
[![Kubernetes](https://img.shields.io/badge/Kubernetes-1.27+-blue?style=flat-square&logo=kubernetes)](https://kubernetes.io)
[![License](https://img.shields.io/badge/License-MIT-yellow?style=flat-square)](LICENSE)

---

## Why this exists

Most incident tooling is reactive: it helps after failure.

Heal-K8s focuses on the full loop:
- **Predict** likely crashes before they happen
- **Diagnose** known failures instantly
- **Approve and execute** remediation safely
- **Learn** from outcomes to resolve repeats faster

This project is open-source, self-hostable, and designed for practical DevOps workflows.

---

## Core capabilities

1. **Predictive prevention (no LLM)**
   - Time-series engine detects sustained memory growth
   - OOM countdown is shown before crash
   - Reduces false positives via sustained-growth rules

2. **Signature diagnosis (no LLM)**
   - Regex + rule-based detection for common Kubernetes failures
   - Typical known-failure confidence: 95-99%

3. **LLM fallback (unknown only)**
   - Called only when no known signature matches
   - Returns structured diagnosis and command recommendation

4. **Human-in-the-loop execution**
   - Remediation is approval-gated from the dashboard
   - Backend validates command prefix before execution

5. **Incident memory**
   - Stores outcomes in SQLite
   - Repeated incidents can return a high-confidence memory hit

---

## Architecture

```
Prometheus metrics / alerts
          │
          ▼
  Predictive Engine (time-series)
          │
          ├─ known pattern? ──► Signature Engine
          │                          │
          │                          └─ no match ─► LLM Fallback
          ▼
     Human Approval UI
          │
          ▼
 Kubernetes Executor (safe action)
          │
          ▼
    Incident Memory (SQLite)
```

---

## Demo flow used in submission

- **False positive rejection**: transient spike does not trigger incident
- **Prediction before crash**: warning with countdown and pre-failure remediation
- **Live telemetry proof**: short Prometheus clip
- **LLM fallback**: unknown incident path
- **Signature fix**: known OOM path
- **Memory hit**: repeated known incident resolved faster

---

## Project structure

```
heal-k8s/
├── backend/
│   ├── main.py
│   ├── predictor.py
│   ├── signature_engine.py
│   └── llm_fallback.py
├── frontend/
│   ├── index.html
│   ├── app.js
│   └── style.css
├── infrastructure/
│   ├── api.py
│   ├── k8s_executor.py
│   ├── leak-pod.yaml
│   └── leaky_app.py
├── memory/
│   ├── memory.py
│   └── models.py
├── tests/
│   ├── test_predictor.py
│   ├── test_signature.py
│   └── test_memory.py
├── mock_prometheus.py
├── requirements.txt
├── .env.example
└── README.md
```

---

## Quick start (recommended demo mode)

This path works without live Prometheus polling and is the fastest way to run the full loop.

### Prerequisites

- Python 3.10+
- Optional: Minikube + kubectl (only required for real cluster execution)
- Optional: Gemini API key (for non-mock LLM fallback)

### 1) Install dependencies

```bash
pip install -r requirements.txt
```

### 2) Configure environment

```bash
cp .env.example .env
```

Edit `.env`:

```env
GEMINI_API_KEY=your_key_here
ENABLE_PROMETHEUS_POLLING=false
ENABLE_K8S_EXECUTION=false
PROMETHEUS_URL=http://localhost:9090
```

### 3) Start backend

```bash
uvicorn backend.main:app --reload --port 8000
```

### 4) Open dashboard

Open `frontend/index.html` in your browser.

### 5) Trigger incidents manually

Use `POST /trigger-fake-prediction` and `POST /trigger-fake-alert` to run scenarios.

---

## Real telemetry mode (Prometheus polling)

Enable only for live telemetry capture or full cluster demos.

```env
ENABLE_PROMETHEUS_POLLING=true
PROMETHEUS_URL=http://localhost:9090
```

Port-forward Prometheus:

```bash
kubectl port-forward svc/prometheus-kube-prometheus-prometheus 9090:9090 -n monitoring
```

Restart backend after changing env values.

---

## API reference

### Core endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/trigger-alert` | POST | Ingest a real alert payload |
| `/trigger-fake-alert` | POST | Manual alert trigger for demos/tests |
| `/trigger-fake-prediction` | POST | Manual prediction trigger |
| `/system-status` | GET | Dashboard state payload |
| `/execute` | POST | Execute an approved remediation command |
| `/incident-history` | GET | Historical incident outcomes |

### Example payload: `/trigger-fake-prediction`

```json
{
  "pod_name": "leaky-pod",
  "namespace": "default",
  "memory_readings": [120, 145, 178, 210, 255, 301, 355, 410],
  "memory_limit_mb": 512
}
```

### Example payload: `/trigger-fake-alert`

```json
{
  "pod_name": "leaky-pod",
  "namespace": "default",
  "logs": "OOMKilled: container exceeded memory limit",
  "metrics": {"memory_usage": 0.98, "restart_count": 1}
}
```

---

## Signature coverage

Known failure classes currently supported:
- `OOMKilled`
- `CrashLoopBackOff`
- `ImagePullBackOff`
- `PodPending` / unschedulable

Unknown incidents route to LLM fallback.

---

## Safety model

- Execution is **approval-gated**
- Backend validates command prefixes before execution
- Demo mode supports safe simulated execution
- Incident outcomes are recorded for confidence-based memory reuse

---

## Testing

Run full test suite:

```bash
pytest tests/ -v
```

Run targeted suites:

```bash
pytest tests/test_predictor.py -v
pytest tests/test_signature.py -v
pytest tests/test_memory.py -v
```

---

## Troubleshooting

### `kubectl ... connectex` / API refused

Your kube context is likely stale or Minikube is down.

```bash
minikube start
minikube update-context
kubectl cluster-info
```

### Prometheus port-forward fails

Verify monitoring namespace resources:

```bash
kubectl get pods -n monitoring
```

Then retry port-forward.

### Dashboard shows no live telemetry

- Ensure backend restarted after env changes
- Confirm `ENABLE_PROMETHEUS_POLLING=true`
- Confirm Prometheus port-forward is active

---

## Roadmap

- More failure signatures
- Multi-cluster support
- Alert integrations (Slack/PagerDuty)
- Expanded telemetry sources

---

## License

MIT

---

If this project helps your team, consider starring the repository.