# backend/app/agents/analysis_agent.py
import os
import json
import re
from typing import List, Dict, Any, Optional

import google.generativeai as genai

from app.utils.observability import agent_call
from app.tools.pdf_processor import PDFProcessor

# Configure Gemini from env var - USE GOOGLE_API_KEY (not GEMINI_API_KEY)
GOOGLE_KEY = os.getenv("GOOGLE_API_KEY")
if GOOGLE_KEY:
    genai.configure(api_key=GOOGLE_KEY)
else:
    # If not set, we'll still allow the module to import; runtime calls will error clearly.
    pass


def _clean_model_text(text: str) -> str:
    """
    Remove markdown code fences and leading 'json' token if present.
    Return cleaned string likely to parse as JSON.
    """
    if not text:
        return text
    # Remove triple-backtick blocks and keep the inner content if needed
    if "```" in text:
        parts = text.split("```")
        # find a part that looks like JSON
        for part in parts:
            p = part.strip()
            if p.startswith("{") or p.startswith("["):
                text = p
                break
        else:
            # fallback to the middle part
            text = parts[1] if len(parts) > 1 else parts[0]
    # Remove a leading "json" marker
    text = re.sub(r'^\s*json\s*', '', text, flags=re.IGNORECASE)
    return text.strip()


class AnalysisAgent:
    """
    Gemini-powered AnalysisAgent.
    Extracts structured claims, methods and metrics from PDF text.
    """

    def __init__(self, model_name: str = None):
        self.pdf = PDFProcessor()
        # Use GOOGLE_MODEL from env, fallback to gemini-2.5-flash
        self.model_name = model_name or os.getenv("GOOGLE_MODEL", "gemini-2.5-flash")
        # Create a model handle if configured
        try:
            self.model = genai.GenerativeModel(self.model_name)
        except Exception:
            self.model = None

    @agent_call("AnalysisAgent")
    def analyze(self, paper_id: str, pdf_path: str, trace_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Main entry: extract text from pdf_path, chunk it, run Gemini to extract
        structured claims from the top-K chunks, and return analysis JSON.
        """
        full_text = self.pdf.extract_text(pdf_path)
        chunks = self._chunk_text(full_text, chunk_size_chars=1500, overlap_chars=200)

        claims: List[Dict[str, Any]] = []
        max_chunks = 6  # keep within free-tier / token limits
        for i, chunk in enumerate(chunks[:max_chunks]):
            claim_data = self._extract_with_gemini(chunk, chunk_id=i)
            if claim_data:
                claim_obj = {
                    "claim_id": f"{paper_id}_claim_{i}",
                    "text": claim_data.get("text"),
                    "confidence": float(claim_data.get("confidence", 0.0)),
                    "provenance": claim_data.get("provenance", [f"chunk_{i}"]),
                    "methods": claim_data.get("methods", []),
                    "metrics": claim_data.get("metrics", []),
                }
                claims.append(claim_obj)

        analysis = {
            "paper_id": paper_id,
            "title": None,
            "num_chunks_analyzed": min(len(chunks), max_chunks),
            "num_claims": len(claims),
            "claims": claims
        }
        return analysis

    def _chunk_text(self, text: str, chunk_size_chars: int = 1500, overlap_chars: int = 200) -> List[str]:
        """
        Simple char-based chunker. Preserves sentence boundaries when possible.
        """
        if not text:
            return []
        text = text.replace("\r", " ")
        chunks = []
        start = 0
        N = len(text)
        while start < N:
            end = min(start + chunk_size_chars, N)
            # try to extend to sentence boundary
            if end < N:
                next_period = text.rfind(".", start, end)
                if next_period and next_period > start:
                    end = next_period + 1
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            start = end - overlap_chars if end - overlap_chars > start else end
        return chunks

    def _extract_with_gemini(self, text: str, chunk_id: int) -> Dict[str, Any]:
        """
        Use Gemini to extract a single key claim and structured fields.
        Returns dict with keys: text, confidence, methods, metrics, provenance
        """
        # Build the prompt — keep concise to save tokens
        prompt = f"""
Extract ONE key research claim from the following text. Return ONLY valid JSON (no explanation).

Text (truncated):
{text[:1200]}

Desired JSON:
{{
  "text": "string - the claim as one clear sentence",
  "confidence": 0.0,
  "methods": ["method1", "method2"],
  "metrics": ["accuracy", "f1"]
}}

Return JSON ONLY.
"""

        # If model not configured, fallback to heuristic
        if self.model is None:
            return self._fallback_extraction(text, chunk_id)

        try:
            response = self.model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.15,
                    max_output_tokens=280
                )
            )
            raw = response.text or ""
            cleaned = _clean_model_text(raw)
            parsed = json.loads(cleaned)
            # Ensure types
            parsed.setdefault("provenance", [f"chunk_{chunk_id}"])
            parsed.setdefault("methods", parsed.get("methods") or [])
            parsed.setdefault("metrics", parsed.get("metrics") or [])
            # normalize confidence
            try:
                parsed["confidence"] = float(parsed.get("confidence", 0.0))
            except Exception:
                parsed["confidence"] = 0.0
            return parsed
        except Exception as e:
            # log via observability (agent_call will capture exception logs) and fallback
            return self._fallback_extraction(text, chunk_id)

    def _fallback_extraction(self, text: str, chunk_id: int) -> Dict[str, Any]:
        """
        Conservative fallback: return a short first-sentence claim with low confidence.
        """
        first_sentence = text.split(".")[0].strip() if "." in text else text[:200].strip()
        return {
            "text": first_sentence,
            "confidence": 0.35,
            "provenance": [f"chunk_{chunk_id}"],
            "methods": [],
            "metrics": []
        }