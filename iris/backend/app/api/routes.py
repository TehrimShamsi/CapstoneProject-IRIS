import uuid
from typing import Optional
import arxiv
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
    FetchArxivRequest, UploadPDFResponse, AnalyzeRequest, SynthesizeRequest, EvaluationResponse
)

router = APIRouter()

session_manager = SessionManager()
orchestrator = Orchestrator(session_manager)
pdf_processor = PDFProcessor()
fetcher = ArxivFetcher()
evaluator = AgentEvaluator()
search_agent = SearchAgent()

    # NEW request models - add these
# -----------------------------
# PDF Upload
# -----------------------------
@router.post("/upload", response_model=UploadPDFResponse)
async def upload_pdf(file: UploadFile = File(...)):
    paper_id = str(uuid.uuid4())
    try:
        logger.info(f"/upload called — saving file {file.filename} size={getattr(file.file, 'length', 'unknown')}")
        pdf_path = pdf_processor.save_pdf(file, paper_id)

        # Try to extract a human-friendly title from the uploaded PDF.
        title = None
        try:
            # Use the PDFProcessor text extractor — take the first non-empty line
            text = pdf_processor.extract_text(pdf_path)
            if text:
                # Use the first non-empty line as a candidate title
                for line in text.splitlines():
                    clean = line.strip()
                    if len(clean) > 6:
                        title = clean[:200]
                        break
        except Exception as e:
            logger.debug(f"Could not extract text/title from uploaded PDF: {e}")

        # Persist paper metadata (include filename, pdf_path and optional title)
        metadata = {"pdf_path": pdf_path, "filename": file.filename, "source": "upload"}
        if title:
            metadata["title"] = title

        session_manager.create_paper_entry(paper_id, metadata)

        logger.info(f"Saved PDF for paper_id={paper_id} at {pdf_path} (title={title})")

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
        agent_res = search_agent.search_papers(query, max_results=max_results)
        papers = agent_res.get("papers") if isinstance(agent_res, dict) else agent_res
        papers = papers or []
        return {
            "query": query,
            "count": len(papers),
            "papers": papers
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
        agent_res = search_agent.get_trending_papers(category, max_results=max_results)
        papers = agent_res.get("papers") if isinstance(agent_res, dict) else agent_res
        papers = papers or []
        return {
            "category": category,
            "count": len(papers),
            "papers": papers
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
        agent_res = search_agent.suggest_papers(session_context, max_suggestions=max_suggestions)
        suggestions = agent_res.get("suggestions") if isinstance(agent_res, dict) else agent_res
        suggestions = suggestions or []

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
# -----------------------------
# Fetch ArXiv Paper Endpoint
# -----------------------------
@router.post("/fetch_arxiv")
async def fetch_arxiv_paper(request: FetchArxivRequest):
    """Fetch a paper from ArXiv and add to session"""
    try:
        # Clean arxiv_id - remove version suffix for storage key
        clean_id = request.arxiv_id.split('v')[0] if 'v' in request.arxiv_id else request.arxiv_id

        logger.info(f"Fetching ArXiv paper {request.arxiv_id} (clean: {clean_id}) for session {request.session_id}")

        # Fetch PDF - fetcher handles version numbers internally
        pdf_path = fetcher.fetch(request.arxiv_id)

        # Analyze it
        analysis = orchestrator.analysis_agent.analyze(clean_id, pdf_path)

        # Add to session using clean_id as the key
        session_manager.add_paper_to_session(request.session_id, clean_id, analysis)

        return {
            "status": "success",
            "paper_id": clean_id,
            "session_id": request.session_id,
            "num_claims": analysis.get("num_claims", 0)
        }
    except Exception as e:
        logger.error(f"Error fetching ArXiv paper {request.arxiv_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# -----------------------------
# Search ArXiv Direct (alternative)
# -----------------------------
@router.get("/search_arxiv_direct")
async def search_arxiv_papers(query: str, max_results: int = 8):
    """Direct ArXiv search endpoint"""
    try:
        logger.info(f"Searching ArXiv for: {query}")

        # Create client (required in newer arxiv library versions)
        client = arxiv.Client()

        # Create search
        search = arxiv.Search(
            query=query,
            max_results=max_results,
            sort_by=arxiv.SortCriterion.Relevance
        )

        results = []
        # Use client.results() instead of search.results()
        for result in client.results(search):
            arxiv_id = result.entry_id.split('/')[-1].split('v')[0]
            results.append({
                "id": arxiv_id,
                "title": result.title,
                "authors": [a.name for a in result.authors[:3]],
                "abstract": result.summary[:250] + "..." if len(result.summary) > 250 else result.summary,
                "published": str(result.published.date())
            })

        logger.info(f"Found {len(results)} papers for query: {query}")
        return {"results": results, "query": query}

    except Exception as e:
        logger.error(f"ArXiv search error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# -----------------------------
# Trending Papers Fallback (internal helper)
# -----------------------------
async def get_trending_papers():
    """Get currently trending/popular papers from ArXiv"""
    try:
        categories = ["cs.LG", "cs.AI", "cs.CL", "cs.CV"]
        suggestions = []

        client = arxiv.Client()

        for category in categories:
            search = arxiv.Search(
                query=f"cat:{category}",
                max_results=2,
                sort_by=arxiv.SortCriterion.SubmittedDate
            )

            for result in client.results(search):
                arxiv_id = result.entry_id.split('/')[-1].split('v')[0]
                suggestions.append({
                    "id": arxiv_id,
                    "title": result.title,
                    "authors": [a.name for a in result.authors[:3]],
                    "abstract": result.summary[:200] + "..." if len(result.summary) > 200 else result.summary,
                    "published": str(result.published.date()),
                    "category": category
                })

        return {
            "suggestions": suggestions,
            "type": "trending",
            "note": "These are recent popular papers. Upload a paper to get personalized suggestions."
        }

    except Exception as e:
        logger.error(f"Error fetching trending papers: {e}")
        return {
            "suggestions": [],
            "error": "Could not fetch trending papers"
        }


# -----------------------------
# Smart Paper Suggestions (AI-powered)
# -----------------------------
@router.post("/suggest_related_papers")
async def suggest_related_papers(request: dict):
    """
    Intelligently suggest related papers based on existing analyses.
    Uses Gemini to understand the research topics and search ArXiv.
    Accepts a simple dict payload with optional 'session_id' to avoid needing an extra Pydantic model import.
    """
    try:
        # Extract session id from the incoming request dict or object
        session_id = None
        if isinstance(request, dict):
            session_id = request.get("session_id")
        else:
            session_id = getattr(request, "session_id", None)

        logger.info(f"Generating smart suggestions for session {session_id}")

        # Load session
        session = session_manager.load_session(session_id) if session_id else {}
        analyses = session.get("analysis_results", {}) if session else {}

        if not analyses:
            # No papers yet - return trending papers from ArXiv
            return await get_trending_papers()

        # Extract key information from existing papers
        all_claims = []
        all_methods = set()
        all_metrics = set()

        for paper_id, analysis in analyses.items():
            for claim in analysis.get("claims", []):
                all_claims.append(claim.get("text", ""))
                all_methods.update(claim.get("methods", []))
                all_metrics.update(claim.get("metrics", []))

        # Use Gemini to understand the research domain and generate search queries
        from app.llm.llm_client import LLMClient
        llm = LLMClient()

        # Create a prompt for understanding the research domain
        context = {
            "sample_claims": all_claims[:5],
            "methods": list(all_methods)[:10],
            "metrics": list(all_metrics)[:10]
        }

        prompt = f"""Based on this research context, generate 3-5 specific ArXiv search queries 
to find highly related papers. Return ONLY a JSON array of search strings.

Context:
- Sample claims: {context['sample_claims']}
- Methods used: {context['methods']}
- Metrics: {context['metrics']}

Return format: ["query1", "query2", "query3"]
Focus on: specific techniques, models, datasets, or problem domains mentioned.
"""

        try:
            response = llm.call(prompt, max_tokens=200, temperature=0.3)
            # Parse search queries from LLM response
            import json
            import re

            # Clean response
            cleaned = response.strip()
            if "```" in cleaned:
                match = re.search(r'```(?:json)?\s*(\[.*?\])\s*```', cleaned, re.DOTALL)
                if match:
                    cleaned = match.group(1)

            search_queries = json.loads(cleaned)
            logger.info(f"Generated queries: {search_queries}")

        except Exception as e:
            logger.warning(f"LLM query generation failed: {e}. Using fallback.")
            # Fallback: use methods and claims directly
            search_queries = [
                " ".join(list(all_methods)[:3]),
                " ".join(all_claims[0].split()[:10]) if all_claims else "machine learning"
            ]

        # Search ArXiv with generated queries
        suggestions = []
        seen_ids = set(analyses.keys())  # Don't suggest papers we already have

        client = arxiv.Client()

        for query in search_queries[:3]:  # Limit to 3 queries
            try:
                search = arxiv.Search(
                    query=query,
                    max_results=3,
                    sort_by=arxiv.SortCriterion.Relevance
                )

                for result in client.results(search):
                    arxiv_id = result.entry_id.split('/')[-1].split('v')[0]

                    if arxiv_id not in seen_ids:
                        suggestions.append({
                            "id": arxiv_id,
                            "title": result.title,
                            "authors": [a.name for a in result.authors[:3]],
                            "abstract": result.summary[:200] + "..." if len(result.summary) > 200 else result.summary,
                            "published": str(result.published.date()),
                            "relevance_query": query
                        })
                        seen_ids.add(arxiv_id)

                        if len(suggestions) >= 6:  # Limit total suggestions
                            break

                if len(suggestions) >= 6:
                    break

            except Exception as e:
                logger.warning(f"ArXiv search failed for query '{query}': {e}")
                continue

        return {
            "suggestions": suggestions,
            "based_on_methods": list(all_methods)[:5],
            "search_queries_used": search_queries[:3]
        }

    except Exception as e:
        logger.error(f"Error generating suggestions: {e}")
        # Fallback to trending papers
        return await get_trending_papers()