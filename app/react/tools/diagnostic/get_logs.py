import time
import re
from typing import Any, Dict, List, Optional
from collections import Counter

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
    Fetch logs from journalctl / plain log files and return top error patterns.
    Falls back to mock data when running outside a live host.
    """

    # ==========================================
    # MOCK DATA FOR PORTFOLIO DEMO
    # ==========================================
    logger.info(f"Using MOCK logs for: {service_name}")
    
    if service_name == "frontend":
        top_errors = [
            {"pattern": "level=error msg=\"Node server crashed with OOM\"", "count": 42},
            {"pattern": "level=error msg=\"Failed to fetch data from /api/checkout api timeout\"", "count": 15},
            {"pattern": "level=error msg=\"Unhandled promise rejection in ClientRouter\"", "count": 5}
        ]
        total_error_lines = 150
    elif service_name == "checkout-service":
        top_errors = [
            {"pattern": "FATAL - Connection to database timed out after 30000ms", "count": 210},
            {"pattern": "ERROR - Payment gateway stripe returned 503 Service Unavailable", "count": 45},
            {"pattern": "WARN - Queue size reached maximum capacity", "count": 12}
        ]
        total_error_lines = 300
    elif service_name == "auth-service":
        top_errors = [
            {"pattern": "ERROR - Invalid JWT signature detected from IP", "count": 8},
            {"pattern": "WARN - Rate limit exceeded for user login attempts", "count": 3}
        ]
        total_error_lines = 25
    else:
        top_errors = [
            {"pattern": f"ERROR - Unexpected generic fault in {service_name}", "count": 5}
        ]
        total_error_lines = 12

    time.sleep(1)  # Simulate latency

    return {
        "top_errors": top_errors,
        "total_error_lines": total_error_lines,
        "query_duration_ms": 145.2,
        "errors": [],
    }

    # ──────────────────────────────────────────
    # PRODUCTION: journalctl / plain log files
    # ──────────────────────────────────────────
    # import subprocess, pathlib
    #
    # log_file = pathlib.Path(f"/var/log/{service_name}/{service_name}.log")
    #
    # query_start = time.monotonic()
    #
    # try:
    #     if log_file.exists():
    #         # Read from plain log file
    #         lines = log_file.read_text().splitlines()[-500:]
    #     else:
    #         # Fall back to journalctl
    #         result = subprocess.run(
    #             ["journalctl", "-u", service_name,
    #              f"--since={lookback_minutes} min ago",
    #              "--no-pager", "-q"],
    #             capture_output=True, text=True, timeout=10,
    #         )
    #         lines = result.stdout.splitlines()[-500:]
    #
    # except Exception as e:
    #     logger.error("Log fetch failed", extra={"error": str(e)})
    #     return {
    #         "top_errors": [],
    #         "total_error_lines": 0,
    #         "query_duration_ms": None,
    #         "errors": [f"WARNING: Failed to fetch logs. Error: {str(e)}. Try get_metrics or get_pod_status instead."],
    #     }
    #
    # query_duration_ms = (time.monotonic() - query_start) * 1000
    #
    # if log_level:
    #     lines = [l for l in lines if log_level.upper() in l.upper()]
    #
    # messages = [normalize_message(l) for l in lines if normalize_message(l)]
    #
    # counter = Counter(messages)
    # most_common = counter.most_common(top_k)
    #
    # top_errors = [
    #     {"pattern": pattern, "count": count}
    #     for pattern, count in most_common
    # ]
    #
    # return {
    #     "top_errors": top_errors,
    #     "total_error_lines": len(messages),
    #     "query_duration_ms": round(query_duration_ms, 2),
    #     "errors": [],
    # }
