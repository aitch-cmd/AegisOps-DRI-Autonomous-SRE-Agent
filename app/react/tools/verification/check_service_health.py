"""
Verification Tool — check_service_health
Poll pod readiness + error rate post-action to verify recovery.
"""

import time
from typing import Dict, Any

import requests
from kubernetes import client, config
from langchain_core.tools import tool

from app.core.settings import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

import os

try:
    if os.getenv("KUBERNETES_SERVICE_HOST"):
        config.load_incluster_config()
    else:
        config.load_kube_config()
except Exception as e:
    logger.error(f"Failed to load Kubernetes config: {e}")


@tool
def check_service_health(
    service: str,
    deployment: str,
    namespace: str = "prod",
    lookback_minutes: int = 2,
) -> Dict[str, Any]:
    """
    Poll pod readiness and error rate post-action to verify recovery.

    Args:
        service:          Logical service name (used for Prometheus queries).
        deployment:       Kubernetes deployment name (used for pod selector).
        namespace:        Kubernetes namespace.
        lookback_minutes: Window for error-rate check.

    Returns:
        Dict with pod readiness summary, current error rate, and healthy flag.
    """
    # ── Pod readiness ──────────────────────────────────────────────────
    try:
        v1 = client.CoreV1Api()
        pods = v1.list_namespaced_pod(
            namespace=namespace,
            label_selector=f"app={deployment}",
        )
    except Exception as e:
        return {"error": f"WARNING: Failed to connect to Kubernetes API. Error: {str(e)}."}

    total, ready = 0, 0
    for pod in pods.items:
        total += 1
        if pod.status.container_statuses:
            cs = pod.status.container_statuses[0]
            if cs.ready:
                ready += 1

    # ── Error rate ─────────────────────────────────────────────────────
    duration = f"{lookback_minutes}m"
    query = (
        f'sum(rate(http_requests_total{{job="{service}", status=~"5.."}}[{duration}]))'
        f' / '
        f'sum(rate(http_requests_total{{job="{service}"}}[{duration}]))'
    )
    error_rate = None
    try:
        resp = requests.get(
            f"{settings.PROMETHEUS_URL}/api/v1/query",
            params={"query": query},
            timeout=2,
        )
        resp.raise_for_status()
        data = resp.json()
        if data["status"] == "success" and data["data"]["result"]:
            error_rate = float(data["data"]["result"][0]["value"][1])
    except Exception as e:
        logger.error(f"Error querying Prometheus for health check: {e}")

    healthy = ready == total and total > 0 and (error_rate is None or error_rate < 0.05)

    return {
        "service": service,
        "healthy": healthy,
        "pods_total": total,
        "pods_ready": ready,
        "error_rate": error_rate,
        "checked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
