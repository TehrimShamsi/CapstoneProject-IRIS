from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import router

# Load environment variables from a .env file (if present)
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    # python-dotenv is optional at runtime if env vars are set by other means
    pass

app = FastAPI(title="IRIS Research Assistant")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)

@app.get("/")
def root():
    return {"message": "IRIS API is running"}
