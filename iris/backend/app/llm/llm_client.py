"""LLM client wrapper — Google Generative AI (Gemini) implementation.

This uses `google-generativeai` and requires `GOOGLE_API_KEY` to be set in
the environment (or in `.env`).
"""

import os
from typing import Optional

# Mock mode for local development
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
        
        # Configure with API key
        genai.configure(api_key=api_key)

        # Get model name from env, default to gemini-1.5-flash
        raw_model = os.getenv("GOOGLE_MODEL", "gemini-1.5-flash")
        
        # Don't add "models/" prefix - the SDK handles it
        self.model_name = raw_model
        
        try:
            self.max_tokens_default = int(os.getenv("MAX_TOKENS_DEFAULT", "1024"))
        except Exception:
            self.max_tokens_default = 1024

        print(f"Using GOOGLE_MODEL: {self.model_name}")

    def call(self, prompt: str, max_tokens: Optional[int] = None, temperature: float = 0.0) -> str:
        """Call the Gemini API with the given prompt."""
        max_tokens = max_tokens or self.max_tokens_default
        
        try:
            # Create model instance
            model = genai.GenerativeModel(self.model_name)
            
            print("Sending test prompt to model...")
            
            # Generate content
            response = model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    max_output_tokens=max_tokens,
                    temperature=temperature,
                )
            )
            
            # Extract text from response
            if hasattr(response, 'text'):
                return response.text
            elif hasattr(response, 'candidates') and len(response.candidates) > 0:
                candidate = response.candidates[0]
                if hasattr(candidate, 'content') and hasattr(candidate.content, 'parts'):
                    return ''.join(part.text for part in candidate.content.parts if hasattr(part, 'text'))
            
            return str(response)

        except Exception as e:
            error_msg = str(e)
            
            # Provide helpful error messages
            if "404" in error_msg:
                raise RuntimeError(
                    f"LLM call failed: {e}\n"
                    f"If this is a 404, verify your GOOGLE_MODEL is available to your API key and run:\n"
                    f"   Invoke-RestMethod -Uri \"https://generativelanguage.googleapis.com/v1beta/models?key=$env:GOOGLE_API_KEY\" -Method GET"
                ) from e
            elif "403" in error_msg or "API key" in error_msg:
                raise RuntimeError(
                    f"LLM call failed: {e}\n"
                    f"API key error. Verify:\n"
                    f"1. Your GOOGLE_API_KEY is set correctly\n"
                    f"2. The key is valid at https://aistudio.google.com/app/apikey\n"
                    f"3. Generative Language API is enabled"
                ) from e
            else:
                raise RuntimeError(f"LLM call failed: {e}") from e


class _MockLLMClient:
    """Mock LLM client for safe local development. Returns deterministic text."""

    def __init__(self):
        self.max_tokens_default = int(os.getenv("MAX_TOKENS_DEFAULT", "1024"))

    def call(self, prompt: str, max_tokens: Optional[int] = None, temperature: float = 0.0) -> str:
        max_tokens = max_tokens or self.max_tokens_default
        snippet = prompt.strip().replace("\n", " ")[:160]
        return f"[MOCK-GEMINI RESPONSE | tokens={min(32, max_tokens)}] {snippet}"


# Export the public name expected elsewhere in the codebase
LLMClient = _MockLLMClient if USE_MOCK else _RealLLMClient