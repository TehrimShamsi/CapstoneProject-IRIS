# backend/app/agents/synthesis_agent.py
import os
import json
import re
import google.generativeai as genai
from typing import List, Dict, Any, Optional

from app.utils.observability import agent_call, logger

# USE GOOGLE_API_KEY (not GEMINI_API_KEY) — REQUIRED (no fallback to Application Default Credentials)
GOOGLE_KEY = os.getenv("GOOGLE_API_KEY")
if not GOOGLE_KEY:
    raise RuntimeError(
        "GOOGLE_API_KEY environment variable is required for SynthesisAgent. "
        "Set it in .env or your environment before starting the server."
    )
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
                    "text": c.get("text", ""),
                    "confidence": float(c.get("confidence", 0.0)) if isinstance(c.get("confidence", 0.0), (int, float, str)) else 0.0
                })
        # unique id prefix for response mapping
        max_claims = 30
        claims_for_prompt = claims_for_prompt[:max_claims]

        # Build a compact prompt listing the claims
        claims_text = "\n".join([f"{i+1}. ({c['paper_id']}) {c['text']}" for i, c in enumerate(claims_for_prompt)])

        # Consensus prompt - with explicit JSON markers to force output
        consensus_prompt = f"""You are analyzing research claims from multiple papers.
Identify consensus statements (claims supported by similar claims from 2+ different papers).

Claims:
{claims_text}

Output a JSON array inside <JSON>...</JSON> tags. MUST output structured data.

Format:
[
  {{
    "text": "consensus statement text",
    "papers": ["paper_id1", "paper_id2"],
    "average_confidence": 0.8
  }},
  ...
]

If there is no consensus, return an empty array: []

<JSON>
"""

        contradictions_prompt = f"""You are analyzing research claims from multiple papers.
Identify contradiction pairs (claims from different papers that directly conflict).

Claims:
{claims_text}

Output a JSON array inside <JSON>...</JSON> tags. MUST output structured data.

Format:
[
  {{
    "claim_a": "text of claim A",
    "paper_a": "paper_idA",
    "claim_b": "text of claim B",
    "paper_b": "paper_idB"
  }},
  ...
]

If there are no contradictions, return an empty array: []

<JSON>
"""

        consensus = self._call_gemini_json(consensus_prompt, default=None)
        contradictions = self._call_gemini_json(contradictions_prompt, default=None)

        logger.info(f"SynthesisAgent: LLM consensus result: type={type(consensus)}, len={len(consensus) if isinstance(consensus, list) else 'N/A'}, value={consensus}")

        # If consensus is empty/None, try extracting it from contradictions or generate from claims
        if consensus is None or (isinstance(consensus, list) and len(consensus) == 0):
            logger.info("SynthesisAgent: No consensus from LLM, attempting to extract from claim similarity...")
            consensus = self._extract_consensus_from_claims(claims_for_prompt)
            logger.info(f"SynthesisAgent: Extracted {len(consensus)} consensus items from claim similarity")

        # If Gemini isn't available for contradictions, fall back to lightweight heuristic
        if contradictions is None:
            logger.info("SynthesisAgent: No contradictions from LLM, using heuristic...")
            _, contradictions = self._heuristic_synthesis(claims_for_prompt)

        # Post-process LLM output defensively:
        # - Ensure papers lists are unique and contain real paper ids
        # - Compute average_confidence from underlying analyses when missing or suspicious
        try:
            # Build mapping paper_id -> list of claim confidences from provided analyses
            paper_conf_map = {}
            for a in analyses:
                pid = a.get('paper_id') or a.get('paper') or None
                if not pid:
                    continue
                paper_conf_map.setdefault(pid, [])
                for c in a.get('claims', []):
                    try:
                        paper_conf_map[pid].append(float(c.get('confidence', 0.0)))
                    except Exception:
                        pass

            # Consensus defensive cleanup
            cleaned_consensus = []
            seen_consensus = set()
            logger.debug(f"Processing {len(consensus) if isinstance(consensus, list) else 0} consensus items for cleanup")
            if isinstance(consensus, list):
                for item in consensus:
                    try:
                        papers = item.get('papers', []) if isinstance(item, dict) else []
                        # dedupe paper ids
                        uniq_papers = sorted(list(dict.fromkeys(papers)))
                        logger.debug(f"Consensus item papers: {papers} -> unique: {uniq_papers}")
                        if len(uniq_papers) < 2:
                            # skip consensus that doesn't span multiple papers
                            logger.debug(f"Skipping consensus: only {len(uniq_papers)} unique papers")
                            continue

                        # Normalize text to identify near-duplicates
                        raw_text = item.get('text') if isinstance(item, dict) else str(item)
                        norm = re.sub(r"[^a-z0-9]\s+", " ", raw_text.lower())
                        norm_key = norm.strip()[:120]

                        # canonical key to dedupe similar consensus texts (normalize + papers)
                        key = (norm_key, tuple(uniq_papers))
                        if key in seen_consensus:
                            # If we saw a near-duplicate, try to merge confidences by updating existing entry
                            for existing in cleaned_consensus:
                                if tuple(existing['papers']) == tuple(uniq_papers) and re.sub(r"[^a-z0-9]\s+", " ", existing['text'].lower()).strip()[:120] == norm_key:
                                    # merge average_conf by averaging
                                    try:
                                        old_conf = float(existing.get('average_confidence', 0.0))
                                    except Exception:
                                        old_conf = 0.0
                                    try:
                                        new_conf = float(item.get('average_confidence', 0.0))
                                    except Exception:
                                        # fallback to underlying paper confidences
                                        all_confs = []
                                        for pid in uniq_papers:
                                            all_confs.extend(paper_conf_map.get(pid, []))
                                        new_conf = (sum(all_confs) / len(all_confs)) if all_confs else 0.0
                                    existing['average_confidence'] = round((old_conf + new_conf) / 2.0, 3)
                                    # optionally update text to the longer descriptive one
                                    if len(raw_text) > len(existing['text']):
                                        existing['text'] = raw_text
                                    break
                            continue

                        seen_consensus.add(key)

                        avg_conf = None
                        if isinstance(item, dict) and item.get('average_confidence') is not None:
                            try:
                                avg_conf = float(item.get('average_confidence'))
                            except Exception:
                                avg_conf = None

                        # if missing or equals 0.5 (previous default), compute from underlying analyses
                        if avg_conf is None or avg_conf == 0.5:
                            all_confs = []
                            for pid in uniq_papers:
                                all_confs.extend(paper_conf_map.get(pid, []))
                            if all_confs:
                                avg_conf = sum(all_confs) / len(all_confs)
                            else:
                                avg_conf = 0.0

                        cleaned_item = {
                            'text': raw_text,
                            'papers': uniq_papers,
                            'average_confidence': round(float(avg_conf), 3)
                        }
                        cleaned_consensus.append(cleaned_item)
                    except Exception:
                        continue
            else:
                cleaned_consensus = []

            consensus = cleaned_consensus

            # Contradictions defensive cleanup: ensure different papers and dedupe
            cleaned_contradictions = []
            seen_con = set()
            if isinstance(contradictions, list):
                for item in contradictions:
                    try:
                        pa = item.get('paper_a') if isinstance(item, dict) else None
                        pb = item.get('paper_b') if isinstance(item, dict) else None
                        if not pa or not pb or pa == pb:
                            continue
                        key = (str(item.get('claim_a') if isinstance(item, dict) else '' )[:120],
                               str(item.get('claim_b') if isinstance(item, dict) else '' )[:120],
                               tuple(sorted([pa, pb])))
                        if key in seen_con:
                            continue
                        seen_con.add(key)
                        cleaned_contradictions.append({
                            'claim_a': item.get('claim_a'),
                            'paper_a': pa,
                            'claim_b': item.get('claim_b'),
                            'paper_b': pb
                        })
                    except Exception:
                        continue
            contradictions = cleaned_contradictions
        except Exception:
            # If post-processing fails, keep original outputs
            pass

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
        Helper to call Gemini and parse JSON safely. Extracts JSON from <JSON>...</JSON> tags.
        Falls back to default on error.
        """
        import re
        if self.model is None:
            return default
        try:
            response = self.model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.15,
                    max_output_tokens=1024
                )
            )

            logger.debug("SynthesisAgent: calling model.generate_content for synthesis prompt")
            # Extract raw text from response
            raw = ""
            try:
                if getattr(response, 'text', None):
                    raw = response.text
                else:
                    parts_list = []
                    rv_parts = getattr(response, 'parts', None)
                    if rv_parts:
                        for p in rv_parts:
                            parts_list.append(getattr(p, 'text', str(p)))

                    try:
                        if hasattr(response, 'result') and getattr(response.result, 'parts', None):
                            for p in response.result.parts:
                                parts_list.append(getattr(p, 'text', str(p)))
                    except Exception:
                        pass

                    cands = getattr(response, 'candidates', None)
                    if cands:
                        for cand in cands:
                            if isinstance(cand, str):
                                parts_list.append(cand)
                                continue
                            try:
                                content = getattr(cand, 'content', None) or (cand if isinstance(cand, dict) else None)
                                if isinstance(content, dict) and content.get('parts'):
                                    for p in content.get('parts'):
                                        parts_list.append(p.get('text') if isinstance(p, dict) else getattr(p, 'text', str(p)))
                                    continue
                            except Exception:
                                pass
                            parts_list.append(str(cand))

                    raw = ''.join(parts_list)

                if not raw:
                    try:
                        raw = str(response)
                    except Exception:
                        raw = ""
            except Exception:
                raw = ""

            logger.debug(f"SynthesisAgent: raw model output (first 500 chars): {repr(raw[:500])}")

            if not raw:
                logger.info("SynthesisAgent: model returned empty response, falling back to default")
                return default

            # Try to extract JSON from <JSON>...</JSON> tags
            json_match = re.search(r'<JSON>\s*(.*?)\s*</JSON>', raw, re.DOTALL)
            if json_match:
                json_text = json_match.group(1).strip()
                logger.debug(f"Extracted JSON from tags: {json_text[:200]}")
            else:
                json_text = raw

            cleaned = _clean_model_text(json_text)
            try:
                parsed = json.loads(cleaned)
            except Exception as e:
                logger.debug(f"Initial JSON parse failed: {e}, attempting repairs...")
                # Try minimal repairs
                repaired = re.sub(r',\s*([}\]])', r'\1', cleaned)
                try:
                    parsed = json.loads(repaired)
                except Exception as e2:
                    logger.warning(f"JSON repair failed: {e2}. Returning default.")
                    return default

            logger.debug(f"SynthesisAgent: parsed JSON successfully, type={type(parsed)}")
            return parsed
        except Exception as e:
            logger.warning(f"SynthesisAgent._call_gemini_json failed: {e}")
            return default

    def _extract_consensus_from_claims(self, claims: List[Dict[str, str]]) -> List[Dict]:
        """
        Extract consensus from similar claims across papers.
        Looks for claims from different papers that share significant textual overlap.
        """
        import re
        from collections import defaultdict

        def normalize_text(text):
            """Normalize text for comparison."""
            t = text.lower()
            t = re.sub(r"[^a-z0-9\s]", " ", t)
            return ' '.join(t.split())

        def get_tokens(text):
            """Extract significant tokens (>3 chars)."""
            norm = normalize_text(text)
            return set(w for w in norm.split() if len(w) > 3)

        consensus_items = []
        seen_pairs = set()

        # Compare each pair of claims
        for i in range(len(claims)):
            for j in range(i + 1, len(claims)):
                claim_i = claims[i]
                claim_j = claims[j]

                # Skip if same paper
                if claim_i['paper_id'] == claim_j['paper_id']:
                    continue

                # Get tokens
                tokens_i = get_tokens(claim_i['text'])
                tokens_j = get_tokens(claim_j['text'])

                # Count overlap
                overlap = tokens_i & tokens_j
                if len(overlap) >= 3:  # At least 3 tokens in common
                    # This looks like consensus
                    pair_key = tuple(sorted([claim_i['paper_id'], claim_j['paper_id']]) + [
                        normalize_text(claim_i['text'])[:100],
                        normalize_text(claim_j['text'])[:100]
                    ])
                    if pair_key not in seen_pairs:
                        seen_pairs.add(pair_key)
                        
                        # Compute average confidence
                        try:
                            conf_i = float(claim_i.get('confidence', 0.0))
                        except Exception:
                            conf_i = 0.0
                        try:
                            conf_j = float(claim_j.get('confidence', 0.0))
                        except Exception:
                            conf_j = 0.0

                        avg_conf = (conf_i + conf_j) / 2.0

                        consensus_items.append({
                            'text': f"{claim_i['text']} / {claim_j['text']}",
                            'papers': sorted(list(set([claim_i['paper_id'], claim_j['paper_id']]))),
                            'average_confidence': round(avg_conf, 3)
                        })

        logger.info(f"SynthesisAgent: extracted {len(consensus_items)} consensus items from claim similarity")
        return consensus_items

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
                    # Only consider consensus across different papers
                    if pid_i == pid_j:
                        continue

                    key = ' || '.join(sorted([pid_i, pid_j])) + ' :: ' + ' / '.join(sorted(list(common))[:5])
                    if key not in consensus_map:
                        # compute average confidence from the two claims if available
                        try:
                            conf_i = float(token_sets[i][2]) if isinstance(token_sets[i][2], (int, float)) else None
                        except Exception:
                            conf_i = None
                        try:
                            conf_j = float(token_sets[j][2]) if isinstance(token_sets[j][2], (int, float)) else None
                        except Exception:
                            conf_j = None

                        # token_sets currently: (paper_id, claim_id, text, toks)
                        # but we updated claims to include confidence in the input list; try to read from claims param instead
                        conf_i = None
                        conf_j = None
                        try:
                            conf_i = float(claims[i].get("confidence", 0.0))
                        except Exception:
                            conf_i = 0.0
                        try:
                            conf_j = float(claims[j].get("confidence", 0.0))
                        except Exception:
                            conf_j = 0.0

                        avg_conf = (conf_i + conf_j) / 2.0

                        consensus_map[key] = {
                            "text": f"{text_i} / {text_j}",
                            "papers": sorted(list(set([pid_i, pid_j]))),
                            "average_confidence": round(avg_conf, 3)
                        }

        consensus = list(consensus_map.values())

        # Contradictions: check polarity pairs and negation-based contradictions.
        polarity_pairs = [ ("increase","decrease"), ("improve","worse"), ("higher","lower"), ("positive","negative"), ("gain","loss"), ("better","worse") ]
        negation_terms = {"not","no","none","without","lack","fails","failed","doesn't","doesnt","cannot","can't","cant"}
        contradictions = []
        contradictions_seen = set()
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
                    # dedupe by canonical key
                    can = tuple(sorted([pid_i, pid_j]) + [ '::'.join(sorted([text_i.strip()[:120], text_j.strip()[:120]])) ])
                    if can not in contradictions_seen:
                        contradictions.append({
                            "claim_a": text_i,
                            "paper_a": pid_i,
                            "claim_b": text_j,
                            "paper_b": pid_j
                        })
                        contradictions_seen.add(can)
                    continue
                # Negation-based: one claim contains negation while the other does not and they share tokens
                a_neg = any(nt in a_text for nt in negation_terms)
                b_neg = any(nt in b_text for nt in negation_terms)
                if a_neg != b_neg and len(common) >= 2:
                    can = tuple(sorted([pid_i, pid_j]) + [ '::'.join(sorted([text_i.strip()[:120], text_j.strip()[:120]])) ])
                    if can not in contradictions_seen:
                        contradictions.append({
                            "claim_a": text_i,
                            "paper_a": pid_i,
                            "claim_b": text_j,
                            "paper_b": pid_j
                        })
                        contradictions_seen.add(can)

        return consensus, contradictions