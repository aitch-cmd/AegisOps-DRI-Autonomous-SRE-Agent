# 🛡️ AegisOps

AegisOps is an autonomous Site Reliability Engineering (SRE) agent designed to instantly diagnose and resolve production incidents. Powered by LangGraph and ReAct architectures, AegisOps securely bridges observability platforms, Kubernetes execution, and human-in-the-loop Slack approvals to safely remediate outages at superhuman speeds.

## ✨ Key Features
- **ReAct Cognitive Architecture:** Follows a strict "Thought → Action → Observation" loop driven by LLMs.
- **Multi-tiered Memory:**
  - *Working Memory:* Short-term tracking of ongoing incidents using LangGraph checkpointers.
  - *Episodic Memory:* Pre-loads historical RAG context via `pgvector` to remember how similar past incidents were solved.
  - *Semantic Memory:* On-demand vectorized retrieval of internal runbooks and docs.
  - *Procedural Memory:* Strict operational policies gating destructive actions based on autonomy levels.
- **Graceful Diagnostic Fallbacks:** Intelligent tooling that knows to switch from Prometheus to Loki, or from in-cluster Kubernetes APIs to local `kubeconfig` fallback if primary services fail.
- **Human-in-the-Loop Muting:** Slack interactive endpoints (`/slack/actions`) allow SREs to `Approve` or `Deny` high-risk agent commands (e.g. `restart_deployment`) before they execute.

## 🏗️ Architecture Flow
1. **Trigger:** Monitoring tools (PagerDuty/Prometheus) or SREs (via Slack `@AegisOps`) hit the FastAPI webhook endpoints.
2. **Pre-loading:** The LangGraph `memory_node` fetches relevant rules and similar past outages.
3. **Reasoning:** The `agent_node` forms a hypothesis and executes diagnostic tools (fetch metrics, logs, pod statuses).
4. **Action:** The agent executes mutated actions (scaling, rollbacks, restarts) gated by policy checkers.
5. **Verification:** Custom tools poll health metrics post-action to ensure the specific fix worked.
6. **Resolution:** The `resolution_node` summarizes the outcome to Slack and embeds the RCA into pgvector so it remembers the fix for next time.

## 🚀 Quick Start (Minikube / Local Testing)

AegisOps relies on `uv` for fast dependency resolution. It automatically detects if it's running inside a cluster or locally against Minikube via `~/.kube/config`.

### Prerequisites
- Python 3.13+
- `uv` installed
- PostgreSQL with `pgvector` enabled (for episodic memory & LangGraph checkpointing)

### Installation
```bash
# 1. Clone the repository
git clone https://github.com/aitch-cmd/AegisOps.git
cd AegisOps

# 2. Sync dependencies using uv
uv sync

# 3. Activate the virtual environment
# Windows
.venv\Scripts\activate
# Linux/macOS
source .venv/bin/activate

# 4. Apply Database Migrations
alembic upgrade head
```

### Running the Server
```bash
uvicorn app.main:app --reload
```

## 🛠️ Built With

*   **[LangGraph](https://python.langchain.com/docs/langgraph):** Agent State Tracking & Checkpointing
*   **[FastAPI](https://fastapi.tiangolo.com/):** High-performance Async Webhooks
*   **[SQLAlchemy](https://www.sqlalchemy.org/) & [pgvector](https://github.com/pgvector/pgvector):** Relational State & Vectorized Memory
*   **[Kubernetes AsyncIO](https://github.com/tomplus/kubernetes_asyncio):** Non-blocking Cluster Operations

## 🤝 Integrating with Slack

AegisOps supports dynamic Slack integration via two primary webhook architectures. To connect, provide these URLs in your Slack App configurations:

1. **Event Subscriptions (`/slack/events`):** Listens for `@AegisOps` mentions in channels to dynamically create incidents.
2. **Interactivity (`/slack/actions`):** Handles the callback POST requests when an SRE clicks "Approve" or "Deny" on an action card.
