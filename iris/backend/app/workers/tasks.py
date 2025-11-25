from celery import Celery
from ..config import settings
from ..agents.search_agent import SearchAgent
from ..agents.fetcher_agent import FetcherAgent
from ..agents.parser_agent import ParserAgent
from ..agents.embedder import Embedder
from ..agents.analysis_agent import AnalysisAgent
from ..agents.synthesis_agent import SynthesisAgent
from ..storage.metadata_db import store_pipeline_result

celery = Celery("iris_workers", broker=settings.CELERY_BROKER_URL)

@celery.task(bind=True)
def start_research_pipeline(self, query: str, options: dict):
    trace_id = self.request.id
    # 1. Search
    search_agent = SearchAgent()
    candidates = search_agent.search(query, top_k=options.get("top_k", 10))
    # 2. Fetch PDFs (in parallel)
    fetcher = FetcherAgent()
    fetched = fetcher.fetch_many(candidates)
    # 3. Parse
    parser = ParserAgent()
    parsed = [parser.parse_pdf(f["pdf_path"], f["paper_id"]) for f in fetched if f["download_status"] == "success"]
    # 4. Embed
    embedder = Embedder()
    for paper in parsed:
        embedder.index_paper(paper)
    # 5. Analysis
    analysis_agent = AnalysisAgent()
    analyses = [analysis_agent.analyze(paper) for paper in parsed]
    # 6. Synthesis
    synth_agent = SynthesisAgent()
    synthesis = synth_agent.synthesize(analyses, query, options)
    # 7. Store + return
    store_pipeline_result(trace_id, {
        "query": query,
        "candidates": candidates,
        "analyses": analyses,
        "synthesis": synthesis
    })
    return {"task_id": trace_id, "status": "completed"}
