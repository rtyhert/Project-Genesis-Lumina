import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "lumina-py"))
os.environ["LUMINA_MOCK"] = "1"

# Test 1: thread_pool
from src.thread_pool import get_io_executor, shutdown_io_executor
e = get_io_executor()
assert e._max_workers == 4
print(f"thread_pool OK (workers={e._max_workers})")

# Test 2: metrics
from src.metrics import get_metrics_collector
mc = get_metrics_collector()
mc.inc_request("/test")
mc.inc_error("/test")
mc.record_latency("/test", 0.1)
snap = mc.snapshot()
assert "lumina_requests_total" in snap
assert "lumina_errors_total" in snap
assert "lumina_latency_seconds" in snap
print("metrics OK")

# Test 3: config_schema with monitoring
from src.config_schema import validate_config
cfg = validate_config({"server": {"host": "0.0.0.0", "port": 50051, "rest_port": 8000}})
assert cfg.monitoring.enabled == False
assert cfg.monitoring.port == 9090
print("config_schema OK (monitoring field present)")

# Test 4: crew_manager import
from src.crew_manager import CrewManager
print("crew_manager import OK")

# Test 5: stt_engine import
from src.stt_engine import STTEngine
print("stt_engine import OK")

print("\n=== ALL CHECKS PASSED ===")
