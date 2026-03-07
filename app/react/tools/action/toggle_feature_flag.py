"""
Action Tool — toggle_feature_flag
Enable/disable a feature flag via internal flag service with scope support:
global | tenant | region | percentage — enabling canary and kill-switch patterns.
"""

import os
import time
from datetime import datetime, timezone
from typing import Literal

import httpx
from langchain_core.tools import tool

from app.react.states import ToolInvocation, PolicyDecision
from app.react.tools.memory.retrieve_policy import retrieve_policy

_FLAG_SERVICE_URL   = os.environ.get("FEATURE_FLAG_SERVICE_URL", "")
_FLAG_SERVICE_TOKEN = os.environ.get("FEATURE_FLAG_SERVICE_TOKEN", "")


@tool
async def toggle_feature_flag(
    service: str,
    flag_name: str,
    enabled: bool,
    severity: str,
    autonomy_level: str,
    scope: Literal["global", "tenant", "region", "percentage"] = "global",
    target: str = "",       # tenant ID, region name, or percentage string e.g. "10"
) -> dict:
    """
    Policy-gated enable/disable of a feature flag with granular scope control.

    Args:
        service:        Logical service name that owns the flag.
        flag_name:      Feature flag identifier, e.g. 'payment.new_checkout_flow'.
        enabled:        True to enable, False to disable.
        severity:       Incident severity — critical | high | medium | low.
        autonomy_level: Agent level — L0 | L1 | L2 | L3.
        scope:          Rollout scope — global | tenant | region | percentage.
        target:         Scope target value:
                          tenant     → tenant ID, e.g. "tenant_abc"
                          region     → region name, e.g. "us-east-1"
                          percentage → numeric string, e.g. "10" for 10 %
                          global     → leave empty

    Returns:
        Dict with policy_decision, tool_invocation, and success flag.
    """
    started_at = time.time()
    timestamp  = datetime.now(timezone.utc).isoformat()
    params     = {"service": service, "flag_name": flag_name, "enabled": enabled,
                  "scope": scope, "target": target}

    policy: PolicyDecision = await retrieve_policy.ainvoke({
        "action": "toggle_feature_flag", "service": service,
        "severity": severity, "autonomy_level": autonomy_level,
    })

    if not policy["allowed"]:
        return _result(policy, params, {"reason": policy["reason"]}, False, started_at, timestamp)

    success, error = False, None
    try:
        payload = {"enabled": enabled, "scope": scope, "target": target}
        headers = {"Authorization": f"Bearer {_FLAG_SERVICE_TOKEN}",
                   "Content-Type": "application/json"}

        async with httpx.AsyncClient(timeout=10) as http:
            resp = await http.patch(
                f"{_FLAG_SERVICE_URL}/flags/{flag_name}",
                json=payload,
                headers=headers,
            )
            resp.raise_for_status()
            success = True

    except httpx.HTTPStatusError as e:
        error = f"Flag service error {e.response.status_code}: {e.response.text}"
    except Exception as e:
        error = str(e)

    return _result(policy, params, {"error": error}, success, started_at, timestamp)


def _result(policy, params, result, success, started_at, timestamp) -> dict:
    invocation = ToolInvocation(
        tool_name="toggle_feature_flag",
        params=params,
        result=result,
        success=success,
        latency_ms=int((time.time() - started_at) * 1000),
        timestamp=timestamp,
        policy_decision=policy,
    )
    return {"policy_decision": policy, "tool_invocation": invocation,
            "success": success, "error": result.get("error")}