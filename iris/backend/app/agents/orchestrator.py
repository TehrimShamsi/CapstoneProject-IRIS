from concurrent.futures import ThreadPoolExecutor
from app.agents.analysis_agent import AnalysisAgent
from app.agents.synthesis_agent import SynthesisAgent
from app.agents.fetch_agent import FetchAgent
from app.agents.loop_refinement_agent import LoopRefinementAgent

class Orchestrator:
    def __init__(self, session_manager=None):
        self.session_manager = session_manager
        self.fetch_agent = FetchAgent()
        self.analysis_agent = AnalysisAgent()
        self.synthesis_agent = SynthesisAgent()
        self.loop_agent = LoopRefinementAgent()

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
        with ThreadPoolExecutor(max_workers=3) as exe:
            analysis_jobs = [
                exe.submit(self.analysis_agent.analyze, p["paper_id"], p["title"], p["chunks"])
                for p in fetch_results
            ]
            analyses = [a.result() for a in analysis_jobs]

        print("[ORCH] Analysis complete.")

        # --- Sequential Synthesis ---
        synthesis_output = self.synthesis_agent.synthesize(analyses)
        print("[ORCH] Synthesis complete.")

        # --- Loop Refinement ---
        refined_output = self.loop_agent.refine(synthesis_output)
        print("[ORCH] Loop refinement complete.")

        return refined_output
