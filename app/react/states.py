from typing import Annotated, Optional, Literal
from typing import TypedDict, List
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage


# ─────────────────────────────────────────────
# Sub-structures (not states, used inside states)
# ─────────────────────────────────────────────

class IncidentEvent(TypedDict):
    incident_id: str
    source: Literal["pagerduty", "prometheus", "mock"]
    severity: Literal["critical", "high", "medium", "low"]
    service: str
    symptoms: List[str]
    raw_payload: dict
    received_at: str


class SimilarIncident(TypedDict):
    incident_id: str
    symptoms: List[str]
    root_cause: str
    actions_taken: List[str]
    outcome: str
    similarity_score: float


class PolicyDecision(TypedDict):
    action: str
    allowed: bool
    reason: str
    autonomy_level: Literal["L0", "L1", "L2", "L3"]
    requires_approval: bool


class ToolInvocation(TypedDict):
    tool_name: str
    params: dict
    result: Optional[dict]
    success: bool
    latency_ms: int
    timestamp: str
    policy_decision: Optional[PolicyDecision]


class DiagnosisResult(TypedDict):
    root_cause_hypothesis: str
    confidence_score: float          # 0.0 – 1.0
    supporting_evidence: List[str]
    recommended_actions: List[str]


class HealthCheckResult(TypedDict):
    service: str
    healthy: bool
    pod_status: str
    error_rate: float
    checked_at: str


# ─────────────────────────────────────────────
# Core Agent State
# ─────────────────────────────────────────────

class AegisOpsState(TypedDict):
    # ── Messaging ──────────────────────────────
    messages: Annotated[List[BaseMessage], add_messages]

    # ── Incident ───────────────────────────────
    incident: IncidentEvent
    incident_status: Literal["investigating", "diagnosing", "acting", "verifying", "resolved", "escalated", "failed"]

    # ── Memory ─────────────────────────────────
    similar_incidents: List[SimilarIncident]          # episodic: top-3 retrieved
    runbook_context: List[str]                        # semantic: relevant runbook chunks
    procedural_policies: List[str]                    # procedural: loaded policy YAMLs

    # ── Reasoning ──────────────────────────────
    current_thought: str
    iteration: int                                    # max 10 guard
    diagnosis: Optional[DiagnosisResult]

    # ── Actions ────────────────────────────────
    pending_action: Optional[str]
    policy_decision: Optional[PolicyDecision]
    approval_status: Optional[Literal["pending", "approved", "denied"]]
    tool_invocations: List[ToolInvocation]            # full audit trail

    # ── Verification ───────────────────────────
    expected_outcome: Optional[str]
    health_check: Optional[HealthCheckResult]
    verification_passed: Optional[bool]
    retry_count: int                                    # max 2 (circuit breaker)

    # ── Resolution ─────────────────────────────
    resolution_summary: Optional[str]
    mttr_seconds: Optional[int]
    slack_notified: bool

    # ── Meta ───────────────────────────────────
    autonomy_level: Literal["L0", "L1", "L2", "L3"]
    user_id: str
    session_id: str
    error: Optional[str]