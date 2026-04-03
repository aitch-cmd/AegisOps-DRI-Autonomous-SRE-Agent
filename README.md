# 🛡️ AegisOps

AegisOps is an autonomous Site Reliability Engineering (SRE) agent that diagnoses and resolves production incidents in real time. Powered by a **LangGraph ReAct** cognitive loop and a **multi-tiered memory architecture** (episodic, semantic, procedural), it bridges live Kubernetes clusters, observability stacks, and human-in-the-loop Slack approvals to safely remediate outages at machine speed.

## ✨ Key Features
- **ReAct Cognitive Architecture:** Strict "Thought → Action → Observation" loop driven by a locally-hosted Ollama LLM (`llama3.1:8b`).
- **Multi-tiered Memory:**
  - *Working Memory:* Short-term tracking of ongoing incidents via LangGraph PostgreSQL checkpointers.
  - *Episodic Memory:* Vectorized retrieval of similar past incidents via `pgvector` embeddings (`nomic-embed-text`).
  - *Semantic Memory:* On-demand RAG search over chunked runbooks, architecture docs, and postmortems.
  - *Procedural Memory:* Strict operational policies gating destructive actions based on autonomy levels (`L0–L3`), with Redis-backed caching (1h TTL).
- **Graceful Diagnostic Fallbacks:** `get_logs` tries `journalctl` first, then falls back to `/var/log/<service>/` plain log files. `get_pod_status` and `check_service_health` detect whether they're running inside a Kubernetes cluster or locally via `~/.kube/config`.
- **Policy-Gated Actions:** Every mutating tool (e.g. `restart_deployment`) passes through `retrieve_policy` which enforces autonomy-level checks and caches results in Redis.
- **Human-in-the-Loop Approvals:** Slack interactive endpoints (`/slack/actions`) allow SREs to `Approve` or `Deny` high-risk agent commands before they execute.

## 🏗️ Architecture Flow
1. **Trigger:** Prometheus alerts, SREs (via Slack `@AegisOps` / manual FastAPI webhook), or direct API calls hit the webhook endpoint.
2. **Pre-loading:** The LangGraph `memory_node` fetches relevant procedural policies from Postgres and retrieves similar past incidents via pgvector.
3. **Reasoning:** The `agent_node` forms a hypothesis and executes diagnostic tools (`get_pod_status`, `get_logs`, `retrieve_runbook`).
4. **Action:** The agent proposes mutating actions (`restart_deployment`) which are policy-gated via `retrieve_policy`. High-risk actions require human approval via Slack.
5. **Verification:** `check_service_health` polls pod readiness and Prometheus error rates post-action to confirm the fix worked.
6. **Resolution:** The `resolution_node` calculates MTTR, summarizes the outcome to Slack, and embeds the resolution into pgvector for future episodic retrieval.

## 🧰 Tool Inventory

| Category | Tool | Description |
|---|---|---|
| **Diagnostic** | `get_pod_status` | Query Kubernetes pod health, restarts, OOMKills |
| **Diagnostic** | `get_logs` | Fetch error logs via journalctl / log files with pattern analysis |
| **Memory** | `retrieve_runbook` | Semantic RAG search over runbooks & architecture docs |
| **Memory** | `retrieve_policy` | Policy lookup with Redis cache → Postgres fallback |
| **Action** | `restart_deployment` | Policy-gated rolling restart: drain → restart → health check |
| **Verification** | `check_service_health` | Poll pod readiness + Prometheus error rates |
| **Notification** | `write_audit_log` | Append tool calls to permanent audit trail |
| **Notification** | `send_slack_notification` | Post resolution summaries to Slack channels |

## 🚀 Quick Start

AegisOps relies on `uv` for fast dependency resolution. It automatically detects if it's running inside a cluster or locally against Minikube via `~/.kube/config`.

### Prerequisites
- Python 3.13+
- `uv` installed
- PostgreSQL with `pgvector` extension enabled
- Redis (for policy caching)
- [Ollama](https://ollama.com/) running locally with `llama3.1:8b` and `nomic-embed-text` models pulled

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

# 4. Copy and configure environment variables
cp .env.example .env
# Edit .env with your DATABASE_URL, REDIS_URL, Slack tokens, etc.

# 5. Apply Database Migrations
alembic upgrade head

# 6. Seed initial policies & runbook data
python scripts/seed_data.py
```

### Running the Server
```bash
uvicorn app.main:app --reload
```

## 🛠️ Built With

*   **[LangGraph](https://python.langchain.com/docs/langgraph):** ReAct State Machine & PostgreSQL Checkpointing
*   **[Ollama](https://ollama.com/):** Local LLM (`llama3.1:8b`) & Embeddings (`nomic-embed-text`)
*   **[FastAPI](https://fastapi.tiangolo.com/):** High-performance Async Webhooks & Slack Integration
*   **[SQLAlchemy](https://www.sqlalchemy.org/) & [pgvector](https://github.com/pgvector/pgvector):** Relational State & Vectorized Episodic Memory
*   **[Redis](https://redis.io/):** Policy Decision Caching
*   **[Kubernetes AsyncIO](https://github.com/tomplus/kubernetes_asyncio):** Non-blocking Cluster Operations

## 🤝 Integrating with Slack

AegisOps supports dynamic Slack integration via two primary webhook architectures. To connect, provide these URLs in your Slack App configurations:

1. **Event Subscriptions (`/slack/events`):** Listens for `@AegisOps` mentions in channels to dynamically create incidents. Supports structured format: `@AegisOps service: <name> severity: <level> symptoms: <comma list>`.
2. **Interactivity (`/slack/actions`):** Handles the callback POST requests when an SRE clicks "Approve" or "Deny" on an action card.
