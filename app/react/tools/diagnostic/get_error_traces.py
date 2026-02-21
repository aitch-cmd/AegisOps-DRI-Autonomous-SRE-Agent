import requests
from typing import Dict, Any
from langchain_core.tools import tool
from app.core.settings import settings

@tool
def get_error_traces(service: str, lookback_minutes: int = 10) -> Dict[str, Any]:
    """
    Pull recent Jaeger traces for a service.
    """
    end = int(time.time())
    start = end - lookback_minutes * 60

    url = f"{settings.JAEGER_URL}/api/traces"

    params = {
        "service": service,
        "start": start * 1000000,
        "end": end * 1000000,
        "limit": 5
    }

    try:
        resp = requests.get(url, params=params, timeout=3)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        return {"error": str(e)}