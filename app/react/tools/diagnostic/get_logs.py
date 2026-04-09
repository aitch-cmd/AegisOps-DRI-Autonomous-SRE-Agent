import time
import re
import pathlib
from typing import Any, Dict, List, Optional
from collections import Counter

from langchain_core.tools import tool
from app.core.logging import get_logger

logger = get_logger(__name__)


def normalize_message(msg: str) -> str:
    msg = msg.lower()
    msg = re.sub(r'\b\d+\b', '', msg)
    msg = re.sub(r'[0-9a-fA-F-]{36}', '', msg)
    msg = re.sub(r'\d+\.\d+\.\d+\.\d+', '', msg)
    msg = re.sub(r'\s+', ' ', msg)
    return msg.strip()


@tool
def get_logs(
    service_name: str,
    lookback_minutes: int = 10,   # (kept for compatibility, not used unless timestamps exist)
    top_k: int = 5,
    log_level: Optional[str] = "error",
) -> Dict[str, Any]:
    """
    Fetch logs from local ./logs directory and return top error patterns.
    Expected structure:
        logs/
            service_name.log
    """

    query_start = time.monotonic()
    lines: List[str] = []
    source = "logs_folder"

    # ── Read from local logs folder ───────────────────────────────
    log_file = pathlib.Path("logs") / f"{service_name}.log"

    if not log_file.exists():
        logger.warning("Log file not found: %s", log_file)
        return {
            "top_errors": [],
            "total_error_lines": 0,
            "query_duration_ms": 0,
            "source": source,
            "errors": [f"Log file not found: {log_file}"],
        }

    try:
        # Read last N lines (avoid loading huge file)
        lines = log_file.read_text().splitlines()[-500:]
        logger.info("Fetched %d lines from %s", len(lines), log_file)
    except Exception as e:
        return {
            "top_errors": [],
            "total_error_lines": 0,
            "query_duration_ms": 0,
            "source": source,
            "errors": [f"Failed to read log file: {str(e)}"],
        }

    # ── Filter by log level ───────────────────────────────────────
    if log_level:
        lines = [l for l in lines if log_level.upper() in l.upper()]

    # ── Normalize + count ─────────────────────────────────────────
    normalized = []
    for l in lines:
        nm = normalize_message(l)
        if nm:
            normalized.append(nm)

    counter = Counter(normalized)
    most_common = counter.most_common(top_k)

    top_errors = [
        {"pattern": pattern, "count": count}
        for pattern, count in most_common
    ]

    query_duration_ms = (time.monotonic() - query_start) * 1000

    return {
        "top_errors": top_errors,
        "total_error_lines": len(normalized),
        "query_duration_ms": round(query_duration_ms, 2),
        "source": source,
        "errors": [],
    }