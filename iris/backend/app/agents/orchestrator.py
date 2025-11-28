# iris/backend/app/agents/orchestrator.py
from concurrent.futures import ThreadPoolExecutor
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

    def analyze_paper(self, session_id: str, paper_id: str):
        """
        Analyze a single paper and store result in session.
        Returns the analysis result immediately.
        """
        from app.tools.arxiv_fetcher import ArxivFetcher
        
        logger.info(f"[ORCH] Starting analysis for paper: {paper_id}")
        
        fetcher = ArxivFetcher()
        
        try:
            # Ensure we have the PDF
            pdf_path = fetcher.fetch(paper_id)
            logger.info(f"[ORCH] PDF fetched: {pdf_path}")
            
            # Run analysis
            analysis_result = self.analysis_agent.analyze(paper_id, pdf_path)
            logger.info(f"[ORCH] Analysis complete for {paper_id}: {analysis_result.get('num_claims', 0)} claims extracted")
            
            # Store in session using SessionManager helper (keeps papers mapping consistent)
            if self.session_manager:
                try:
                    self.session_manager.add_paper_to_session(session_id, paper_id, analysis_result)
                    logger.info(f"[ORCH] Analysis stored in session {session_id} under papers.{paper_id}")
                except Exception as se:
                    # Fallback: if add_paper_to_session fails, write to legacy analysis_results
                    logger.warning(f"Failed to add paper to session via SessionManager: {se}. Falling back to analysis_results storage.")
                    session = self.session_manager.get_session(session_id)
                    if "analysis_results" not in session:
                        session["analysis_results"] = {}
                    session["analysis_results"][paper_id] = analysis_result
                    self.session_manager._atomic_write(
                        self.session_manager._session_path(session_id),
                        session
                    )
                    logger.info(f"[ORCH] Analysis stored in session {session_id} under analysis_results.{paper_id}")
            
            return {
                "status": "success",
                "paper_id": paper_id,
                "analysis": analysis_result
            }
            
        except Exception as e:
            logger.error(f"[ORCH] Analysis failed for {paper_id}: {str(e)}")
            raise

    def synthesize(self, session_id: str, paper_ids: list):
        """
        Synthesize multiple analyzed papers.
        """
        logger.info(f"[ORCH] Starting synthesis for {len(paper_ids)} papers")
        
        if not self.session_manager:
            raise ValueError("SessionManager required for synthesis")
        
        session = self.session_manager.get_session(session_id)
        analyses = []

        # Collect analyses for selected papers — prefer `session['papers'][pid]['analysis']`
        for paper_id in paper_ids:
            paper_entry = session.get("papers", {}).get(paper_id)
            if paper_entry and paper_entry.get("analysis"):
                analyses.append(paper_entry.get("analysis"))
                continue

            # Fallback to legacy analysis_results key
            if paper_id in session.get("analysis_results", {}):
                analyses.append(session["analysis_results"][paper_id])
            else:
                logger.warning(f"[ORCH] Paper {paper_id} not found in session")
        
        if len(analyses) < 2:
            raise ValueError("Need at least 2 analyzed papers for synthesis")
        
        # Run synthesis
        synthesis_result = self.synthesis_agent.synthesize(analyses)
        logger.info(f"[ORCH] Synthesis complete: {synthesis_result.get('num_consensus', 0)} consensus found")
        
        # Store synthesis result
        session["synthesis_result"] = synthesis_result
        self.session_manager._atomic_write(
            self.session_manager._session_path(session_id), 
            session
        )
        
        return synthesis_result

    def process_papers_parallel(self, arxiv_ids: list):
        """
        Step 1: Fetch PDFs in parallel
        Step 2: Analyze each paper in parallel
        Step 3: Synthesize findings
        Step 4: Loop refine
        """

        print("\n[ORCH] Starting parallel processing...")

        # --- Parallel Fetching ---
        with ThreadPoolExecutor(max_workers=3) as exe:
            fetch_jobs = [exe.submit(self.fetch_agent.fetch_and_extract, pid) for pid in arxiv_ids]
            fetch_results = [f.result() for f in fetch_jobs]

        print("[ORCH] Fetch complete.")

        # --- Parallel Analysis ---
        from app.tools.arxiv_fetcher import ArxivFetcher
        fetcher = ArxivFetcher()

        with ThreadPoolExecutor(max_workers=3) as exe:
            analysis_jobs = []
            for arxiv_id in arxiv_ids:
                # ensure we have a local PDF path
                pdf_path = fetcher.fetch(arxiv_id)
                job = exe.submit(self.analysis_agent.analyze, arxiv_id, pdf_path)
                analysis_jobs.append(job)

            analyses = [a.result() for a in analysis_jobs]

        print("[ORCH] Analysis complete.")

        # --- Sequential Synthesis ---
        synthesis_output = self.synthesis_agent.synthesize(analyses)
        print("[ORCH] Synthesis complete.")

        # --- Loop Refinement ---
        refined_output = self.loop_agent.refine(synthesis_output)
        print("[ORCH] Loop refinement complete.")

        return refined_output