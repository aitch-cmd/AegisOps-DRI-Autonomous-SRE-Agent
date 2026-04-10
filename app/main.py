import os
from datetime import datetime, timezone
from typing import List, Literal, Optional, Any
import uuid

from dotenv import load_dotenv

# Load environment variables before importing app modules
load_dotenv()

from fastapi import FastAPI, BackgroundTasks, HTTPException
from pydantic import BaseModel

from app.react.graph import run_agent
from app.react.states import IncidentEvent
from app.routers.slack import router as slack_router

from contextlib import asynccontextmanager
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from app.core.settings import settings

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Setup database schema for checkpointer if it doesn't exist
    db_uri = settings.checkpointer_url
        
    async with AsyncPostgresSaver.from_conn_string(db_uri) as checkpointer:
        print("Setting up checkpointer schema in Postgres...")
        await checkpointer.setup()
        print("Checkpointer schema setup complete.")
    yield

app = FastAPI(
    title="AegisOps Agent API",
    description="Webhook receiver for triggering the AegisOps ReAct agent.",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(slack_router)

# Pydantic model for incoming webhook payloads
class IncidentWebhookPayload(BaseModel):
    source: Literal["webhook", "prometheus", "slack"]
    severity: Literal["critical", "high", "medium", "low"]
    service: str
    symptoms: List[str]
    raw_payload: dict[str, Any] = {}
    autonomy_level: Literal["L0", "L1", "L2", "L3"] = "L2"
    user_id: str = "system"


async def process_incident_background(incident: IncidentEvent):
    """Run the agent graph in the background."""
    try:
        # Ainvoke runs the compiled LangGraph agent
        result = await run_agent(incident)
        print(f"Incident {incident['incident_id']} processed. Status: {result.get('incident_status')}")
    except Exception as e:
        print(f"Error processing incident {incident['incident_id']}: {e}")


@app.post("/webhook/incident", status_code=202)
async def receive_incident(payload: IncidentWebhookPayload, background_tasks: BackgroundTasks):
    """
    Receive an incident alert from a monitoring system (e.g., Prometheus) or manual webhook
    and kick off the AegisOps agent investigation in the background.
    """
    incident_id = str(uuid.uuid4())
    
    # Map Pydantic model to TypedDict expected by the state graph
    incident: IncidentEvent = {
        "incident_id": incident_id,
        "source": payload.source,
        "severity": payload.severity,
        "service": payload.service,
        "symptoms": payload.symptoms,
        "raw_payload": payload.raw_payload,
        "received_at": datetime.now(timezone.utc).isoformat(),
        # Add extra fields that run_agent might use for its initial state
        "autonomy_level": payload.autonomy_level,
        "user_id": payload.user_id,
        "session_id": incident_id,
    }

    # The agent might take seconds or minutes to run, so process it in the background
    background_tasks.add_task(process_incident_background, incident)

    return {
        "status": "accepted",
        "message": "Incident received and agent dispatched.",
        "incident_id": incident_id
    }


@app.get("/health")
async def health_check():
    """Simple API health check."""
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    # Optional: Run directly using python app/main.py
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
