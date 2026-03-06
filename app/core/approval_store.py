"""
Approval Store
In-memory registry that links incident_id → approval decision.

The agent calls `wait_for_approval(incident_id)` and suspends.
The Slack /actions endpoint calls `resolve_approval(incident_id, decision)`
which unblocks the waiting coroutine.
"""

import asyncio
from typing import Dict, Literal, Optional

# Maps  incident_id  →  {"event": asyncio.Event, "decision": "approved"|"denied"}
_store: Dict[str, dict] = {}


def register_pending(incident_id: str) -> None:
    """Create a pending approval slot for the given incident."""
    if incident_id not in _store:
        _store[incident_id] = {"event": asyncio.Event(), "decision": None}


def resolve_approval(
    incident_id: str,
    decision: Literal["approved", "denied"],
) -> bool:
    """
    Record the operator's decision and unblock any awaiting coroutine.

    Returns True if the incident was pending, False if unknown.
    """
    entry = _store.get(incident_id)
    if not entry:
        return False
    entry["decision"] = decision
    entry["event"].set()
    return True


async def wait_for_approval(
    incident_id: str,
    timeout_seconds: float = 300.0,
) -> Optional[Literal["approved", "denied"]]:
    """
    Await the operator's decision for up to `timeout_seconds`.

    Returns the decision string, or None on timeout.
    """
    register_pending(incident_id)
    entry = _store[incident_id]
    try:
        await asyncio.wait_for(entry["event"].wait(), timeout=timeout_seconds)
        return entry["decision"]
    except asyncio.TimeoutError:
        return None
    finally:
        # Clean up after decision is consumed
        _store.pop(incident_id, None)


def get_decision(incident_id: str) -> Optional[str]:
    """Peek at the current decision without blocking."""
    entry = _store.get(incident_id)
    return entry["decision"] if entry else None
