"""
Action Tool — scale_service
Horizontal scale up or down a Kubernetes deployment replica count.
Guardrails loaded from app/params.yml prevent overscaling and eviction storms.
"""

import time
from datetime import datetime, timezone
from pathlib import Path

import yaml
from kubernetes_asyncio import client, config
from kubernetes_asyncio.client import ApiException
from langchain_core.tools import tool

from app.states import ToolInvocation, PolicyDecision
from tools.retrieve_policy import retrieve_policy


def _load_params() -> dict:
    path = Path(__file__).parents[1] / "app" / "params.yml"
    return yaml.safe_load(path.read_text())


_PARAMS    = _load_params()["scale_service"]
_MAX_DELTA = _PARAMS["max_scale_delta"]        # max replicas change in one action
_MAX_ABS   = _PARAMS["max_absolute_replicas"]  # hard ceiling


async def _get_apps_v1() -> client.AppsV1Api:
    try:
        await config.load_incluster_config()
    except Exception:
        await config.load_kube_config()
    return client.AppsV1Api()


@tool
async def scale_service(
    service: str,
    deployment: str,
    namespace: str,
    replicas: int,
    severity: str,
    autonomy_level: str,
) -> dict:
    """
    Policy-gated horizontal scaling of a Kubernetes deployment.
    Guardrails enforce max delta and absolute replica ceiling from params.yml.

    Args:
        service:        Logical service name.
        deployment:     Kubernetes deployment name.
        namespace:      Kubernetes namespace.
        replicas:       Desired replica count.
        severity:       Incident severity — critical | high | medium | low.
        autonomy_level: Agent level — L0 | L1 | L2 | L3.

    Returns:
        Dict with policy_decision, tool_invocation, and success flag.
    """
    started_at = time.time()
    timestamp  = datetime.now(timezone.utc).isoformat()
    params     = {"service": service, "deployment": deployment,
                  "namespace": namespace, "replicas": replicas}

    policy: PolicyDecision = await retrieve_policy.ainvoke({
        "action": "scale_service", "service": service,
        "severity": severity, "autonomy_level": autonomy_level,
    })

    if not policy["allowed"]:
        return _result(policy, params, {"reason": policy["reason"]}, False, started_at, timestamp)

    success, error = False, None
    try:
        apps_v1 = await _get_apps_v1()

        # ── Guardrails ────────────────────────────────────────────────────
        dep     = await apps_v1.read_namespaced_deployment(name=deployment, namespace=namespace)
        current = dep.spec.replicas or 1

        if replicas > _MAX_ABS:
            raise ValueError(f"Requested {replicas} replicas exceeds safe limit of {_MAX_ABS}")
        if abs(replicas - current) > _MAX_DELTA:
            raise ValueError(
                f"Scale delta {abs(replicas - current)} exceeds max allowed delta of {_MAX_DELTA}"
            )

        # ── Scale ─────────────────────────────────────────────────────────
        await apps_v1.patch_namespaced_deployment_scale(
            name=deployment,
            namespace=namespace,
            body={"spec": {"replicas": replicas}},
        )
        success = True

    except ApiException as e:
        error = f"Kubernetes API error {e.status}: {e.reason}"
    except ValueError as e:
        error = str(e)
    except Exception as e:
        error = str(e)

    return _result(policy, params, {"error": error}, success, started_at, timestamp)


def _result(policy, params, result, success, started_at, timestamp) -> dict:
    invocation = ToolInvocation(
        tool_name="scale_service",
        params=params,
        result=result,
        success=success,
        latency_ms=int((time.time() - started_at) * 1000),
        timestamp=timestamp,
        policy_decision=policy,
    )
    return {"policy_decision": policy, "tool_invocation": invocation,
            "success": success, "error": result.get("error")}