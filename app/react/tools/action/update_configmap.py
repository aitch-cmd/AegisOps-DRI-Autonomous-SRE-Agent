"""
Action Tool — update_config_map
Patch a single key-value in a Kubernetes ConfigMap.
Snapshots the old value to incident memory before patching — making every
config change reversible, auditable, and memory-tracked.
"""

import time
from datetime import datetime, timezone

from kubernetes_asyncio import client, config
from kubernetes_asyncio.client import ApiException
from langchain_core.tools import tool

from app.states import ToolInvocation, PolicyDecision
from tools.retrieve_policy import retrieve_policy
from tools.save_incident_memory import save_incident_memory


async def _get_core_v1() -> client.CoreV1Api:
    try:
        await config.load_incluster_config()
    except Exception:
        await config.load_kube_config()
    return client.CoreV1Api()


@tool
async def update_config_map(
    service: str,
    config_map_name: str,
    namespace: str,
    key: str,
    value: str,
    severity: str,
    autonomy_level: str,
) -> dict:
    """
    Policy-gated patch of a Kubernetes ConfigMap key.
    Snapshots the previous value to incident memory before applying the change.

    Args:
        service:          Logical service name.
        config_map_name:  Name of the ConfigMap to patch.
        namespace:        Kubernetes namespace.
        key:              ConfigMap data key to update.
        value:            New value for the key.
        severity:         Incident severity — critical | high | medium | low.
        autonomy_level:   Agent level — L0 | L1 | L2 | L3.

    Returns:
        Dict with policy_decision, tool_invocation, old_value, and success flag.
    """
    started_at = time.time()
    timestamp  = datetime.now(timezone.utc).isoformat()
    params     = {"service": service, "config_map": config_map_name,
                  "namespace": namespace, "key": key, "value": value}

    policy: PolicyDecision = await retrieve_policy.ainvoke({
        "action": "update_config_map", "service": service,
        "severity": severity, "autonomy_level": autonomy_level,
    })

    if not policy["allowed"]:
        return _result(policy, params, {"reason": policy["reason"]}, False, None, started_at, timestamp)

    success, error, old_val = False, None, None
    try:
        core_v1 = await _get_core_v1()

        # ── Snapshot old value before touching anything ────────────────────
        cm      = await core_v1.read_namespaced_config_map(name=config_map_name, namespace=namespace)
        old_val = (cm.data or {}).get(key)

        await save_incident_memory.ainvoke({
            "incident_id":      f"config_snapshot_{service}_{key}_{timestamp}",
            "symptoms":         [f"config change on key={key} in {config_map_name}"],
            "diagnosis":        {"root_cause_hypothesis": "agent mitigation via config patch",
                                 "confidence_score": 1.0,
                                 "supporting_evidence": [],
                                 "recommended_actions": []},
            "tool_invocations": [],
            "outcome":          f"previous_value={old_val}",
            "mttr_seconds":     0,
        })

        # ── Apply patch ───────────────────────────────────────────────────
        await core_v1.patch_namespaced_config_map(
            name=config_map_name,
            namespace=namespace,
            body={"data": {key: value}},
        )
        success = True

    except ApiException as e:
        error = f"Kubernetes API error {e.status}: {e.reason}"
    except Exception as e:
        error = str(e)

    return _result(policy, params, {"error": error, "old_value": old_val}, success, old_val, started_at, timestamp)


def _result(policy, params, result, success, old_val, started_at, timestamp) -> dict:
    invocation = ToolInvocation(
        tool_name="update_config_map",
        params=params,
        result=result,
        success=success,
        latency_ms=int((time.time() - started_at) * 1000),
        timestamp=timestamp,
        policy_decision=policy,
    )
    return {"policy_decision": policy, "tool_invocation": invocation,
            "success": success, "old_value": old_val, "error": result.get("error")}