"""Mock Prometheus server for local polling tests."""
from fastapi import FastAPI
import uvicorn
import time

app = FastAPI()

# Simulate a steadily leaking pod over time.
START_TIME = time.time()
POD_NAME = "test-leaky-pod-1"
START_MB = 120
GROWTH_RATE_MB_PER_SEC = 2.5

@app.get("/api/v1/query")
def mock_prometheus_query(query: str):
    elapsed = time.time() - START_TIME
    
    if "container_memory_working_set_bytes" in query:
        # Return a monotonically increasing memory series.
        current_mb = START_MB + (elapsed * GROWTH_RATE_MB_PER_SEC)

        return {
            "status": "success",
            "data": {
                "resultType": "vector",
                "result": [
                    {
                        "metric": {"pod": POD_NAME},
                        "value": [time.time(), str(current_mb)]
                    }
                ]
            }
        }
        
    elif "kube_pod_container_resource_limits_memory_bytes" in query:
        return {
            "status": "success",
            "data": {
                "resultType": "vector",
                "result": [
                    {
                        "metric": {"pod": POD_NAME},
                        "value": [time.time(), str(512 * 1024 * 1024)]
                    }
                ]
            }
        }
        
    return {"status": "success", "data": {"result": []}}

if __name__ == "__main__":
    print("Starting Mock Prometheus on port 9091...")
    uvicorn.run(app, host="0.0.0.0", port=9091)
