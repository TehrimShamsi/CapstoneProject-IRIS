import uuid
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse

from app.tools.pdf_processor import PDFProcessor
from app.tools.arxiv_fetcher import ArxivFetcher
from app.services.session_manager import SessionManager
from app.agents.orchestrator import Orchestrator
from app.utils.evaluation import AgentEvaluator
from app.utils.observability import get_metrics
from app.utils.observability import logger

from app.api.models import (
    UploadPDFResponse, AnalyzeRequest, SynthesizeRequest, EvaluationResponse
)

router = APIRouter()

session_manager = SessionManager()
orchestrator = Orchestrator(session_manager)
pdf_processor = PDFProcessor()
fetcher = ArxivFetcher()
evaluator = AgentEvaluator()


# -----------------------------
# PDF Upload
# -----------------------------
@router.post("/upload", response_model=UploadPDFResponse)
async def upload_pdf(file: UploadFile = File(...)):
    paper_id = str(uuid.uuid4())
    try:
        logger.info(f"/upload called — saving file {file.filename} size={getattr(file.file, 'length', 'unknown')}")
        pdf_path = pdf_processor.save_pdf(file, paper_id)
        session_manager.create_paper_entry(paper_id, {"pdf_path": pdf_path})

        logger.info(f"Saved PDF for paper_id={paper_id} at {pdf_path}")

        return UploadPDFResponse(
            paper_id=paper_id,
            filename=file.filename
        )
    except Exception as e:
        logger.error(f"Error handling upload for {file.filename}: {e}")
        raise


# -----------------------------
# Create Session
# -----------------------------
@router.post("/session")
async def create_session_endpoint(user_id: str = "demo_user"):
    """Create a new session"""
    session_id = session_manager.create_session(user_id)
    return {"session_id": session_id}


# -----------------------------
# Analyze Paper
# -----------------------------
@router.post("/analyze")
async def analyze(req: AnalyzeRequest):
    try:
        result = orchestrator.analyze_paper(
            session_id=req.session_id,
            paper_id=req.paper_id
        )
        return JSONResponse(result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# -----------------------------
# Synthesize Multiple Papers
# -----------------------------
@router.post("/synthesize")
async def synthesize(req: SynthesizeRequest):
    try:
        result = orchestrator.synthesize(
            session_id=req.session_id,
            paper_ids=req.paper_ids
        )
        return JSONResponse(result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# -----------------------------
# Get Session Data
# -----------------------------
@router.get("/session/{session_id}")
async def get_session(session_id: str):
    data = session_manager.load_session(session_id)
    if not data:
        raise HTTPException(status_code=404, detail="Session not found")
    return data


# -----------------------------
# Observability Metrics
# -----------------------------
@router.get("/metrics")
async def metrics():
    return get_metrics()


# -----------------------------
# Evaluation Reports
# -----------------------------
@router.get("/evaluation/{session_id}", response_model=EvaluationResponse)
async def evaluation(session_id: str):
    session = session_manager.load_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    analyses = session.get("analysis_results", {})
    synthesis = session.get("synthesis_result", {})

    report = evaluator.generate_report(
        list(analyses.values()),
        synthesis
    )

    return EvaluationResponse(report=report)
