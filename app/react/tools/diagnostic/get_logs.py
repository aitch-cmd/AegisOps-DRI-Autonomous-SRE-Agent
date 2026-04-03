import time
import re
import subprocess
import pathlib
from typing import Any, Dict, List, Optional
from collections import Counter

from langchain_core.tools import tool

from app.core.logging import get_logger

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
    Fetch logs from journalctl or plain log files and return top error patterns.
    Tries journalctl first (systemd hosts), then falls back to
    /var/log/<service>/<service>.log for containerised or file-based setups.
    """

    lines: List[str] = []
    source = "none"

    # ── Strategy 1: journalctl (systemd) ──────────────────────────────────
    try:
        cmd = [
            "journalctl", "-u", service_name,
            "--since", f"{lookback_minutes} min ago",
            "--no-pager", "-q",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if result.returncode == 0 and result.stdout.strip():
            lines = result.stdout.strip().splitlines()
            source = "journalctl"
            logger.info("Fetched %d lines via journalctl for %s", len(lines), service_name)
    except FileNotFoundError:
        logger.info("journalctl not available, falling back to log file")
    except subprocess.TimeoutExpired:
        logger.warning("journalctl timed out for %s", service_name)

    # ── Strategy 2: Plain log file ────────────────────────────────────────
    if not lines:
        log_file = pathlib.Path(f"/var/log/{service_name}/{service_name}.log")
        if log_file.exists():
            lines = log_file.read_text().splitlines()[-500:]
            source = "logfile"
            logger.info("Fetched %d lines from %s", len(lines), log_file)
        else:
            logger.warning("No log source found for %s", service_name)
            return {
                "top_errors": [],
                "total_error_lines": 0,
                "query_duration_ms": 0,
                "errors": [f"No log source available for '{service_name}'. "
                           "Tried journalctl and /var/log/."],
            }

    # ── Filter by level ───────────────────────────────────────────────────
    query_start = time.monotonic()

    if log_level:
        lines = [l for l in lines if log_level.upper() in l.upper()]

    # ── Normalize and count top patterns ──────────────────────────────────
    messages = [normalize_message(l) for l in lines if normalize_message(l)]
    counter = Counter(messages)
    most_common = counter.most_common(top_k)

    top_errors = [
        {"pattern": pattern, "count": count}
        for pattern, count in most_common
    ]

    query_duration_ms = (time.monotonic() - query_start) * 1000

    return {
        "top_errors": top_errors,
        "total_error_lines": len(messages),
        "query_duration_ms": round(query_duration_ms, 2),
        "source": source,
        "errors": [],
    }
