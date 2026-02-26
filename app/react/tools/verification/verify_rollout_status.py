"""
Verification Tool — verify_rollout_status
Check Kubernetes rollout status — Running / Progressing / Failed.
"""

from typing import Dict, Any

from kubernetes import client, config
from langchain_core.tools import tool

config.load_incluster_config()


@tool
def verify_rollout_status(
    deployment: str,
    namespace: str = "prod",
) -> Dict[str, Any]:
    """
    Check Kubernetes deployment rollout status.

    Args:
        deployment: Kubernetes deployment name.
        namespace:  Kubernetes namespace.

    Returns:
        Dict with rollout status (Running / Progressing / Failed),
        replicas summary, and condition details.
    """
    apps_v1 = client.AppsV1Api()
    dep = apps_v1.read_namespaced_deployment(name=deployment, namespace=namespace)

    status = dep.status
    spec_replicas = dep.spec.replicas or 1

    # ── Derive rollout state from conditions ──────────────────────────
    conditions = {c.type: c for c in (status.conditions or [])}

    progressing = conditions.get("Progressing")
    available = conditions.get("Available")

    if progressing and progressing.reason == "ProgressDeadlineExceeded":
        rollout_status = "Failed"
    elif (
        status.updated_replicas == spec_replicas
        and status.ready_replicas == spec_replicas
        and (status.unavailable_replicas or 0) == 0
    ):
        rollout_status = "Running"
    else:
        rollout_status = "Progressing"

    return {
        "deployment": deployment,
        "namespace": namespace,
        "rollout_status": rollout_status,
        "spec_replicas": spec_replicas,
        "ready_replicas": status.ready_replicas or 0,
        "updated_replicas": status.updated_replicas or 0,
        "unavailable_replicas": status.unavailable_replicas or 0,
        "conditions": [
            {"type": c.type, "status": c.status, "reason": c.reason}
            for c in (status.conditions or [])
        ],
    }
