# backend/app/agents/analysis_agent.py
import os
import json
import re
from typing import List, Dict, Any, Optional

import google.generativeai as genai
import time
import traceback

from app.utils.observability import agent_call, logger
from app.tools.pdf_processor import PDFProcessor
from app.storage.vector_db import get_vector_db
from app.protocol.a2a_messages import A2AAgent, MessageRouter, create_trace_id

# Configure Gemini from env var
GOOGLE_KEY = os.getenv("GOOGLE_API_KEY")
if GOOGLE_KEY:
    genai.configure(api_key=GOOGLE_KEY)
else:
    pass


def _clean_model_text(text: str) -> str:
    """
    Remove markdown code fences and leading 'json' token if present.
    Return cleaned string likely to parse as JSON.
    """
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
    text = re.sub(r'^\s*json\s*', '', text, flags=re.IGNORECASE)
    return text.strip()


def _attempt_extract_json(text: str) -> Optional[dict]:
    """
    Try several heuristics to extract JSON from an arbitrary model string.
    Returns a parsed dict on success, or None on failure.
    """
    if not text:
        return None
    # First, try direct load
    try:
        return json.loads(text)
    except Exception:
        pass

    # Try to find a JSON substring by looking for first { ... } or [ ... ]
    # This is a best-effort approach: grab from first opening brace to last closing brace.
    for open_ch, close_ch in (("{", "}"), ("[", "]")):
        try:
            start = text.find(open_ch)
            end = text.rfind(close_ch)
            if start != -1 and end != -1 and end > start:
                candidate = text[start:end + 1]
                try:
                    return json.loads(candidate)
                except Exception:
                    # try cleaning candidate from markdown code fences
                    cand_clean = _clean_model_text(candidate)
                    try:
                        return json.loads(cand_clean)
                    except Exception:
                        continue
        except Exception:
            continue

    # Try to find a JSON-like substring using regex (non-greedy for braces)
    try:
        m = re.search(r"(\{(?:.|\n)*?\})", text)
        if m:
            try:
                return json.loads(m.group(1))
            except Exception:
                pass
    except Exception:
        pass

    return None


