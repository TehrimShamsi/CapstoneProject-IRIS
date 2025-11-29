# backend/app/agents/synthesis_agent.py
import os
import json
import google.generativeai as genai
from typing import List, Dict, Any, Optional

from app.utils.observability import agent_call

# USE GOOGLE_API_KEY (not GEMINI_API_KEY)
GOOGLE_KEY = os.getenv("GOOGLE_API_KEY")
if GOOGLE_KEY:
    genai.configure(api_key=GOOGLE_KEY)

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

    def __init__(self, model_name: str = None):
        # Use GOOGLE_MODEL from env, fallback to gemini-2.5-flash
        self.model_name = model_name or os.getenv("GOOGLE_MODEL", "gemini-2.5-flash")
        try:
            self.model = genai.GenerativeModel(self.model_name)
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

        consensus = self._call_gemini_json(consensus_prompt, default=None)
        contradictions = self._call_gemini_json(contradictions_prompt, default=None)

        # If Gemini isn't available or returned nothing, fall back to a lightweight heuristic
        if consensus is None or contradictions is None:
            consensus, contradictions = self._heuristic_synthesis(claims_for_prompt)

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

    def _heuristic_synthesis(self, claims: List[Dict[str, str]]):
        """
        Lightweight heuristic synthesizer used when Gemini is unavailable.
                - Consensus: find claim texts that share >=2 normalized tokens across papers (configurable).
                - Contradictions: detect polarity contradictions (e.g. 'increase' vs 'decrease', 'improve' vs 'worse'),
                    and negation-based contradictions where one claim negates an otherwise similar claim.
                This is intentionally simple but useful for local dev when the model is not available.
        """
        import re
        from collections import defaultdict

        def normalize(text):
            t = text.lower()
            t = re.sub(r"[^a-z0-9\s]", " ", t)
            toks = [w for w in t.split() if len(w) > 2]
            return toks

        # Build token sets per claim
        token_sets = []
        for c in claims:
            toks = set(normalize(c.get("text", "")))
            token_sets.append((c.get("paper_id"), c.get("claim_id"), c.get("text", ""), toks))

        # Consensus: if two claims share >=N tokens (configurable), default 2
        consensus_map = {}
        token_threshold = int(os.getenv("ANALYSIS_CONSENSUS_TOKEN_THRESHOLD", "2"))
        strict_cross = os.getenv("ANALYSIS_STRICT_CROSSPAPER", "0") == "1"
        for i in range(len(token_sets)):
            pid_i, cid_i, text_i, toks_i = token_sets[i]
            for j in range(i + 1, len(token_sets)):
                pid_j, cid_j, text_j, toks_j = token_sets[j]
                if strict_cross and pid_i == pid_j:
                    continue
                common = toks_i & toks_j
                if len(common) >= token_threshold:
                    key = ' || '.join(sorted([pid_i, pid_j])) + ' :: ' + ' / '.join(sorted(list(common))[:5])
                    if key not in consensus_map:
                        consensus_map[key] = {
                            "text": f"{text_i} / {text_j}",
                            "papers": sorted([pid_i, pid_j]),
                            "average_confidence": 0.5
                        }

        consensus = list(consensus_map.values())

        # Contradictions: check polarity pairs and negation-based contradictions.
        polarity_pairs = [ ("increase","decrease"), ("improve","worse"), ("higher","lower"), ("positive","negative"), ("gain","loss"), ("better","worse") ]
        negation_terms = {"not","no","none","without","lack","fails","failed","doesn't","doesnt","cannot","can't","cant"}
        contradictions = []
        for i in range(len(token_sets)):
            pid_i, cid_i, text_i, toks_i = token_sets[i]
            for j in range(i + 1, len(token_sets)):
                pid_j, cid_j, text_j, toks_j = token_sets[j]
                if strict_cross and pid_i == pid_j:
                    continue
                # require at least some overlap to consider contradiction (helps avoid spurious matches)
                common = toks_i & toks_j
                if len(common) < 1:
                    continue
                a_text = ' '.join(toks_i)
                b_text = ' '.join(toks_j)
                found = False
                for a,b in polarity_pairs:
                    if (a in a_text and b in b_text) or (b in a_text and a in b_text):
                        contradictions.append({
                            "claim_a": text_i,
                            "paper_a": pid_i,
                            "claim_b": text_j,
                            "paper_b": pid_j
                        })
                        found = True
                        break
                if found:
                    continue
                # Negation-based: one claim contains negation while the other does not and they share tokens
                a_neg = any(nt in a_text for nt in negation_terms)
                b_neg = any(nt in b_text for nt in negation_terms)
                if a_neg != b_neg and len(common) >= 2:
                    contradictions.append({
                        "claim_a": text_i,
                        "paper_a": pid_i,
                        "claim_b": text_j,
                        "paper_b": pid_j
                    })

        return consensus, contradictions