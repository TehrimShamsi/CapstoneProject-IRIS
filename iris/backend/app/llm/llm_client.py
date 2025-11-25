"""LLM client wrapper — Google Generative AI (Gemini) implementation.

This uses `google-generativeai` and requires `GOOGLE_API_KEY` to be set in
the environment (or in `.env`). The codebase does NOT use Application Default
Credentials (service-account JSON) — `GOOGLE_API_KEY` is sufficient.
"""

import os
from typing import Optional

# Provide a safe mock mode for local development to avoid incurring charges.
# Set environment variable `USE_MOCK_LLM=1` to enable.
USE_MOCK = os.getenv("USE_MOCK_LLM", "").lower() in ("1", "true", "yes")

if not USE_MOCK:
    try:
        import google.generativeai as genai
    except Exception as e:
        raise RuntimeError(
            "google-generativeai package required. pip install google-generativeai"
        ) from e


class _RealLLMClient:
    """Simple wrapper around google.generativeai with a consistent `call` API."""

    def __init__(self):
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise RuntimeError(
                "GOOGLE_API_KEY is required for the real LLM client. "
                "Set GOOGLE_API_KEY in your environment or enable USE_MOCK_LLM."
            )
        # configure with API key
        genai.configure(api_key=api_key)

        raw_model = os.getenv("GOOGLE_MODEL", "gemini-2.5-flash-lite")
        if raw_model.startswith("models/") or raw_model.startswith("tunedModels/"):
            self.model = raw_model
        else:
            self.model = f"models/{raw_model}"
        try:
            self.max_tokens_default = int(os.getenv("MAX_TOKENS_DEFAULT", "1024"))
        except Exception:
            self.max_tokens_default = 1024

    def call(self, prompt: str, max_tokens: Optional[int] = None, temperature: float = 0.0) -> str:
        max_tokens = max_tokens or self.max_tokens_default
        try:
            if hasattr(genai, "chat") and hasattr(genai.chat, "completions"):
                messages = [{"role": "user", "content": prompt}]
                resp = genai.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=temperature,
                    max_output_tokens=max_tokens,
                )
                if hasattr(resp, "candidates") and len(resp.candidates) > 0:
                    return getattr(resp.candidates[0], "content", str(resp.candidates[0]))
                if hasattr(resp, "choices") and len(resp.choices) > 0:
                    choice = resp.choices[0]
                    if hasattr(choice, "message") and isinstance(choice.message, dict):
                        return choice.message.get("content") or str(choice)
                    return getattr(choice, "text", str(choice))

            if hasattr(genai, "generate_text"):
                resp = genai.generate_text(model=self.model, prompt=prompt, max_output_tokens=max_tokens)
                if hasattr(resp, "text"):
                    return resp.text
                if hasattr(resp, "candidates") and len(resp.candidates) > 0:
                    return getattr(resp.candidates[0], "output", str(resp.candidates[0]))

            resp = genai.generate_text(model=self.model, prompt=prompt, max_output_tokens=max_tokens)
            return str(resp)

        except Exception as e:
            raise RuntimeError(f"LLM call failed: {e}") from e


class _MockLLMClient:
    """Mock LLM client for safe local development. Returns deterministic text."""

    def __init__(self):
        self.max_tokens_default = int(os.getenv("MAX_TOKENS_DEFAULT", "1024"))

    def call(self, prompt: str, max_tokens: Optional[int] = None, temperature: float = 0.0) -> str:
        max_tokens = max_tokens or self.max_tokens_default
        # Return a short deterministic mock response that resembles model output.
        snippet = prompt.strip().replace("\n", " ")[:160]
        return f"[MOCK-GEMINI RESPONSE | tokens={min(32, max_tokens)}] {snippet}"


# Export the public name expected elsewhere in the codebase: `LLMClient`.
LLMClient = _MockLLMClient if USE_MOCK else _RealLLMClient
