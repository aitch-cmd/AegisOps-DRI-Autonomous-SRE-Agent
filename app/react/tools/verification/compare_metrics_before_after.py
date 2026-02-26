"""
Verification Tool — compare_metrics_before_after
Diff key metrics snapshot taken before action vs current state.
"""

from typing import Dict, Any, Optional

import requests
from langchain_core.tools import tool

from app.core.settings import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_METRIC_QUERIES = {
    "error_rate": (
        'sum(rate(http_requests_total{{job="{svc}", status=~"5.."}}[{dur}]))'
        ' / '
        'sum(rate(http_requests_total{{job="{svc}"}}[{dur}]))'
    ),
    "latency_p99": (
        'histogram_quantile(0.99, sum('
        'rate(http_request_duration_seconds_bucket{{job="{svc}"}}[{dur}])) by (le))'
    ),
    "cpu_usage": (
        'sum(rate(container_cpu_usage_seconds_total{{'
        'namespace="prod", app="{svc}", image!=""}}[{dur}]))'
    ),
}


def _query_value(query: str) -> Optional[float]:
    try:
        resp = requests.get(
            f"{settings.PROMETHEUS_URL}/api/v1/query",
            params={"query": query},
            timeout=2,
        )
        resp.raise_for_status()
        data = resp.json()
        if data["status"] == "success" and data["data"]["result"]:
            return float(data["data"]["result"][0]["value"][1])
    except Exception as e:
        logger.error(f"Prometheus query failed: {e}")
    return None


@tool
def compare_metrics_before_after(
    service: str,
    before_minutes_ago: int = 10,
    after_minutes: int = 2,
) -> Dict[str, Any]:
    """
    Diff key metrics snapshot taken before an action vs current state.

    Args:
        service:            Logical service name.
        before_minutes_ago: How many minutes ago the 'before' window ends.
        after_minutes:      Duration of the 'after' (current) window.

    Returns:
        Dict mapping metric names to before/after/delta values.
    """
    before_dur = f"{before_minutes_ago}m"
    after_dur = f"{after_minutes}m"

    diffs: Dict[str, Any] = {}

    for metric, tmpl in _METRIC_QUERIES.items():
        before_q = tmpl.format(svc=service, dur=before_dur)
        after_q = tmpl.format(svc=service, dur=after_dur)

        before_val = _query_value(before_q)
        after_val = _query_value(after_q)

        delta = None
        if before_val is not None and after_val is not None:
            delta = round(after_val - before_val, 6)

        diffs[metric] = {
            "before": before_val,
            "after": after_val,
            "delta": delta,
        }

    return {"service": service, "metrics": diffs}
