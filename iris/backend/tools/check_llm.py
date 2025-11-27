"""Small smoke-test for the LLM client.

Run this after installing requirements and setting `GOOGLE_API_KEY` or
`GOOGLE_APPLICATION_CREDENTIALS`.

Usage (PowerShell):
    .venv\Scripts\python backend\tools\check_llm.py
"""

import os
import sys
import pathlib

# Ensure backend root is on sys.path so `app` package can be imported when
# this script is executed from the `backend` folder.
ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from app.llm.llm_client import LLMClient
except Exception as e:
    print("Failed to import LLMClient:", e)
    sys.exit(1)
# Load .env if present so local env vars are available to the client
try:
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=ROOT / '.env')
except Exception:
    # python-dotenv may not be installed or .env may not exist; fall back to process env
    pass

if __name__ == "__main__":
    # Allow overriding model via CLI: `python tools/check_llm.py --model gemini-2.0-flash`
    model_arg = None
    if len(sys.argv) >= 3 and sys.argv[1] in ("--model", "-m"):
        model_arg = sys.argv[2]
        os.environ["GOOGLE_MODEL"] = model_arg

    key = os.getenv("GOOGLE_API_KEY")
    if not key:
        print("Warning: GOOGLE_API_KEY not set. Set it before running this test or enable USE_MOCK_LLM.")

    print("Using GOOGLE_MODEL:", os.getenv("GOOGLE_MODEL", "(not set)"))

    try:
        client = LLMClient()
    except Exception as e:
        print("Failed to initialize LLMClient:", e)
        sys.exit(1)

    try:
        print("Sending test prompt to model...")
        resp = client.call("Say hello in one sentence.", max_tokens=50)
        print("LLM response:")
        print(resp)
    except Exception as e:
        print("LLM call failed:", e)
        print("If this is a 404, verify your GOOGLE_MODEL is available to your API key and run: ")
        print("  Invoke-RestMethod -Uri \"https://generativelanguage.googleapis.com/v1beta/models?key=$env:GOOGLE_API_KEY\" -Method GET")
        sys.exit(2)
