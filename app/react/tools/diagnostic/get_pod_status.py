from typing import Dict, Any
from langchain_core.tools import tool
from kubernetes import client, config

config.load_incluster_config()

@tool
def get_pod_status(deployment: str, namespace: str = "prod") -> Dict[str, Any]:
    """
    Get pod health, restarts, OOMKills.
    """
    v1 = client.CoreV1Api()

    pods = v1.list_namespaced_pod(
        namespace=namespace,
        label_selector=f"app={deployment}"
    )

    status = []

    for pod in pods.items:
        container = pod.status.container_statuses[0]
        status.append({
            "pod": pod.metadata.name,
            "restarts": container.restart_count,
            "ready": container.ready,
            "state": str(container.state)
        })

    return {
        "pods": status
    }