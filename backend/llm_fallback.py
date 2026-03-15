

import os
import json
from dotenv import load_dotenv

load_dotenv()

# Structured fallback response for unknown incidents.

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

SYSTEM_PROMPT = """You are a Kubernetes cluster diagnostics expert.
You are given pod logs and metrics from a failing Kubernetes pod.
Your job is to:
1. Identify the root cause of the failure.
2. Suggest a safe kubectl command to fix it.
3. Provide a confidence score (0.0 to 1.0) for your diagnosis.

You MUST respond with ONLY a JSON object in this exact format:
{
  "failure_type": "short_label",
  "diagnosis": "Clear one-sentence explanation of what went wrong",
  "confidence": 0.75,
  "kubectl_command": "kubectl delete pod <pod-name> -n <namespace>",
  "reasoning": "Brief explanation of why you chose this fix"
}

Do NOT include any text outside the JSON object. Only output valid JSON.
"""


class LLMFallback:
    """Google Gemini-based fallback for unknown Kubernetes failures."""

    def __init__(self):
        self.api_key = GEMINI_API_KEY
        self.model_name = "gemini-2.0-flash"

    def diagnose(self, pod_name: str, namespace: str, logs: str, metrics: dict) -> dict:
        """
        Send logs + metrics to Gemini and get a structured diagnosis.

        Args:
            pod_name: Name of the failing pod.
            namespace: Kubernetes namespace.
            logs: Raw pod logs.
            metrics: Metrics dict (e.g. {"memory_usage": 0.95}).

        Returns:
            dict with keys: failure_type, diagnosis, confidence, kubectl_command, reasoning
        """
        if not self.api_key or self.api_key == "your_key_here":
            return self._mock_response(pod_name, namespace, logs)

        try:
            import google.generativeai as genai

            genai.configure(api_key=self.api_key)
            model = genai.GenerativeModel(
                model_name=self.model_name,
                system_instruction=SYSTEM_PROMPT,
            )

            user_prompt = (
                f"Pod: {pod_name}\n"
                f"Namespace: {namespace}\n"
                f"Logs:\n{logs}\n\n"
                f"Metrics: {json.dumps(metrics)}\n\n"
                "Diagnose this failure and respond with ONLY a JSON object."
            )

            response = model.generate_content(user_prompt)
            raw_text = response.text.strip()

            # Strip markdown fences when the model wraps the response.
            if raw_text.startswith("```"):
                raw_text = raw_text.split("\n", 1)[1]  # remove first line
                raw_text = raw_text.rsplit("```", 1)[0]  # remove last fence
                raw_text = raw_text.strip()

            result = json.loads(raw_text)

            # Validate the expected response fields.
            required_keys = ["failure_type", "diagnosis", "confidence", "kubectl_command"]
            for key in required_keys:
                if key not in result:
                    raise ValueError(f"Missing key in LLM response: {key}")

            return result

        except Exception as e:
            print(f"[LLM Fallback] Error calling Gemini: {e}")
            return self._mock_response(pod_name, namespace, logs)

    @staticmethod
    def _mock_response(pod_name: str, namespace: str, logs: str) -> dict:
        """Fallback mock response when API key is missing or call fails."""
        return {
            "failure_type": "unknown",
            "diagnosis": f"Unknown failure detected in pod {pod_name}. "
                         "Unable to match known patterns. Manual investigation recommended.",
            "confidence": 0.50,
            "kubectl_command": f"kubectl delete pod {pod_name} -n {namespace}",
            "reasoning": "Default safe action: pod restart. LLM API key not configured or call failed.",
        }


# ── Standalone test ──
if __name__ == "__main__":
    fallback = LLMFallback()

    result = fallback.diagnose(
        pod_name="webapp-abc123",
        namespace="production",
        logs="Error: ECONNREFUSED 127.0.0.1:5432 - connection refused to database",
        metrics={"memory_usage": 0.3, "restart_count": 2},
    )

    print("=== LLM Fallback Test ===")
    for key, value in result.items():
        print(f"  {key}: {value}")
