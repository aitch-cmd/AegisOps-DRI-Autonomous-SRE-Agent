"""
Action Tool — update_deployment_image
Updates a deployment's container image (effectively acting as a rollback/rollforward mechanism).
Every execution is policy-gated and appended to the tool_invocations audit trail.
"""

import os
import time
from datetime import datetime, timezone
import asyncio
from kubernetes_asyncio import client, config
from kubernetes_asyncio.client import ApiException
from langchain_core.tools import tool

from app.react.states import HealthCheckResult, PolicyDecision, ToolInvocation
from app.react.tools.memory.retrieve_policy import retrieve_policy
from app.utils.load_params import load_params

params = load_params("app/params.yml")
_ROLLOUT_POLL_INTERVAL_S = params.get("restart_deployment", {}).get("rollout_poll_interval_s", 2)
_ROLLOUT_TIMEOUT_S = params.get("restart_deployment", {}).get("rollout_timeout_s", 60)


async def _get_apps_v1() -> client.AppsV1Api:
    if os.getenv("KUBERNETES_SERVICE_HOST"):
        await config.load_incluster_config()
    else:
        await config.load_kube_config()
    return client.AppsV1Api()


async def _update_image(apps_v1: client.AppsV1Api, namespace: str, deployment: str, container_name: str, new_image: str) -> None:
    patch = {
        "spec": {
            "template": {
                "spec": {
                    "containers": [
                        {
                            "name": container_name,
                            "image": new_image
                        }
                    ]
                }
            }
        }
    }
    await apps_v1.patch_namespaced_deployment(
        name=deployment,
        namespace=namespace,
        body=patch,
    )


async def _wait_for_rollout(apps_v1: client.AppsV1Api, namespace: str, deployment: str) -> bool:
    deadline = time.time() + _ROLLOUT_TIMEOUT_S
    while time.time() < deadline:
        dep = await apps_v1.read_namespaced_deployment(name=deployment, namespace=namespace)
        spec_replicas = dep.spec.replicas or 1
        ready_replicas = dep.status.ready_replicas or 0
        if ready_replicas >= spec_replicas:
            return True
        await asyncio.sleep(_ROLLOUT_POLL_INTERVAL_S)
    return False


async def _check_health(service: str, namespace: str, deployment: str) -> HealthCheckResult:
    apps_v1 = await _get_apps_v1()
    dep = await apps_v1.read_namespaced_deployment(name=deployment, namespace=namespace)
    ready = dep.status.ready_replicas or 0
    desired = dep.spec.replicas or 1
    healthy = ready >= desired

    return HealthCheckResult(
        service=service,
        healthy=healthy,
        pod_status="Running" if healthy else "Degraded",
        error_rate=0.0,
        checked_at=datetime.now(timezone.utc).isoformat(),
    )


@tool
async def update_deployment_image(
    service: str,
    deployment: str,
    namespace: str,
    container_name: str,
    new_image: str,
    severity: str,
    autonomy_level: str,
) -> dict:
    """
    Policy-gated image update for a Kubernetes deployment. Used for immediate rollbacks or emergency patches.
    Flow: policy check -> patch deployment image -> wait for rollout -> health check.

    Args:
        service:        Logical service name.
        deployment:     Kubernetes deployment name.
        namespace:      Kubernetes namespace.
        container_name: The name of the container within the pod to update.
        new_image:      The new Docker image tag to deploy (e.g. 'nginx:1.20' for a rollback).
        severity:       Incident severity.
        autonomy_level: Agent level.

    Returns:
        Dict with policy_decision, health_check, tool_invocation, and success flag.
    """
    started_at = time.time()
    timestamp = datetime.now(timezone.utc).isoformat()

    policy: PolicyDecision = await retrieve_policy.ainvoke({
        "action": "update_deployment_image",
        "service": service,
        "severity": severity,
        "autonomy_level": autonomy_level,
    })

    if not policy["allowed"]:
        invocation = ToolInvocation(
            tool_name="update_deployment_image",
            params={"service": service, "deployment": deployment, "namespace": namespace, "image": new_image},
            result={"reason": policy["reason"]},
            success=False,
            latency_ms=int((time.time() - started_at) * 1000),
            timestamp=timestamp,
            policy_decision=policy,
        )
        return {"policy_decision": policy, "health_check": None, "tool_invocation": invocation, "success": False}

    success = False
    error = None
    health = None

    try:
        apps_v1 = await _get_apps_v1()
        await _update_image(apps_v1, namespace, deployment, container_name, new_image)
        rolled_out = await _wait_for_rollout(apps_v1, namespace, deployment)
        health = await _check_health(service, namespace, deployment)
        success = rolled_out and health["healthy"]
    except ApiException as e:
        error = f"Kubernetes API error {e.status}: {e.reason}"
    except Exception as e:
        error = str(e)

    invocation = ToolInvocation(
        tool_name="update_deployment_image",
        params={"service": service, "deployment": deployment, "namespace": namespace, "image": new_image},
        result={"health_check": health, "error": error},
        success=success,
        latency_ms=int((time.time() - started_at) * 1000),
        timestamp=timestamp,
        policy_decision=policy,
    )

    return {
        "policy_decision": policy,
        "health_check": health,
        "tool_invocation": invocation,
        "success": success,
        "error": error,
    }
