from typing import Dict, List
from app.tools.arxiv_fetcher import ArxivFetcher
from app.tools.pdf_processor import PDFProcessor


class FetchAgent:
    """Fetches a paper (from arXiv) and extracts text chunks.

    This is a minimal implementation used by the Orchestrator. It downloads
    the PDF using `ArxivFetcher`, extracts raw text with `PDFProcessor`,
    splits the text into simple fixed-size chunks, and returns a dict with
    the expected keys: `paper_id`, `title`, `chunks`.
    """

    def __init__(self, chunk_size: int = 2000):
        self.fetcher = ArxivFetcher()
        self.processor = PDFProcessor()
        self.chunk_size = chunk_size

    def fetch_and_extract(self, arxiv_id: str) -> Dict[str, object]:
        # Download PDF and get path
        pdf_path = self.fetcher.fetch(arxiv_id)

        # Extract text
        text = self.processor.extract_text(pdf_path)

        # Very simple chunking by characters (could be improved to semantic chunks)
        chunks: List[str] = [text[i:i + self.chunk_size] for i in range(0, len(text), self.chunk_size)]

        return {
            "paper_id": arxiv_id,
            "title": arxiv_id,
            "chunks": chunks,
        }
