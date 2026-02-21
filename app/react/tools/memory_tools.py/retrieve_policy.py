"""
Procedural Memory Tool
Fetch Policy row for action + service + severity → evaluate autonomy gate.
Redis cache (1h TTL) prevents repeated Postgres hits per reasoning loop.
"""

import os
from typing import Optional

import redis.asyncio as aioredis
from langchain_core.tools import tool
from sqlalchemy import and_, or_, select

from app.database import get_db_session
from app.react.states import PolicyDecision
from app.models.policies import Policy
from app.utils.load_params import load_params

params = load_params("app/params.yml")
_LEVEL_RANK = params["retrieve_policy"]["level_rank"]   
_redis: Optional[aioredis.Redis] = None


def _get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(os.environ["REDIS_URL"], decode_responses=True)
    return _redis


def _cache_key(action: str, service: str, severity: str) -> str:
    return f"policy:{action}:{service}:{severity}"


def _evaluate(policy: Policy, autonomy_level: str) -> PolicyDecision:
    allowed = _LEVEL_RANK.get(autonomy_level, 0) >= _LEVEL_RANK.get(policy.min_autonomy_level, 3)
    requires_approval = policy.requires_approval and autonomy_level == "L3"
    return PolicyDecision(
        action=policy.action,
        allowed=allowed,
        reason=policy.reason,
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


@tool
async def retrieve_policy(
    action: str,
    service: str,
    severity: str,
    autonomy_level: str,
) -> PolicyDecision:
    """
    Retrieve the policy decision for a proposed mutating action.
    Checks Redis cache first (1h TTL), falls back to Postgres ORM lookup.
    Specific service/severity rows take precedence over wildcard '*' rows.

    Args:
        action:         Tool name, e.g. 'restart_deployment'.
        service:        Target service, e.g. 'payment-service'.
        severity:       Incident severity — critical | high | medium | low.
        autonomy_level: Agent level — L0 | L1 | L2 | L3.

    Returns:
        PolicyDecision with allowed, reason, autonomy_level, requires_approval.
    """
    cache_key = _cache_key(action, service, severity)
    redis = _get_redis()

    # ── Cache hit ──────────────────────────────────────────────────────────
    cached = await redis.hgetall(cache_key)
    if cached:
        policy = Policy(**{k: v for k, v in cached.items()})
        return _evaluate(policy, autonomy_level)

    # ── ORM lookup — specific rows ranked above wildcards ─────────────────
    stmt = (
        select(Policy)
        .where(Policy.action == action)
        .where(or_(Policy.service == service, Policy.service == "*"))
        .where(or_(Policy.severity == severity, Policy.severity == "*"))
        .order_by(
            (Policy.service == service).desc(),
            (Policy.severity == severity).desc(),
        )
        .limit(1)
    )

    async with get_db_session() as db:
        policy = (await db.execute(stmt)).scalar_one_or_none()

    if policy is None:
        return _default_deny(action, autonomy_level)

    # ── Cache the raw policy fields (not the decision — level may differ) ─
    await redis.hset(cache_key, mapping={
        "action": policy.action,
        "service": policy.service,
        "severity": policy.severity,
        "min_autonomy_level": policy.min_autonomy_level,
        "requires_approval": str(policy.requires_approval),
        "reason": policy.reason,
    })
    await redis.expire(cache_key, 3600)

    return _evaluate(policy, autonomy_level)