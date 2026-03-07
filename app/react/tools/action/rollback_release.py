"""
Action Tool — rollback_release
Revert a Kubernetes deployment to its previous revision by swapping the
pod template from the second-most-recent ReplicaSet.
spec.rollbackTo is deprecated and a no-op in modern Kubernetes — this uses
the correct ReplicaSet approach.
"""

import time
from datetime import datetime, timezone

from kubernetes_asyncio import client, config
from kubernetes_asyncio.client import ApiException
from langchain_core.tools import tool

from app.react.states import ToolInvocation, PolicyDecision
from app.react.tools.memory.retrieve_policy import retrieve_policy


async def _get_apps_v1() -> client.AppsV1Api:
    try:
        await config.load_incluster_config()
    except Exception:
        await config.load_kube_config()
    return client.AppsV1Api()


async def _rollback_via_rs(namespace: str, deployment: str) -> None:
    """
    Swap deployment pod template to the previous ReplicaSet's template.
    ReplicaSets are sorted by creation timestamp — index [1] is the previous revision.
    """
    apps_v1 = await _get_apps_v1()

    rs_list = await apps_v1.list_namespaced_replica_set(
        namespace=namespace,
        label_selector=f"app={deployment}",
    )

    rs_sorted = sorted(
        rs_list.items,
        key=lambda rs: rs.metadata.creation_timestamp,
        reverse=True,
    )

    if len(rs_sorted) < 2:
        raise Exception("No previous revision available to rollback to")

    prev_rs = rs_sorted[1]

    await apps_v1.patch_namespaced_deployment(
        name=deployment,
        namespace=namespace,
        body={"spec": {"template": prev_rs.spec.template}},
    )


@tool
async def rollback_release(
    service: str,
    deployment: str,
    namespace: str,
    severity: str,
    autonomy_level: str,
) -> dict:
    """
    Policy-gated rollback of a Kubernetes deployment to its previous revision.
    Uses ReplicaSet pod template swap — not the deprecated spec.rollbackTo.

    Args:
        service:        Logical service name.
        deployment:     Kubernetes deployment name.
        namespace:      Kubernetes namespace.
        severity:       Incident severity — critical | high | medium | low.
        autonomy_level: Agent level — L0 | L1 | L2 | L3.

    Returns:
        Dict with policy_decision, tool_invocation, and success flag.
    """
    started_at = time.time()
    timestamp  = datetime.now(timezone.utc).isoformat()
    params     = {"service": service, "deployment": deployment, "namespace": namespace}

    policy: PolicyDecision = await retrieve_policy.ainvoke({
        "action": "rollback_release", "service": service,
        "severity": severity, "autonomy_level": autonomy_level,
    })

    if not policy["allowed"]:
        return _result(policy, params, {"reason": policy["reason"]}, False, started_at, timestamp)

    success, error = False, None
    try:
        await _rollback_via_rs(namespace, deployment)
        success = True
    except ApiException as e:
        error = f"Kubernetes API error {e.status}: {e.reason}"
    except Exception as e:
        error = str(e)

    return _result(policy, params, {"error": error}, success, started_at, timestamp)


def _result(policy, params, result, success, started_at, timestamp) -> dict:
    invocation = ToolInvocation(
        tool_name="rollback_release",
        params=params,
        result=result,
        success=success,
        latency_ms=int((time.time() - started_at) * 1000),
        timestamp=timestamp,
        policy_decision=policy,
    )
    return {"policy_decision": policy, "tool_invocation": invocation,
            "success": success, "error": result.get("error")}