"""
Action Tool — scale_deployment
Scales a Kubernetes deployment to a specified number of replicas.
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


async def _scale_deployment(apps_v1: client.AppsV1Api, namespace: str, deployment: str, replicas: int) -> None:
    await apps_v1.patch_namespaced_deployment_scale(
        name=deployment,
        namespace=namespace,
        body={"spec": {"replicas": replicas}},
    )


async def _wait_for_scale(apps_v1: client.AppsV1Api, namespace: str, deployment: str, target_replicas: int) -> bool:
    deadline = time.time() + _ROLLOUT_TIMEOUT_S
    while time.time() < deadline:
        dep = await apps_v1.read_namespaced_deployment(name=deployment, namespace=namespace)
        ready = dep.status.ready_replicas or 0
        if ready >= target_replicas:
            return True
        await asyncio.sleep(_ROLLOUT_POLL_INTERVAL_S)
    return False


async def _check_health(service: str, namespace: str, deployment: str, target_replicas: int) -> HealthCheckResult:
    apps_v1 = await _get_apps_v1()
    dep = await apps_v1.read_namespaced_deployment(name=deployment, namespace=namespace)
    ready = dep.status.ready_replicas or 0
    healthy = ready >= target_replicas

    return HealthCheckResult(
        service=service,
        healthy=healthy,
        pod_status="Running" if healthy else "Degraded",
        error_rate=0.0,
        checked_at=datetime.now(timezone.utc).isoformat(),
    )


@tool
async def scale_deployment(
    service: str,
    deployment: str,
    namespace: str,
    replicas: int,
    severity: str,
    autonomy_level: str,
) -> dict:
    """
    Policy-gated scaling of a Kubernetes deployment.
    Flow: policy check -> scale -> wait for ready replicas -> health check.

    Args:
        service:        Logical service name, e.g. 'payment-service'.
        deployment:     Kubernetes deployment name, e.g. 'payment-worker'.
        namespace:      Kubernetes namespace, e.g. 'production'.
        replicas:       Target number of replicas.
        severity:       Incident severity — critical | high | medium | low.
        autonomy_level: Agent level — L0 | L1 | L2 | L3.

    Returns:
        Dict with policy_decision, health_check, tool_invocation, and success flag.
    """
    started_at = time.time()
    timestamp = datetime.now(timezone.utc).isoformat()

    policy: PolicyDecision = await retrieve_policy.ainvoke({
        "action": "scale_deployment",
        "service": service,
        "severity": severity,
        "autonomy_level": autonomy_level,
    })

    if not policy["allowed"]:
        invocation = ToolInvocation(
            tool_name="scale_deployment",
            params={"service": service, "deployment": deployment, "namespace": namespace, "replicas": replicas},
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
        await _scale_deployment(apps_v1, namespace, deployment, replicas)
        scaled_out = await _wait_for_scale(apps_v1, namespace, deployment, replicas)

        health = await _check_health(service, namespace, deployment, replicas)
        success = scaled_out and health["healthy"]
    except ApiException as e:
        error = f"Kubernetes API error {e.status}: {e.reason}"
    except Exception as e:
        error = str(e)

    invocation = ToolInvocation(
        tool_name="scale_deployment",
        params={"service": service, "deployment": deployment, "namespace": namespace, "replicas": replicas},
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