class AnalysisAgent(A2AAgent):
    """
    Gemini-powered AnalysisAgent with A2A protocol support and vector embeddings.
    Extracts structured claims, methods and metrics from PDF text.
    """

    def __init__(self, model_name: str = None, router: Optional[MessageRouter] = None):
        # Initialize A2A support if router provided
        if router:
            super().__init__("AnalysisAgent", router)
        else:
            self.agent_name = "AnalysisAgent"
            self.router = None
        
        self.pdf = PDFProcessor()
        self.model_name = model_name or os.getenv("GOOGLE_MODEL", "gemini-2.5-flash")
        
        # Initialize vector DB
        self.vector_db = get_vector_db()
        
        # Create model handle if configured
        try:
            self.model = genai.GenerativeModel(self.model_name)
        except Exception:
            self.model = None
        # cooldown timestamp to avoid repeated 429 retries
        self._cooldown_until = 0.0
        # Try to provision a lighter fallback model (used before the conservative local fallback)
        self.fallback_model = None
        try:
            lite_name = os.getenv("GOOGLE_LITE_FALLBACK_MODEL", "gemini-2.5-flash-lite")
            # only create if different from primary
            if lite_name != self.model_name:
                try:
                    self.fallback_model = genai.GenerativeModel(lite_name)
                except Exception:
                    self.fallback_model = None
        except Exception:
            self.fallback_model = None

    @agent_call("AnalysisAgent")
    def analyze(self, paper_id: str, pdf_path: str, trace_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Main entry: extract text from pdf_path, chunk it, run Gemini to extract
        structured claims from the top-K chunks, generate embeddings, and return analysis JSON.
        """
        trace_id = trace_id or create_trace_id()
        
        # Send status update via A2A if available
        if self.router:
            self.send_status("processing", progress=0.0, trace_id=trace_id)
        
        # Extract full text
        full_text = self.pdf.extract_text(pdf_path)
        chunks = self._chunk_text(full_text, chunk_size_chars=1500, overlap_chars=200)
        
        # Add chunks to vector DB for semantic search
        try:
            logger.info(f"Adding {len(chunks)} chunks to vector DB for paper {paper_id}")
            self.vector_db.add_paper_chunks(
                paper_id=paper_id,
                chunks=chunks,
                paper_metadata={"pdf_path": pdf_path}
            )
            # Save index after adding new paper
            self.vector_db.save()
        except Exception as e:
            logger.warning(f"Failed to add paper to vector DB: {e}")

        claims: List[Dict[str, Any]] = []
        max_chunks = int(os.getenv("ANALYSIS_MAX_CHUNKS", "6"))
        
        for i, chunk in enumerate(chunks[:max_chunks]):
            # Update progress
            if self.router:
                progress = (i + 1) / max_chunks
                self.send_status("processing", progress=progress, trace_id=trace_id)
            
            claim_data = self._extract_with_gemini(chunk, chunk_id=i)
            if claim_data:
                claim_obj = {
                    "claim_id": f"{paper_id}_claim_{i}",
                    "text": claim_data.get("text"),
                    "confidence": float(claim_data.get("confidence", 0.0)),
                    "provenance": claim_data.get("provenance", [f"chunk_{i}"]),
                    "methods": claim_data.get("methods", []),
                    "metrics": claim_data.get("metrics", []),
                    "used_fallback": bool(claim_data.get("used_fallback", False)),
                }
                claims.append(claim_obj)

        analysis = {
            "paper_id": paper_id,
            "title": None,
            "num_chunks_analyzed": min(len(chunks), max_chunks),
            "num_claims": len(claims),
            "claims": claims,
            "used_fallback": any([c.get("used_fallback") for c in claims]),
            "vector_indexed": True  # Flag indicating vector embeddings created
        }
        
        # Send completion status via A2A
        if self.router:
            self.send_status("idle", progress=1.0, trace_id=trace_id)
            self.send_result(
                to_agent="Orchestrator",
                task_id=f"analyze_{paper_id}",
                result=analysis,
                trace_id=trace_id
            )
        
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

        # Helper to call a model instance and parse result. Returns dict or raises.
        def _call_model_and_parse(model_instance):
            response = model_instance.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.15,
                    max_output_tokens=280
                )
            )
            raw_local = ""
            try:
                if getattr(response, 'text', None):
                    raw_local = response.text or ""
                else:
                    parts_list = []
                    if hasattr(response, 'result') and getattr(response.result, 'parts', None):
                        for p in response.result.parts:
                            if isinstance(p, dict):
                                parts_list.append(p.get('text', ''))
                            else:
                                parts_list.append(str(p))
                    elif getattr(response, 'candidates', None):
                        try:
                            cand = response.candidates[0]
                            content = getattr(cand, 'content', {})
                            parts = getattr(content, 'parts', None) or content.get('parts') if isinstance(content, dict) else None
                            if parts:
                                for p in parts:
                                    if isinstance(p, dict):
                                        parts_list.append(p.get('text', ''))
                                    else:
                                        parts_list.append(str(p))
                        except Exception:
                            pass
                    raw_local = ''.join(parts_list)
                if not raw_local:
                    try:
                        raw_local = str(response)
                    except Exception:
                        raw_local = ""
            except Exception:
                raw_local = ""

            cleaned_local = _clean_model_text(raw_local)
            parsed_local = _attempt_extract_json(cleaned_local)
            if parsed_local is None:
                parsed_local = _attempt_extract_json(str(raw_local))
            if parsed_local is None:
                logger.debug(f"Failed to parse JSON from model response. cleaned='''{cleaned_local}''' raw='''{raw_local}'''")
                raise ValueError("Could not parse JSON from model response")
            return parsed_local

        now = time.time()

        tried_models = []

        # Try primary model first if available and not cooling down
        if self.model is not None and now >= getattr(self, "_cooldown_until", 0.0):
            try:
                parsed = _call_model_and_parse(self.model)
                parsed.setdefault("provenance", [f"chunk_{chunk_id}"])
                parsed.setdefault("methods", parsed.get("methods") or [])
                parsed.setdefault("metrics", parsed.get("metrics") or [])
                parsed.setdefault("used_fallback", False)
                try:
                    parsed["confidence"] = float(parsed.get("confidence", 0.0))
                except Exception:
                    parsed["confidence"] = 0.0
                return parsed
            except Exception as e:
                tried_models.append(("primary", e))
                msg = str(e)
                lower = msg.lower()
                if "quota" in lower or "429" in lower or "rate limit" in lower:
                    retry_secs = None
                    m = re.search(r"please retry in\s*(\d+(?:\.\d+)?)s", msg, flags=re.IGNORECASE)
                    if m:
                        try:
                            retry_secs = float(m.group(1))
                        except Exception:
                            retry_secs = None
                    if retry_secs is None:
                        retry_secs = float(os.getenv("ANALYSIS_QUOTA_COOLDOWN_SECS", "15"))
                    self._cooldown_until = time.time() + retry_secs
                    logger.warning(f"Primary LLM rate-limit detected; cooling down for {retry_secs}s: {msg}")
                else:
                    logger.warning(f"Primary LLM extraction failed: {e}")

        # If primary failed or was unavailable, try lite fallback model if configured
        if getattr(self, 'fallback_model', None) is not None:
            try:
                parsed = _call_model_and_parse(self.fallback_model)
                parsed.setdefault("provenance", [f"chunk_{chunk_id}"])
                parsed.setdefault("methods", parsed.get("methods") or [])
                parsed.setdefault("metrics", parsed.get("metrics") or [])
                parsed.setdefault("used_fallback", False)
                try:
                    parsed["confidence"] = float(parsed.get("confidence", 0.0))
                except Exception:
                    parsed["confidence"] = 0.0
                return parsed
            except Exception as e:
                tried_models.append(("lite", e))
                msg = str(e)
                lower = msg.lower()
                if "quota" in lower or "429" in lower or "rate limit" in lower:
                    retry_secs = float(os.getenv("ANALYSIS_QUOTA_COOLDOWN_SECS", "15"))
                    self._cooldown_until = time.time() + retry_secs
                    logger.warning(f"Lite LLM rate-limit detected; cooling down for {retry_secs}s: {msg}")
                else:
                    logger.warning(f"Lite LLM extraction failed: {e}")

        # All model attempts failed — log debug info and fall back to conservative extraction
        for name, exc in tried_models:
            logger.debug(f"Model attempt '{name}' failed: {exc}")
        logger.info("Using local fallback extraction for chunk %s", chunk_id)
        return self._fallback_extraction(text, chunk_id)

    def _fallback_extraction(self, text: str, chunk_id: int) -> Dict[str, Any]:
        """
        Conservative fallback: return a short first-sentence claim with low confidence.
        """
        import re

        sents = [s.strip() for s in re.split(r'(?<=[.!?])\s+', text.strip()) if s.strip()]

        primary = None
        for s in sents:
            if len(s) > 30:
                primary = s
                break
        if not primary:
            primary = sents[0] if sents else text[:200].strip()

        method_keywords = [
            r'BERT', r'RoBERTa', r'Transformer', r'Transformers', r'CNN', r'RNN', r'LSTM',
            r'GAN', r'SVM', r'reinforcement learning', r'deep learning', r'self-supervised',
            r'contrastive', r'fine-tun', r'pre-train', r'token', r'encoder', r'decoder'
        ]

        methods_found = set()
        for kw in method_keywords:
            try:
                if re.search(kw, text, flags=re.IGNORECASE):
                    methods_found.add(re.sub(r'\\W+$', '', kw))
            except re.error:
                continue

        metrics_found = set()
        for m in re.findall(r"\b\d{1,3}(?:\.\d+)?\s?%", text):
            metrics_found.add(m.strip())
        for metric_kw in [r'accuracy', r'f1', r'precision', r'recall', r'auc', r'mse', r'rmse']:
            if re.search(metric_kw, text, flags=re.IGNORECASE):
                metrics_found.add(metric_kw)

        confidence = 0.35
        if methods_found and metrics_found:
            confidence = 0.55
        elif methods_found or metrics_found:
            confidence = 0.45

        return {
            "text": primary,
            "confidence": confidence,
            "provenance": [f"chunk_{chunk_id}"],
            "methods": list(methods_found),
            "metrics": list(metrics_found),
            "used_fallback": True
        }

    # ============================================
    # A2A Protocol Handlers
    # ============================================
    
    def handle_task(self, message):
        """Handle incoming task messages"""
        task_name = message.payload.get("task_name")
        parameters = message.payload.get("parameters", {})
        
        if task_name == "analyze_paper":
            paper_id = parameters.get("paper_id")
            pdf_path = parameters.get("pdf_path")
            
            try:
                result = self.analyze(paper_id, pdf_path, trace_id=message.trace_id)
                self.send_result(
                    to_agent=message.from_agent,
                    task_id=message.msg_id,
                    result=result,
                    trace_id=message.trace_id
                )
            except Exception as e:
                self.send_error(
                    error_code="ANALYSIS_FAILED",
                    error_message=str(e),
                    trace_id=message.trace_id
                )