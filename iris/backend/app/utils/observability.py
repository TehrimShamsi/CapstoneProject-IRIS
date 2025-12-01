"""
Observability Layer for IRIS (PaperSynth)
Includes:
✔ Structured Logging
✔ Agent-level tracing
✔ Execution timing
✔ Metrics counters
"""

import logging
import os
import time
import uuid
from functools import wraps
from typing import Any, Dict


# ---------------------------------------------------------
# Global Logger
# ---------------------------------------------------------
logger = logging.getLogger("IRIS")
# Allow overriding log level with IRIS_LOG_LEVEL env var for debugging
level_name = os.getenv("IRIS_LOG_LEVEL", "INFO").upper()
logger.setLevel(getattr(logging, level_name, logging.INFO))

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
    out = {k: v for k, v in METRICS.items()}

    # --- Derived analytics from sessions ---
    try:
        from pathlib import Path
        import json

        base = Path(__file__).resolve().parents[2] / "data"
        legacy_base = Path.cwd() / "backend" / "app" / "data"

        session_paths = []
        for p in [base, legacy_base]:
            sp = p / "sessions"
            if sp.exists():
                session_paths.extend(list(sp.glob("*.json")))

        # Aggregations
        claims_over_time = {}  # date -> count
        confidence_values = []
        method_freq = {}

        for sfile in session_paths:
            try:
                s = json.loads(sfile.read_text(encoding="utf-8"))
            except Exception:
                continue

            papers = s.get("papers", {}) or {}
            for pid, pentry in papers.items():
                added = pentry.get("added_at") or s.get("updated_at") or s.get("created_at")
                date_key = None
                if added:
                    date_key = added.split("T")[0]
                analysis = pentry.get("analysis") or {}
                claims = analysis.get("claims") if isinstance(analysis, dict) else []
                # Count claims
                if date_key:
                    claims_over_time[date_key] = claims_over_time.get(date_key, 0) + (len(claims) if claims else 0)

                if claims:
                    for c in claims:
                        # confidence
                        try:
                            conf = float(c.get("confidence", 0.0))
                            confidence_values.append(max(0, min(1, conf)))
                        except Exception:
                            pass
                        # methods
                        for m in c.get("methods", []) or []:
                            method_freq[m] = method_freq.get(m, 0) + 1

        # Convert claims_over_time to sorted list
        cot_list = []
        for k in sorted(claims_over_time.keys()):
            cot_list.append({"time": k, "label": k, "count": claims_over_time[k]})

        out["claims_over_time"] = cot_list
        out["confidence_distribution"] = confidence_values
        out["method_frequency"] = method_freq

    except Exception:
        # Best-effort: if aggregation fails, return base metrics only
        out.setdefault("claims_over_time", [])
        out.setdefault("confidence_distribution", [])
        out.setdefault("method_frequency", {})

    # --- Agent performance summary ---
    perf = {}
    try:
        calls = METRICS.get("agent_calls", {})
        errors = METRICS.get("agent_errors", {})
        lat = METRICS.get("agent_latency", {})
        for agent_name, calls_list in calls.items():
            total_calls = sum(calls_list) if isinstance(calls_list, list) else calls_list
            total_errors = sum(errors.get(agent_name, [])) if isinstance(errors.get(agent_name, []), list) else errors.get(agent_name, 0)
            lat_list = lat.get(agent_name, []) or []
            avg_latency = (sum(lat_list) / len(lat_list)) if lat_list else None
            perf[agent_name] = {
                "calls": int(total_calls) if total_calls is not None else 0,
                "errors": int(total_errors) if total_errors is not None else 0,
                "avg_latency": float(avg_latency) if avg_latency is not None else None,
            }
    except Exception:
        perf = {}

    out["agent_performance"] = perf

    return out
