# backend/app/agents/synthesis_agent.py
import os
import json
import google.generativeai as genai
from typing import List, Dict, Any, Optional

from app.utils.observability import agent_call

GEMINI_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_KEY:
    genai.configure(api_key=GEMINI_KEY)

def _clean_model_text(text: str) -> str:
    # same helper as analysis agent (duplicated for module isolation)
    if not text:
        return text
    if "```" in text:
        parts = text.split("```")
        for part in parts:
            p = part.strip()
            if p.startswith("{") or p.startswith("["):
                text = p
                break
        else:
            text = parts[1] if len(parts) > 1 else parts[0]
    text = text.strip()
    if text.lower().startswith("json"):
        text = text[4:].strip()
    return text

class SynthesisAgent:
    """
    Gemini-powered SynthesisAgent.
    Produces consensus statements and contradiction pairs from a list of analyses.
    """

    def __init__(self, model_name: str = "gemini-1.5-flash"):
        try:
            self.model = genai.GenerativeModel(model_name)
        except Exception:
            self.model = None

    @agent_call("SynthesisAgent")
    def synthesize(self, analyses: List[Dict[str, Any]], trace_id: Optional[str] = None) -> Dict[str, Any]:
        """
        analyses: list of analysis dicts (each with paper_id and claims list)
        """
        # Collect claims (limit to first 30 claims to stay within token limits)
        claims_for_prompt = []
        for a in analyses:
            paper = a.get("paper_id", "unknown")
            for c in a.get("claims", [])[:10]:
                claims_for_prompt.append({
                    "paper_id": paper,
                    "claim_id": c.get("claim_id"),
                    "text": c.get("text", "")
                })
        # unique id prefix for response mapping
        max_claims = 30
        claims_for_prompt = claims_for_prompt[:max_claims]

        # Build a compact prompt listing the claims
        claims_text = "\n".join([f"{i+1}. ({c['paper_id']}) {c['text']}" for i, c in enumerate(claims_for_prompt)])

        # Consensus prompt
        consensus_prompt = f"""
Analyze the following list of research claims and IDENTIFY CONSENSUS statements
(i.e., claims that are supported by similar claims from 2+ different papers).
Return ONLY a JSON array of consensus objects in the format:

[
  {{
    "text": "consensus statement",
    "papers": ["paper_id1", "paper_id2"],
    "average_confidence": 0.0
  }},
  ...
]

Claims:
{claims_text}

Return JSON only.
"""

        contradictions_prompt = f"""
Analyze the following list of research claims and IDENTIFY CONTRADICTIONS
(pairs of claims from different papers that directly conflict). Return ONLY a JSON array:

[
  {{
    "claim_a": "text of claim A",
    "paper_a": "paper_idA",
    "claim_b": "text of claim B",
    "paper_b": "paper_idB"
  }},
  ...
]

Claims:
{claims_text}

Return JSON only.
"""

        consensus = self._call_gemini_json(consensus_prompt, default=[])
        contradictions = self._call_gemini_json(contradictions_prompt, default=[])

        result = {
            "num_papers": len(analyses),
            "num_consensus": len(consensus),
            "num_contradictions": len(contradictions),
            "consensus": consensus,
            "contradictions": contradictions
        }
        return result

    def _call_gemini_json(self, prompt: str, default: Any):
        """
        Helper to call Gemini and parse JSON safely. Falls back to default on error.
        """
        if self.model is None:
            return default
        try:
            response = self.model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.15,
                    max_output_tokens=400
                )
            )
            raw = response.text or ""
            cleaned = _clean_model_text(raw)
            parsed = json.loads(cleaned)
            return parsed
        except Exception:
            return default
