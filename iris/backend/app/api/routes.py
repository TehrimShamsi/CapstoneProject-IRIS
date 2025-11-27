import uuid
from typing import Optional
from fastapi import APIRouter, UploadFile, File, HTTPException, Query
from fastapi.responses import JSONResponse

from app.tools.pdf_processor import PDFProcessor
from app.tools.arxiv_fetcher import ArxivFetcher
from app.services.session_manager import SessionManager
from app.agents.orchestrator import Orchestrator
from app.agents.search_agent import SearchAgent
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
search_agent = SearchAgent()


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


# -----------------------------
# NEW: Search ArXiv Papers
# -----------------------------
@router.get("/search_arxiv")
async def search_arxiv(
    query: str = Query(..., description="Search query"),
    max_results: int = Query(10, ge=1, le=50, description="Maximum number of results")
):
    """
    Search ArXiv for papers matching the query.
    
    Args:
        query: Search query string
        max_results: Maximum number of results (1-50)
        
    Returns:
        List of paper metadata
    """
    try:
        logger.info(f"Searching ArXiv for: {query}")
        results = search_agent.search_papers(query, max_results=max_results)
        return {
            "query": query,
            "count": len(results),
            "papers": results
        }
    except Exception as e:
        logger.error(f"ArXiv search error: {e}")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


# -----------------------------
# NEW: Get Trending Papers
# -----------------------------
@router.get("/trending_papers")
async def trending_papers(
    category: str = Query("cs.AI", description="ArXiv category"),
    max_results: int = Query(10, ge=1, le=50)
):
    """
    Get recently published trending papers from a category.
    
    Args:
        category: ArXiv category (e.g., cs.AI, cs.LG, cs.CL)
        max_results: Maximum number of results
        
    Returns:
        List of trending papers
    """
    try:
        logger.info(f"Fetching trending papers from {category}")
        results = search_agent.get_trending_papers(category, max_results=max_results)
        return {
            "category": category,
            "count": len(results),
            "papers": results
        }
    except Exception as e:
        logger.error(f"Trending papers error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch trending papers: {str(e)}")


# -----------------------------
# NEW: Smart Paper Suggestions
# -----------------------------
@router.post("/suggest_papers")
async def suggest_papers(
    session_id: Optional[str] = None,
    max_suggestions: int = Query(8, ge=1, le=20)
):
    """
    Generate smart paper suggestions based on session context.
    
    Args:
        session_id: Optional session ID for context-aware suggestions
        max_suggestions: Maximum number of suggestions
        
    Returns:
        List of suggested papers
    """
    try:
        # Get session context if provided
        session_context = {}
        if session_id:
            session = session_manager.load_session(session_id)
            if session:
                session_context = session
        
        # Generate suggestions
        suggestions = search_agent.suggest_papers(session_context, max_suggestions=max_suggestions)
        
        return {
            "session_id": session_id,
            "count": len(suggestions),
            "suggestions": suggestions
        }
    except Exception as e:
        logger.error(f"Paper suggestion error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate suggestions: {str(e)}")


# -----------------------------
# NEW: Search by Author
# -----------------------------
@router.get("/search_by_author")
async def search_by_author(
    author: str = Query(..., description="Author name"),
    max_results: int = Query(10, ge=1, le=50)
):
    """
    Search for papers by a specific author.
    
    Args:
        author: Author name to search
        max_results: Maximum number of results
        
    Returns:
        List of papers by the author
    """
    try:
        logger.info(f"Searching papers by author: {author}")
        results = search_agent.search_by_author(author, max_results=max_results)
        return {
            "author": author,
            "count": len(results),
            "papers": results
        }
    except Exception as e:
        logger.error(f"Author search error: {e}")
        raise HTTPException(status_code=500, detail=f"Author search failed: {str(e)}")


# -----------------------------
# NEW: Find Similar Papers
# -----------------------------
@router.get("/similar_papers/{paper_id}")
async def similar_papers(
    paper_id: str,
    max_results: int = Query(5, ge=1, le=20)
):
    """
    Find papers similar to a given paper.
    
    Args:
        paper_id: ArXiv ID of the reference paper
        max_results: Maximum number of similar papers
        
    Returns:
        List of similar papers
    """
    try:
        logger.info(f"Finding papers similar to {paper_id}")
        results = search_agent.search_similar_papers(paper_id, max_results=max_results)
        return {
            "reference_paper": paper_id,
            "count": len(results),
            "similar_papers": results
        }
    except Exception as e:
        logger.error(f"Similar papers error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to find similar papers: {str(e)}")


# -----------------------------
# NEW: Download Paper from ArXiv
# -----------------------------
@router.post("/download_arxiv_paper")
async def download_arxiv_paper(arxiv_id: str):
    """
    Download a paper from ArXiv and create a session entry.
    
    Args:
        arxiv_id: ArXiv paper ID
        
    Returns:
        Paper ID and download status
    """
    try:
        logger.info(f"Downloading paper from ArXiv: {arxiv_id}")
        
        # Download the PDF
        pdf_path = fetcher.fetch(arxiv_id)
        
        # Create paper entry
        paper_id = arxiv_id.replace("/", "_")
        session_manager.create_paper_entry(paper_id, {
            "pdf_path": pdf_path,
            "source": "arxiv",
            "arxiv_id": arxiv_id
        })
        
        logger.info(f"Successfully downloaded and stored paper {arxiv_id}")
        
        return {
            "paper_id": paper_id,
            "arxiv_id": arxiv_id,
            "pdf_path": pdf_path,
            "status": "success"
        }
        
    except Exception as e:
        logger.error(f"Download error for {arxiv_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Download failed: {str(e)}")