import time
import re
from typing import Any, Dict, List, Optional
from collections import Counter

import requests
from langchain_core.tools import tool

from app.core.logging import get_logger
from app.core.settings import settings

logger = get_logger(__name__)


def normalize_message(msg: str) -> str:
    """
    Normalize log message to extract signature:
    - remove numbers, UUIDs, IPs
    - strip extra spaces
    """
    msg = msg.lower()
    msg = re.sub(r'\b\d+\b', '', msg)  # remove numbers
    msg = re.sub(r'[0-9a-fA-F-]{36}', '', msg)  # remove UUIDs
    msg = re.sub(r'\d+\.\d+\.\d+\.\d+', '', msg)  # remove IPs
    msg = re.sub(r'\s+', ' ', msg)
    return msg.strip()


@tool
def get_logs(
    service_name: str,
    lookback_minutes: int = 10,
    top_k: int = 5,
    log_level: Optional[str] = "error",
) -> Dict[str, Any]:
    """
    Fetch logs from Loki and return top error patterns instead of raw lines.
    """

    base_url = settings.LOKI_URL

    now_ns = int(time.time() * 1e9)
    start_ns = now_ns - int(lookback_minutes * 60 * 1e9)

    if log_level:
        logql = f'{{app="{service_name}"}} |= "{log_level.upper()}"'
    else:
        logql = f'{{app="{service_name}"}}'

    params = {
        "query": logql,
        "start": str(start_ns),
        "end": str(now_ns),
        "limit": "500",
        "direction": "backward",
    }

    query_start = time.monotonic()

    try:
        response = requests.get(
            f"{base_url}/loki/api/v1/query_range",
            params=params,
            timeout=5,
            headers={"X-Scope-OrgID": settings.LOKI_TENANT_ID}
            if settings.LOKI_TENANT_ID else {},
        )
        response.raise_for_status()

    except Exception as e:
        logger.error("Loki query failed", extra={"error": str(e)})
        return {
            "top_errors": [],
            "total_error_lines": 0,
            "query_duration_ms": None,
            "errors": [f"WARNING: Failed to connect to Loki API. Error: {str(e)}. Attempt to use get_metrics or get_pod_status instead."],
        }

    query_duration_ms = (time.monotonic() - query_start) * 1000

    try:
        data = response.json()
        streams = data.get("data", {}).get("result", [])
    except Exception as e:
        return {
            "top_errors": [],
            "total_error_lines": 0,
            "query_duration_ms": round(query_duration_ms, 2),
            "errors": [f"JSON parse error: {str(e)}"],
        }

    messages: List[str] = []

    for stream in streams:
        values = stream.get("values", [])
        for entry in values:
            try:
                raw_line = entry[1]
                norm = normalize_message(raw_line)
                if norm:
                    messages.append(norm)
            except (IndexError, ValueError):
                continue

    counter = Counter(messages)
    most_common = counter.most_common(top_k)

    top_errors = [
        {"pattern": pattern, "count": count}
        for pattern, count in most_common
    ]

    return {
        "top_errors": top_errors,
        "total_error_lines": len(messages),
        "query_duration_ms": round(query_duration_ms, 2),
        "errors": [],
    }
