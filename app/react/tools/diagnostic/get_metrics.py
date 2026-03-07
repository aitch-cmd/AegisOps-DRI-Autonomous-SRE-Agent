from typing import Dict, Union, List

import requests
from langchain_core.tools import tool

from app.core.settings import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


@tool
def get_metrics(service_name: str, lookback_minutes: int = 5) -> Dict[str, Union[float, str]]:
    """
    Query Prometheus for CPU, memory, error rate, and latency for a service.

    Args:
        service_name: The name of the service to query (matched via app label).
        lookback_minutes: The number of minutes to look back for metrics.

    Returns:
        A dictionary containing aggregated service-level metrics.
    """
    base_url = settings.PROMETHEUS_URL
    duration = f"{lookback_minutes}m"

    logger.info(f"Fetching metrics for service: {service_name} with lookback: {lookback_minutes}m")

    queries = {
        "cpu_usage": (
            f'sum(rate(container_cpu_usage_seconds_total{{'
            f'namespace="prod", app="{service_name}", image!=""}}'
            f'[{duration}]))'
        ),

        "memory_usage": (
            f'avg_over_time(container_memory_working_set_bytes{{'
            f'namespace="prod", app="{service_name}"}}'
            f'[{duration}])'
        ),

        "error_rate": (
            f'sum(rate(http_requests_total{{'
            f'job="{service_name}", status=~"5.."}}'
            f'[{duration}]))'
            f' / '
            f'sum(rate(http_requests_total{{'
            f'job="{service_name}"}}'
            f'[{duration}]))'
        ),

        "latency_p99": (
            f'histogram_quantile(0.99, sum('
            f'rate(http_request_duration_seconds_bucket{{'
            f'job="{service_name}"}}'
            f'[{duration}])) by (le))'
        ),
    }

    results = {}

    for metric_name, query in queries.items():
        try:
            logger.debug(f"Querying {metric_name} for {service_name}")
            response = requests.get(
                f"{base_url}/api/v1/query",
                params={"query": query},
                timeout=2,
            )
            response.raise_for_status()
            data = response.json()

            if data["status"] == "success" and data["data"]["result"]:
                values: List[float] = []
                for result in data["data"]["result"]:
                    try:
                        values.append(float(result["value"][1]))
                    except (ValueError, IndexError):
                        continue

                if values:
                    results[metric_name] = sum(values)
                else:
                    results[metric_name] = "N/A"
            else:
                results[metric_name] = "N/A"

        except requests.exceptions.Timeout:
            logger.error(f"Timeout querying {metric_name} for {service_name}")
            results[metric_name] = f"WARNING: Prometheus query timed out. The metrics server might be down. Attempt to use get_logs or check_service_health instead."
        except Exception as e:
            logger.error(f"Error querying {metric_name} for {service_name}: {e}")
            results[metric_name] = f"WARNING: Failed to query {metric_name}. Error: {str(e)}. Use alternative diagnostic tools."

    logger.info(f"Metrics retrieval completed for {service_name}: {results}")
    return results