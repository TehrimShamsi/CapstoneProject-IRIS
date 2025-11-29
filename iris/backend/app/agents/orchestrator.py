# backend/app/agents/orchestrator.py
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from app.agents.analysis_agent import AnalysisAgent
from app.agents.synthesis_agent import SynthesisAgent
from app.agents.fetch_agent import FetchAgent
from app.agents.loop_refinement_agent import LoopRefinementAgent
from app.utils.observability import logger
from app.protocol.a2a_messages import MessageRouter, A2AAgent, create_trace_id, TaskMessage


class Orchestrator(A2AAgent):
    """
    Central orchestrator with A2A protocol support
    Coordinates multi-agent workflows
    """

    def __init__(self, session_manager=None, enable_a2a: bool = True):
        self.session_manager = session_manager

        # Initialize message router if A2A enabled
        self.router = None
        if enable_a2a:
            self.router = MessageRouter()
            super().__init__("Orchestrator", self.router)

        # Initialize agents (with or without A2A support)
        # FetchAgent currently does not require router in the original usage
        self.fetch_agent = FetchAgent()
        if enable_a2a:
            self.analysis_agent = AnalysisAgent(router=self.router)
            # SynthesisAgent does not accept a router parameter; instantiate normally
            self.synthesis_agent = SynthesisAgent()
        else:
            self.analysis_agent = AnalysisAgent()
            self.synthesis_agent = SynthesisAgent()

        self.loop_agent = LoopRefinementAgent()

    def analyze_paper(self, session_id: str, paper_id: str):
        """
        Analyze a single paper and store result in session.
        Returns the analysis result immediately.

        Supports both A2A protocol and direct calls.
        """
        from app.tools.arxiv_fetcher import ArxivFetcher
        from app.tools.pdf_processor import PDFProcessor
        from pathlib import Path
        import os

        trace_id = create_trace_id()
        logger.info(f"[ORCH:{trace_id}] Starting analysis for paper: {paper_id}")

        try:
            # Check if PDF already exists locally
            pdf_processor = PDFProcessor()
            pdf_path = str(pdf_processor.base / f"{paper_id}.pdf")

            if os.path.exists(pdf_path):
                logger.info(f"[ORCH:{trace_id}] Found local PDF: {pdf_path}")
            else:
                logger.info(f"[ORCH:{trace_id}] PDF not found locally, fetching from arXiv: {paper_id}")
                fetcher = ArxivFetcher()
                pdf_path = fetcher.fetch(paper_id)

            logger.info(f"[ORCH:{trace_id}] PDF ready: {pdf_path}")

            # Run analysis (with A2A protocol if enabled)
            if self.router:
                # Send task message to Analysis Agent
                self.send_task(
                    to_agent="AnalysisAgent",
                    task_name="analyze_paper",
                    parameters={"paper_id": paper_id, "pdf_path": pdf_path},
                    trace_id=trace_id
                )

                # For now, also do direct call (hybrid approach)
                # In full A2A, we'd wait for result message
                analysis_result = self.analysis_agent.analyze(paper_id, pdf_path, trace_id=trace_id)
            else:
                # Direct call (original behavior)
                analysis_result = self.analysis_agent.analyze(paper_id, pdf_path)

            logger.info(f"[ORCH:{trace_id}] Analysis complete for {paper_id}: {analysis_result.get('num_claims', 0)} claims extracted")

            # Store in session
            if self.session_manager:
                try:
                    self.session_manager.add_paper_to_session(session_id, paper_id, analysis_result)
                    logger.info(f"[ORCH:{trace_id}] Analysis stored in session {session_id}")
                except Exception as se:
                    logger.warning(f"Failed to add paper to session: {se}")
                    session = self.session_manager.get_session(session_id)
                    if "analysis_results" not in session:
                        session["analysis_results"] = {}
                    session["analysis_results"][paper_id] = analysis_result
                    self.session_manager._atomic_write(
                        self.session_manager._session_path(session_id),
                        session
                    )

            return {
                "status": "success",
                "paper_id": paper_id,
                "analysis": analysis_result,
                "trace_id": trace_id
            }

        except Exception as e:
            logger.error(f"[ORCH:{trace_id}] Analysis failed for {paper_id}: {str(e)}")
            if self.router:
                self.send_error(
                    error_code="ORCHESTRATION_FAILED",
                    error_message=str(e),
                    trace_id=trace_id
                )
            raise

    def synthesize(self, session_id: str, paper_ids: list):
        """
        Synthesize multiple analyzed papers.
        """
        trace_id = create_trace_id()
        logger.info(f"[ORCH:{trace_id}] Starting synthesis for {len(paper_ids)} papers")

        if not self.session_manager:
            raise ValueError("SessionManager required for synthesis")

        session = self.session_manager.get_session(session_id)
        analyses = []

        # Collect analyses
        for paper_id in paper_ids:
            paper_entry = session.get("papers", {}).get(paper_id)
            if paper_entry and paper_entry.get("analysis"):
                analyses.append(paper_entry.get("analysis"))
                continue

            if paper_id in session.get("analysis_results", {}):
                analyses.append(session["analysis_results"][paper_id])
            else:
                logger.warning(f"[ORCH:{trace_id}] Paper {paper_id} not found in session")

        if len(analyses) < 2:
            raise ValueError("Need at least 2 analyzed papers for synthesis")

        # Run synthesis (with A2A if enabled)
        if self.router:
            self.send_task(
                to_agent="SynthesisAgent",
                task_name="synthesize_papers",
                parameters={"analyses": analyses},
                trace_id=trace_id
            )
            synthesis_result = self.synthesis_agent.synthesize(analyses, trace_id=trace_id)
        else:
            synthesis_result = self.synthesis_agent.synthesize(analyses)

        logger.info(f"[ORCH:{trace_id}] Synthesis complete: {synthesis_result.get('num_consensus', 0)} consensus found")

        # Store synthesis result
        session["synthesis_result"] = synthesis_result
        self.session_manager._atomic_write(
            self.session_manager._session_path(session_id),
            session
        )

        return synthesis_result

    def process_papers_parallel(self, arxiv_ids: list):
        """
        Full pipeline: Fetch → Analyze → Synthesize → Refine
        """
        trace_id = create_trace_id()
        logger.info(f"[ORCH:{trace_id}] Starting parallel processing for {len(arxiv_ids)} papers")

        # Parallel Fetching
        with ThreadPoolExecutor(max_workers=3) as exe:
            fetch_jobs = [exe.submit(self.fetch_agent.fetch_and_extract, pid) for pid in arxiv_ids]
            fetch_results = [f.result() for f in fetch_jobs]

        logger.info(f"[ORCH:{trace_id}] Fetch complete")

        # Parallel Analysis
        from app.tools.arxiv_fetcher import ArxivFetcher
        fetcher = ArxivFetcher()

        with ThreadPoolExecutor(max_workers=3) as exe:
            analysis_jobs = []
            for arxiv_id in arxiv_ids:
                pdf_path = fetcher.fetch(arxiv_id)
                job = exe.submit(self.analysis_agent.analyze, arxiv_id, pdf_path, trace_id)
                analysis_jobs.append(job)

            analyses = [a.result() for a in analysis_jobs]

        logger.info(f"[ORCH:{trace_id}] Analysis complete")

        # Sequential Synthesis
        synthesis_output = self.synthesis_agent.synthesize(analyses, trace_id=trace_id)
        logger.info(f"[ORCH:{trace_id}] Synthesis complete")

        # Loop Refinement
        refined_output = self.loop_agent.refine(synthesis_output)
        logger.info(f"[ORCH:{trace_id}] Loop refinement complete")

        return refined_output

    # ============================================
    # A2A Protocol Handlers
    # ============================================

    def handle_task(self, message):
        """Handle incoming tasks (not typically used by orchestrator)"""
        pass

    def handle_result(self, message: TaskMessage):
        """Handle result messages from agents"""
        logger.info(f"[ORCH] Received result from {message.from_agent}: {message.payload.get('task_id')}")
        # Store results, trigger next steps, etc.