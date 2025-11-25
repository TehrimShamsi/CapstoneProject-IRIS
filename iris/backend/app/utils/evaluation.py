"""
Evaluation utilities for IRIS (PaperSynth)

Provides:
- AgentEvaluator: evaluates analysis JSON objects and synthesis JSON objects.
- report generation and JSON export.
- simple heuristics for provenance coverage, confidence averages,
  consensus/contradiction counts, hallucination detection.

Usage:
    from app.utils.evaluation import AgentEvaluator
    evaluator = AgentEvaluator()
    a_metrics = evaluator.evaluate_analysis(analysis_json)
    s_metrics = evaluator.evaluate_synthesis(synthesis_json, analyses_list)
    evaluator.export_report(report_dict, "eval_report.json")
"""

from __future__ import annotations
import json
import statistics
from pathlib import Path
from typing import Dict, Any, List, Optional
from app.utils.observability import agent_call, logger

# -------------------------
# Helpers
# -------------------------
def safe_mean(values: List[float], default: float = 0.0) -> float:
    if not values:
        return default
    try:
        return float(statistics.mean(values))
    except Exception:
        return default

# -------------------------
# Evaluator Class
# -------------------------
class AgentEvaluator:
    """
    Evaluates:
    - Analysis JSONs (provenance coverage, claim_count, avg_confidence, hallucination_rate)
    - Synthesis JSONs (consensus_count, contradiction_count, confidence_overall consistency)
    """

    def __init__(self):
        # Configuration thresholds
        self.min_prov_per_claim = 1  # how many provenance entries required to count as "covered"
        self.hallucination_confidence_threshold = 0.5  # low-confidence claims flagged

    # -------------------------
    # Analysis evaluation
    # -------------------------
    @agent_call("AgentEvaluator")
    def evaluate_analysis(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """
        Input: analysis JSON (validated)
        Output: metrics dict
        """
        paper_id = analysis.get("paper_id", "unknown")
        claims = analysis.get("claims", []) or []
        methods = analysis.get("methods", []) or []
        metrics = analysis.get("metrics", []) or []

        # provenance coverage: % of claims that have >= min_prov_per_claim provenance entries
        total_claims = len(claims)
        claims_with_prov = 0
        confidences = []

        hallucinated_claims = 0

        for c in claims:
            prov = c.get("provenance", []) or []
            if len(prov) >= self.min_prov_per_claim:
                claims_with_prov += 1
            # confidence
            conf = c.get("confidence")
            if isinstance(conf, (int, float)):
                confidences.append(float(conf))
            else:
                # if no numeric confidence, treat as low
                confidences.append(0.0)

            # hallucination heuristic: low confidence and no provenance
            if (not prov or len(prov) < self.min_prov_per_claim) and (not conf or conf < self.hallucination_confidence_threshold):
                hallucinated_claims += 1

        provenance_coverage = (claims_with_prov / total_claims) if total_claims else 0.0
        avg_confidence = safe_mean(confidences, default=0.0)

        # Basic method/metric counts
        method_count = len(methods)
        metrics_count = len(metrics)

        result = {
            "paper_id": paper_id,
            "total_claims": total_claims,
            "claims_with_provenance": claims_with_prov,
            "provenance_coverage": round(provenance_coverage, 4),
            "avg_claim_confidence": round(avg_confidence, 4),
            "hallucinated_claims": hallucinated_claims,
            "method_count": method_count,
            "metrics_count": metrics_count
        }

        logger.info(f"[Evaluator] Analysis metrics for {paper_id}: {result}")
        return result

    # -------------------------
    # Synthesis evaluation
    # -------------------------
    @agent_call("AgentEvaluator")
    def evaluate_synthesis(self, synthesis: Dict[str, Any], analyses: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """
        Evaluates synthesis JSON produced by SynthesisAgent.
        - Counts consensus statements and contradictions.
        - Checks that each consensus has >= 2 supporting_claims (rule).
        - Computes coverage of consensus claims across analyses (how many analyses contributed).
        - Returns consistency checks and a scored summary.
        """
        topic = synthesis.get("topic", "unknown")
        consensus = synthesis.get("consensus_statements", []) or []
        contradictions = synthesis.get("contradictions", []) or []
        confidence_overall = synthesis.get("confidence_overall", 0.0) or 0.0

        # consensus checks: ensure each consensus has >= 2 supporting claims
        consensus_checks = []
        for c in consensus:
            sc = c.get("supporting_claims", []) or []
            ok = len(sc) >= 2
            consensus_checks.append({"statement": c.get("statement", "")[:120], "supporting_count": len(sc), "valid": ok})

        # contradiction checks: ensure pairs are validly formatted
        contradiction_checks = []
        for cons in contradictions:
            pairs = cons.get("paper_pairs", []) or []
            valid = len(pairs) >= 2
            contradiction_checks.append({"description": cons.get("description", "")[:120], "pair_count": len(pairs), "valid": valid})

        # If analyses provided, compute how many papers contributed to consensus
        coverage_per_consensus = []
        if analyses:
            paper_ids = set(a.get("paper_id") for a in analyses)
            for c in consensus:
                supporting_claims = c.get("supporting_claims", []) or []
                contributing_papers = set(sc.get("paper_id") for sc in supporting_claims if sc.get("paper_id"))
                coverage_per_consensus.append({
                    "statement": c.get("statement", "")[:120],
                    "num_contributing_papers": len(contributing_papers),
                    "pct_of_total_papers": round((len(contributing_papers) / len(paper_ids) if paper_ids else 0.0), 4)
                })

        result = {
            "topic": topic,
            "consensus_count": len(consensus),
            "contradiction_count": len(contradictions),
            "consensus_checks": consensus_checks,
            "contradiction_checks": contradiction_checks,
            "coverage_per_consensus": coverage_per_consensus,
            "confidence_overall": round(float(confidence_overall), 4)
        }

        logger.info(f"[Evaluator] Synthesis metrics for topic '{topic}': {result}")
        return result

    # -------------------------
    # Aggregate report generation
    # -------------------------
    def generate_report(self, analyses_metrics: List[Dict[str, Any]], synthesis_metrics: Dict[str, Any]) -> Dict[str, Any]:
        """
        Combine per-paper analysis metrics and synthesis metrics into a single report
        that can be exported or displayed in the UI.
        """
        total_papers = len(analyses_metrics)
        avg_prov_cov = safe_mean([m.get("provenance_coverage", 0.0) for m in analyses_metrics])
        avg_confidence = safe_mean([m.get("avg_claim_confidence", 0.0) for m in analyses_metrics])
        total_hallucinated = sum(m.get("hallucinated_claims", 0) for m in analyses_metrics)
        total_claims = sum(m.get("total_claims", 0) for m in analyses_metrics)

        report = {
            "summary": {
                "total_papers": total_papers,
                "total_claims": total_claims,
                "avg_provenance_coverage": round(avg_prov_cov, 4),
                "avg_claim_confidence": round(avg_confidence, 4),
                "total_hallucinated_claims": total_hallucinated
            },
            "analyses": analyses_metrics,
            "synthesis": synthesis_metrics
        }
        return report

    # -------------------------
    # Export report to JSON
    # -------------------------
    def export_report(self, report: Dict[str, Any], path: str = "eval_report.json") -> None:
        Path(path).write_text(json.dumps(report, indent=2))
        logger.info(f"[Evaluator] Exported evaluation report to {path}")
