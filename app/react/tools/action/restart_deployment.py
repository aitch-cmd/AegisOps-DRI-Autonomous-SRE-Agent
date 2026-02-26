"""
Action Tool — restart_deployment
Rolling restart of a Kubernetes deployment: drain → restart → health check.
Every execution is policy-gated and appended to the tool_invocations audit trail.
"""

import os
import time
from datetime import datetime, timezone
import asyncio
from kubernetes_asyncio import client, config
from kubernetes_asyncio.client import ApiException
from langchain_core.tools import tool

from app.states import HealthCheckResult, PolicyDecision, ToolInvocation
from tools.retrieve_policy import retrieve_policy
from app.utils.load_params import load_params

params = load_params("app/params.yml")
_HEALTH_ERROR_RATE_THRESHOLD = params["restart_deployment"]["health_error_rate_threshold"]
_ROLLOUT_POLL_INTERVAL_S     = params["restart_deployment"]["rollout_poll_interval_s"]
_ROLLOUT_TIMEOUT_S           = params["restart_deployment"]["rollout_timeout_s"]


# ── Kubernetes helpers ─────────────────────────────────────────────────────────

async def _get_apps_v1() -> client.AppsV1Api:
    if os.getenv("KUBERNETES_SERVICE_HOST"):
        await config.load_incluster_config()
    else:
        await config.load_kube_config()
    return client.AppsV1Api()


async def _drain_deployment(apps_v1, namespace, deployment):
    await apps_v1.patch_namespaced_deployment_scale(
        name=deployment,
        namespace=namespace,
        body={"spec": {"replicas": 0}},
    )
    await asyncio.sleep(3)


async def _restart_deployment(apps_v1: client.AppsV1Api, namespace: str, deployment: str) -> None:
    """Patch restart annotation — triggers a rolling restart without scaling."""
    now = datetime.now(timezone.utc).isoformat()
    patch = {"spec": {"template": {"metadata": {"annotations": {
        "kubectl.kubernetes.io/restartedAt": now
    }}}}}
    await apps_v1.patch_namespaced_deployment(
        name=deployment,
        namespace=namespace,
        body=patch,
    )


async def _wait_for_rollout(
    apps_v1: client.AppsV1Api,
    namespace: str,
    deployment: str,
) -> bool:
    deadline = time.time() + _ROLLOUT_TIMEOUT_S

    while time.time() < deadline:
        dep = await apps_v1.read_namespaced_deployment(
            name=deployment,
            namespace=namespace
        )
        spec_replicas  = dep.spec.replicas or 1
        ready_replicas = dep.status.ready_replicas or 0

        if ready_replicas >= spec_replicas:
            return True

        await asyncio.sleep(_ROLLOUT_POLL_INTERVAL_S)



async def _check_health(service: str, namespace: str, deployment: str) -> HealthCheckResult:
    """Read pod status post-rollout and return a HealthCheckResult."""
    apps_v1 = await _get_apps_v1()
    dep = await apps_v1.read_namespaced_deployment(name=deployment, namespace=namespace)

    ready    = dep.status.ready_replicas or 0
    desired  = dep.spec.replicas or 1
    healthy  = ready >= desired

    return HealthCheckResult(
        service=service,
        healthy=healthy,
        pod_status="Running" if healthy else "Degraded",
        error_rate=0.0,          # wire to Prometheus in check_service_health tool
        checked_at=datetime.now(timezone.utc).isoformat(),
    )


# ── Tool ──────────────────────────────────────────────────────────────────────

@tool
async def restart_deployment(
    service: str,
    deployment: str,
    namespace: str,
    severity: str,
    autonomy_level: str,
) -> dict:
    """
    Policy-gated rolling restart of a Kubernetes deployment.
    Flow: policy check → drain → restart → wait for rollout → health check.

    Args:
        service:        Logical service name, e.g. 'payment-service'.
        deployment:     Kubernetes deployment name, e.g. 'payment-worker'.
        namespace:      Kubernetes namespace, e.g. 'production'.
        severity:       Incident severity — critical | high | medium | low.
        autonomy_level: Agent level — L0 | L1 | L2 | L3.

    Returns:
        Dict with policy_decision, health_check, tool_invocation, and success flag.
    """
    started_at = time.time()
    timestamp  = datetime.now(timezone.utc).isoformat()

    # ── 1. Policy gate ────────────────────────────────────────────────────
    policy: PolicyDecision = await retrieve_policy.ainvoke({
        "action":         "restart_deployment",
        "service":        service,
        "severity":       severity,
        "autonomy_level": autonomy_level,
    })

    if not policy["allowed"]:
        invocation = ToolInvocation(
            tool_name="restart_deployment",
            params={"service": service, "deployment": deployment, "namespace": namespace},
            result={"reason": policy["reason"]},
            success=False,
            latency_ms=int((time.time() - started_at) * 1000),
            timestamp=timestamp,
            policy_decision=policy,
        )
        return {"policy_decision": policy, "health_check": None,
                "tool_invocation": invocation, "success": False}

    # ── 2. Drain → Restart → Wait ─────────────────────────────────────────
    success = False
    error   = None
    health  = None

    try:
        apps_v1 = await _get_apps_v1()
        await _drain_deployment(apps_v1, namespace, deployment)
        await _restart_deployment(apps_v1, namespace, deployment)
        rolled_out = await _wait_for_rollout(apps_v1, namespace, deployment)

        # ── 3. Health check ───────────────────────────────────────────────
        health  = await _check_health(service, namespace, deployment)
        success = rolled_out and health["healthy"]

    except ApiException as e:
        error = f"Kubernetes API error {e.status}: {e.reason}"
    except Exception as e:
        error = str(e)

    # ── 4. Build audit record ─────────────────────────────────────────────
    invocation = ToolInvocation(
        tool_name="restart_deployment",
        params={"service": service, "deployment": deployment, "namespace": namespace},
        result={"health_check": health, "error": error},
        success=success,
        latency_ms=int((time.time() - started_at) * 1000),
        timestamp=timestamp,
        policy_decision=policy,
    )

    return {
        "policy_decision": policy,
        "health_check":    health,
        "tool_invocation": invocation,
        "success":         success,
        "error":           error,
    }