# backend/app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import router

# OpenTelemetry instrumentation (optional - for enhanced observability)
try:
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    OTEL_AVAILABLE = True
except ImportError:
    OTEL_AVAILABLE = False

# Load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

app = FastAPI(
    title="IRIS Research Assistant",
    description="Intelligent Research Insight System - Multi-agent AI for research paper analysis",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Instrument with OpenTelemetry if available
if OTEL_AVAILABLE:
    FastAPIInstrumentor.instrument_app(app)

app.include_router(router)

@app.get("/")
def root():
    return {
        "message": "IRIS API is running",
        "version": "1.0.0",
        "features": {
            "vector_search": True,
            "a2a_protocol": True,
            "multi_agent": True,
            "semantic_search": True
        }
    }

@app.get("/health")
def health_check():
    """Health check endpoint"""
    from app.storage.vector_db import get_vector_db
    
    vector_db = get_vector_db()
    
    return {
        "status": "healthy",
        "vector_db_docs": vector_db.get_document_count(),
        "agents": ["AnalysisAgent", "SynthesisAgent", "SearchAgent", "FetchAgent"]
    }
