from collections import defaultdict
from typing import Dict


class MetricsCollector:
    def __init__(self):
        self._request_count: Dict[str, int] = defaultdict(int)
        self._error_count: Dict[str, int] = defaultdict(int)
        self._latency_buckets: Dict[str, list] = defaultdict(list)

    def inc_request(self, endpoint: str):
        self._request_count[endpoint] += 1

    def inc_error(self, endpoint: str):
        self._error_count[endpoint] += 1

    def record_latency(self, endpoint: str, seconds: float):
        self._latency_buckets[endpoint].append(seconds)

    def snapshot(self) -> str:
        lines = [
            "# HELP lumina_requests_total Total number of requests by endpoint",
            "# TYPE lumina_requests_total counter",
        ]
        for ep, count in sorted(self._request_count.items()):
            lines.append(f'lumina_requests_total{{endpoint="{ep}"}} {count}')

        lines += [
            "",
            "# HELP lumina_errors_total Total number of errors by endpoint",
            "# TYPE lumina_errors_total counter",
        ]
        for ep, count in sorted(self._error_count.items()):
            lines.append(f'lumina_errors_total{{endpoint="{ep}"}} {count}')

        lines += [
            "",
            "# HELP lumina_latency_seconds Request latency in seconds by endpoint",
            "# TYPE lumina_latency_seconds summary",
        ]
        for ep, latencies in sorted(self._latency_buckets.items()):
            if latencies:
                avg = sum(latencies) / len(latencies)
                lines.append(f'lumina_latency_seconds{{endpoint="{ep}",quantile="0.5"}} {avg}')
                lines.append(f'lumina_latency_seconds_count{{endpoint="{ep}"}} {len(latencies)}')

        return "\n".join(lines) + "\n"


_METRICS = MetricsCollector()


def get_metrics_collector() -> MetricsCollector:
    return _METRICS
