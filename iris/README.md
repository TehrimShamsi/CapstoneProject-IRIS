IRIS Research Assistant

This repository contains a FastAPI backend and a React frontend. The backend uses Google Generative AI (Gemini) via the `google-generativeai` package.

Quick start (Backend)

1. Open PowerShell and change to the backend folder:

```powershell
cd "c:\Users\tehrim\Documents\CapstoneProject-IRIS\iris\backend"
```

2. Create and activate a virtual environment:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

3. Install Python dependencies:

```powershell
pip install -r requirements.txt
```

4. Create a `.env` from the example and add your Google API key (or set `GOOGLE_APPLICATION_CREDENTIALS`):

```powershell
copy .env.example .env
# then edit .env and set GOOGLE_API_KEY or set GOOGLE_APPLICATION_CREDENTIALS to a service account JSON
```

5. Run the API:

```powershell
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

6. Verify: open `http://localhost:8000/` to see a readiness message.

Notes on Gemini / Google Generative AI

- The backend now uses `iris/backend/app/llm/llm_client.py`, which calls `google.generativeai`.
- Set `GOOGLE_API_KEY` in `.env` or use ADC (`GOOGLE_APPLICATION_CREDENTIALS`) if using a service account.
-- Change `GOOGLE_MODEL` in `.env` if you need a different model. This project defaults to `gemini-2.5-flash-lite`.

Frontend

- The frontend source is in `iris/frontend/src`. There is no `package.json` in this repo; scaffold a frontend in `iris/frontend` using Vite or create a `package.json` and install dependencies.

Example (create a Vite React project in the frontend folder):

```powershell
cd "c:\Users\tehrim\Documents\CapstoneProject-IRIS\iris\frontend"
npm create vite@latest . -- --template react
npm install
npm run dev
```

Security

- Do NOT commit real API keys. Keep `.env` out of source control. Use `.env.example` in the repo to show required variables.
If you want, I can:
- Scaffold a `package.json` and add Tailwind/Vite config for the frontend,
- Wire the frontend API client defaults, or
- Add a provider switcher to support both OpenAI and Google (not requested).

Windows-specific backend tips

- If PowerShell blocks script execution when activating the venv you can either:
	- Allow script execution for the current session and activate the venv:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
. .venv\Scripts\Activate.ps1
```

	- Or avoid activation and run the venv python directly (works even if activation is blocked):

```powershell
# Create the venv (recommended use py -3.11 if you installed 3.11 alongside 3.13)
py -3.11 -m venv .venv

# Install requirements without activating the venv
.venv\Scripts\python -m pip install --upgrade pip
.venv\Scripts\python -m pip install -r requirements.txt

# Run the server using the venv python (no activation required)
.venv\Scripts\python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- If you prefer a short helper script, use `backend\run_server.ps1`:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\run_server.ps1
```

Notes on Python versions

- Recommendation: use Python 3.11 (binary wheels widely available). Python 3.13 may require Rust+MSVC to compile `pydantic-core` and other native extensions. If you are on 3.13 and want to keep it, install Rust and Visual Studio Build Tools.

Smoke test for LLM client

- After installing dependencies and setting `GOOGLE_API_KEY` (or ADC), run:

```powershell
.venv\Scripts\python backend\tools\check_llm.py
```

This will import `app.llm.llm_client.LLMClient` and make a short test call. It helps verify credentials and the LLM client without starting the server.

