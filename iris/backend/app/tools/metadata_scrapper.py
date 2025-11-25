import arxiv

class MetadataScraper:
    def get_metadata(self, arxiv_id: str) -> dict:
        search = arxiv.Search(id_list=[arxiv_id])
        result = next(search.results(), None)

        if not result:
            raise ValueError("Metadata not found.")

        return {
            "paper_id": arxiv_id,
            "title": result.title,
            "authors": [a.name for a in result.authors],
            "abstract": result.summary,
            "published": str(result.published.date())
        }
