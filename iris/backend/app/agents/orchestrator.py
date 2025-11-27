from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Any
from app.agents.analysis_agent import AnalysisAgent
from app.agents.synthesis_agent import SynthesisAgent
from app.agents.fetch_agent import FetchAgent
from app.agents.loop_refinement_agent import LoopRefinementAgent
from app.utils.observability import logger


class Orchestrator:
    def __init__(self, session_manager=None):
        self.session_manager = session_manager
        self.fetch_agent = FetchAgent()
        self.analysis_agent = AnalysisAgent()
        self.synthesis_agent = SynthesisAgent()
        self.loop_agent = LoopRefinementAgent()

    def analyze_paper(self, session_id: str, paper_id: str) -> Dict[str, Any]:
        """
        Analyze a single paper and store results in session.
        
        Args:
            session_id: The session ID
            paper_id: The paper ID to analyze
            
        Returns:
            Analysis results dict
        """
        logger.info(f"[ORCH] Starting single paper analysis: paper_id={paper_id}, session_id={session_id}")
        
        # Get the session to ensure it exists
        if self.session_manager:
            session = self.session_manager.load_session(session_id)
            if not session:
                raise ValueError(f"Session {session_id} not found")
        
        # Get the PDF path - it should have been saved during upload
        from app.tools.pdf_processor import PDFProcessor
        pdf_processor = PDFProcessor()
        pdf_path = pdf_processor.base / f"{paper_id}.pdf"
        
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF not found at {pdf_path}")
        
        logger.info(f"[ORCH] Found PDF at {pdf_path}")
        
        # Run analysis
        try:
            analysis = self.analysis_agent.analyze(paper_id, str(pdf_path))
            logger.info(f"[ORCH] Analysis complete for {paper_id}: {len(analysis.get('claims', []))} claims extracted")
        except Exception as e:
            logger.error(f"[ORCH] Analysis failed for {paper_id}: {str(e)}")
            raise
        
        # Store in session
        if self.session_manager:
            try:
                self.session_manager.add_paper_to_session(session_id, paper_id, analysis)
                logger.info(f"[ORCH] Analysis stored in session {session_id}")
            except Exception as e:
                logger.error(f"[ORCH] Failed to store analysis in session: {str(e)}")
                raise
        
        return analysis

    def synthesize(self, session_id: str, paper_ids: list) -> Dict[str, Any]:
        """
        Synthesize multiple papers.
        
        Args:
            session_id: The session ID
            paper_ids: List of paper IDs to synthesize
            
        Returns:
            Synthesis results dict
        """
        logger.info(f"[ORCH] Starting synthesis for {len(paper_ids)} papers in session {session_id}")
        
        if self.session_manager:
            session = self.session_manager.load_session(session_id)
            if not session:
                raise ValueError(f"Session {session_id} not found")
        
        # Collect analyses from the session
        analyses = []
        if self.session_manager:
            session = self.session_manager.load_session(session_id)
            for pid in paper_ids:
                if pid in session.get("papers", {}):
                    paper_data = session["papers"][pid]
                    if "analysis" in paper_data:
                        analyses.append(paper_data["analysis"])
        
        if not analyses:
            logger.warning(f"[ORCH] No analyses found for papers {paper_ids}")
            return {"num_papers": 0, "consensus": [], "contradictions": []}
        
        # Run synthesis
        try:
            synthesis_output = self.synthesis_agent.synthesize(analyses)
            logger.info(f"[ORCH] Synthesis complete: {len(synthesis_output.get('consensus', []))} consensus, {len(synthesis_output.get('contradictions', []))} contradictions")
        except Exception as e:
            logger.error(f"[ORCH] Synthesis failed: {str(e)}")
            raise
        
        # Store synthesis result in session
        if self.session_manager:
            try:
                session = self.session_manager.load_session(session_id)
                session["synthesis_result"] = synthesis_output
                session["updated_at"] = self.session_manager.__class__.__dict__.get("iso_now", lambda: "")() if hasattr(self.session_manager, "iso_now") else None
                self.session_manager._atomic_write(self.session_manager._session_path(session_id), session)
                logger.info(f"[ORCH] Synthesis stored in session {session_id}")
            except Exception as e:
                logger.error(f"[ORCH] Failed to store synthesis in session: {str(e)}")
        
        return synthesis_output

    def process_papers_parallel(self, arxiv_ids: list):
        """
        Legacy method: Step 1: Fetch PDFs in parallel
        Step 2: Analyze each paper in parallel
        Step 3: Synthesize findings
        Step 4: Loop refine
        """

        logger.info("\n[ORCH] Starting parallel processing...")

        # --- Parallel Fetching ---
        with ThreadPoolExecutor(max_workers=3) as exe:
            fetch_jobs = [exe.submit(self.fetch_agent.fetch_and_extract, pid) for pid in arxiv_ids]
            fetch_results = [f.result() for f in fetch_jobs]

        logger.info("[ORCH] Fetch complete.")

        # --- Parallel Analysis ---
        from app.tools.arxiv_fetcher import ArxivFetcher
        fetcher = ArxivFetcher()

        with ThreadPoolExecutor(max_workers=3) as exe:
            analysis_jobs = []
            for arxiv_id in arxiv_ids:
                pdf_path = fetcher.fetch(arxiv_id)
                job = exe.submit(self.analysis_agent.analyze, arxiv_id, pdf_path)
                analysis_jobs.append(job)

            analyses = [a.result() for a in analysis_jobs]

        logger.info("[ORCH] Analysis complete.")

        # --- Sequential Synthesis ---
        synthesis_output = self.synthesis_agent.synthesize(analyses)
        logger.info("[ORCH] Synthesis complete.")

        # --- Loop Refinement ---
        refined_output = self.loop_agent.refine(synthesis_output)
        logger.info("[ORCH] Loop refinement complete.")

        return refined_output