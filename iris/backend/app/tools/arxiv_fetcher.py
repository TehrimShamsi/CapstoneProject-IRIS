import arxiv
import os

class ArxivFetcher:
    def __init__(self, download_dir="papers"):
        self.download_dir = download_dir
        os.makedirs(download_dir, exist_ok=True)

    def fetch(self, arxiv_id: str) -> str:
        """
        Downloads a PDF from arXiv and returns file path.
        """
        search = arxiv.Search(id_list=[arxiv_id])
        result = next(search.results(), None)

        if not result:
            raise ValueError(f"Paper {arxiv_id} not found.")

        paper_path = os.path.join(self.download_dir, f"{arxiv_id}.pdf")
        result.download_pdf(paper_path)

        return paper_path
