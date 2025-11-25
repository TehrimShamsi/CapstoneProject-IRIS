"""
Observability Layer for IRIS (PaperSynth)
Includes:
✔ Structured Logging
✔ Agent-level tracing
✔ Execution timing
✔ Metrics counters
"""

import logging
import time
import uuid
from functools import wraps
from typing import Any, Dict


# ---------------------------------------------------------
# Global Logger
# ---------------------------------------------------------
logger = logging.getLogger("IRIS")
logger.setLevel(logging.INFO)

handler = logging.StreamHandler()
formatter = logging.Formatter(
    '[%(asctime)s] %(levelname)s | %(message)s'
)
handler.setFormatter(formatter)
logger.addHandler(handler)


# ---------------------------------------------------------
# Metrics Store (simple, no DB needed)
# ---------------------------------------------------------
METRICS = {
    "agent_calls": {},        # {"AnalysisAgent.analyze": 3, ...}
    "agent_errors": {},       # {"SynthesisAgent.synthesize": 1}
    "agent_latency": {}       # {"AnalysisAgent.analyze": [0.43, 0.29]}
}


def record_metric(metric_name: str, key: str, value: Any):
    if metric_name not in METRICS:
        METRICS[metric_name] = {}

    if key not in METRICS[metric_name]:
        METRICS[metric_name][key] = []

    METRICS[metric_name][key].append(value)


# ---------------------------------------------------------
# Trace ID Generator
# ---------------------------------------------------------
def new_trace_id() -> str:
    return str(uuid.uuid4())[:8]


# ---------------------------------------------------------
# Decorator: agent_call
# Adds:
# ✔ Logging
# ✔ Latency measurement
# ✔ Error tracking
# ✔ Trace ID propagation
# ---------------------------------------------------------
def agent_call(agent_name: str):
    """Decorator for logging, metrics & tracing."""

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            trace_id = kwargs.get("trace_id") or new_trace_id()
            func_name = f"{agent_name}.{func.__name__}"

            logger.info(f"🟦 [{trace_id}] Starting {func_name}")

            start_time = time.time()

            try:
                result = func(*args, **kwargs)

                elapsed = round(time.time() - start_time, 3)
                logger.info(f"🟩 [{trace_id}] Completed {func_name} in {elapsed}s")

                # Metrics
                record_metric("agent_calls", func_name, 1)
                record_metric("agent_latency", func_name, elapsed)

                return result

            except Exception as e:
                logger.error(f"🟥 [{trace_id}] Error in {func_name}: {str(e)}")

                record_metric("agent_errors", func_name, 1)

                raise e

        return wrapper

    return decorator


# ---------------------------------------------------------
# SHOW METRICS (for demo & debugging)
# ---------------------------------------------------------
def print_metrics():
    logger.info("\n📊 AGENT METRICS\n-----------------------------")
    for category, values in METRICS.items():
        logger.info(f"▶ {category}:")
        for k, v in values.items():
            logger.info(f"   • {k}: {v}")


def get_metrics() -> Dict[str, Any]:
    """Return a shallow copy of current metrics for API endpoints."""
    # Return the metrics structure (shallow copy to avoid external mutation)
    return {k: v for k, v in METRICS.items()}
