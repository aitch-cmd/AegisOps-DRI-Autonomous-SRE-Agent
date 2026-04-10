from typing import Optional

from langchain_core.tools import tool

from app.react.states import PolicyDecision
from app.utils.load_params import load_params

params = load_params("app/params.yml")
_LEVEL_RANK = params["retrieve_policy"]["level_rank"]
_POLICIES = params["retrieve_policy"].get("policies", [])


def _evaluate(policy: dict, autonomy_level: str) -> PolicyDecision:
    allowed = _LEVEL_RANK.get(autonomy_level, 0) >= _LEVEL_RANK.get(policy.get("min_autonomy_level", "L3"), 3)
    requires_approval = policy.get("requires_approval", True) and autonomy_level == "L3"
    return PolicyDecision(
        action=policy.get("action", "unknown"),
        allowed=allowed,
        reason=policy.get("reason", ""),
        autonomy_level=autonomy_level,  # type: ignore[arg-type]
        requires_approval=requires_approval,
    )


def _default_deny(action: str, autonomy_level: str) -> PolicyDecision:
    return PolicyDecision(
        action=action,
        allowed=False,
        reason="No matching policy found — default deny.",
        autonomy_level=autonomy_level,  # type: ignore[arg-type]
        requires_approval=True,
    )


def match_policies(service: str, severity: str, action: Optional[str] = None) -> list[dict]:
    """Find all policies matching service, severity, and optionally action."""
    matches = []
    for p in _POLICIES:
        p_act = p.get("action")
        p_srv = p.get("service")
        p_sev = p.get("severity")

        # Action must match exactly or be wildcard (if action provided)
        if action and p_act != action and p_act != "*":
            continue

        # Service must match exactly or be wildcard
        if p_srv != service and p_srv != "*":
            continue

        # Severity must match exactly or be wildcard
        if p_sev != severity and p_sev != "*":
            continue
        
        matches.append(p)
    return matches


@tool
async def retrieve_policy(
    action: str,
    service: str,
    severity: str,
    autonomy_level: str,
) -> PolicyDecision:
    """
    Retrieve the policy decision for a proposed mutating action.
    Evaluates against the local params.yml configuration.
    Specific service/severity matching takes precedence over wildcards.

    Args:
        action:         Tool name, e.g. 'restart_deployment'.
        service:        Target service, e.g. 'payment-service'.
        severity:       Incident severity — critical | high | medium | low.
        autonomy_level: Agent level — L0 | L1 | L2 | L3.

    Returns:
        PolicyDecision with allowed, reason, autonomy_level, requires_approval.
    """
    matches = match_policies(service, severity, action)
    
    if not matches:
        return _default_deny(action, autonomy_level)

    # Specific matches are better than wildcards
    best_match = None
    best_score = -1

    for p in matches:
        score = 0
        if p.get("action") == action: score += 4
        if p.get("service") == service: score += 2
        if p.get("severity") == severity: score += 1

        if score > best_score:
            best_score = score
            best_match = p

    return _evaluate(best_match, autonomy_level)