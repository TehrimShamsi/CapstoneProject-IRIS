import arxiv
import os
import ssl
from typing import List, Dict, Any, Optional
from pathlib import Path

# Import shared config
try:
    from app.config import PDFS_DIR
except ImportError:
    PDFS_DIR = Path("data/pdfs")
    PDFS_DIR.mkdir(parents=True, exist_ok=True)

# Import logger separately to avoid circular imports
try:
    from app.utils.observability import logger
except ImportError:
    import logging
    logger = logging.getLogger(__name__)

# Fix SSL certificate verification issues on Windows
def _create_unverified_context():
    """Create an unverified SSL context for downloads."""
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    return context

# Set the default opener to use unverified SSL context
ssl._create_default_https_context = _create_unverified_context


class ArxivFetcher:
    """
    Fetches papers from ArXiv with intelligent caching and error handling.
    All PDFs stored in a centralized location (data/pdfs/).
    """
    
    def __init__(self, download_dir: Optional[str] = None):
        # Use shared config directory by default
        self.download_dir = download_dir if download_dir else str(PDFS_DIR)
        os.makedirs(self.download_dir, exist_ok=True)
        logger.info(f"ArxivFetcher initialized with download_dir: {self.download_dir}")

    def fetch(self, arxiv_id: str) -> str:
        """
        Downloads a PDF from arXiv and returns file path.
        Handles version suffixes like v1, v2, etc.
        Caches downloads to avoid re-fetching.
        """
        try:
            # Strip version suffix if present (e.g., "2306.11113v2" -> "2306.11113")
            clean_id = arxiv_id.split('v')[0] if 'v' in arxiv_id and arxiv_id.split('v')[-1].isdigit() else arxiv_id
            
            logger.info(f"Fetching paper {arxiv_id} (clean_id: {clean_id})")
            
            # Create safe filename using the original arxiv_id
            safe_id = arxiv_id.replace('/', '_').replace(':', '_')
            paper_filename = f"{safe_id}.pdf"
            paper_path = os.path.join(self.download_dir, paper_filename)
            
            # Check if already exists (caching)
            if os.path.exists(paper_path):
                logger.info(f"Paper {arxiv_id} already exists at {paper_path} (cache hit)")
                return paper_path
            
            # Create client with default config
            client = arxiv.Client()
            
            # Search for the paper using clean ID
            search = arxiv.Search(id_list=[clean_id])
            
            # Get first result
            try:
                result = next(client.results(search))
            except StopIteration:
                raise ValueError(f"Paper {arxiv_id} not found on ArXiv.")
            
            # Download PDF - CRITICAL: use dirpath and filename separately
            logger.info(f"Downloading PDF to {paper_path}")
            result.download_pdf(dirpath=self.download_dir, filename=paper_filename)
            
            logger.info(f"Successfully downloaded {arxiv_id} ({os.path.getsize(paper_path) / 1024:.2f} KB)")
            return paper_path
            
        except Exception as e:
            logger.error(f"Error fetching paper {arxiv_id}: {e}")
            raise

    def search(self, query: str, max_results: int = 10, sort_by: arxiv.SortCriterion = arxiv.SortCriterion.Relevance) -> List[Dict[str, Any]]:
        """
        Search ArXiv for papers matching the query.
        
        Args:
            query: Search query string
            max_results: Maximum number of results to return
            sort_by: Sort criterion (Relevance, LastUpdatedDate, SubmittedDate)
            
        Returns:
            List of paper metadata dictionaries
        """
        try:
            logger.info(f"Searching ArXiv: '{query}' (max_results={max_results})")
            
            # Create client
            client = arxiv.Client()
            
            # Create search
            search = arxiv.Search(
                query=query,
                max_results=max_results,
                sort_by=sort_by
            )
            
            results = []
            # Iterate through results using the client
            for result in client.results(search):
                try:
                    # Extract clean arxiv_id
                    entry_id = result.entry_id
                    if "/" in entry_id:
                        arxiv_id = entry_id.split("/")[-1]
                    elif ":" in entry_id:
                        arxiv_id = entry_id.split(":")[-1]
                    else:
                        arxiv_id = entry_id
                    
                    paper_info = {
                        "arxiv_id": arxiv_id,
                        "title": result.title,
                        "authors": [author.name for author in result.authors],
                        "summary": result.summary,
                        "published": result.published.isoformat() if hasattr(result, 'published') and result.published else None,
                        "updated": result.updated.isoformat() if hasattr(result, 'updated') and result.updated else None,
                        "pdf_url": result.pdf_url if hasattr(result, 'pdf_url') else None,
                        "primary_category": result.primary_category if hasattr(result, 'primary_category') else None,
                        "categories": result.categories if hasattr(result, 'categories') else [],
                        "comment": result.comment if hasattr(result, 'comment') else None,
                        "journal_ref": result.journal_ref if hasattr(result, 'journal_ref') else None,
                    }
                    results.append(paper_info)
                except Exception as e:
                    logger.warning(f"Error processing search result: {e}")
                    continue
            
            logger.info(f"Found {len(results)} papers for query: {query}")
            return results
            
        except Exception as e:
            logger.error(f"ArXiv search error for query '{query}': {e}")
            import traceback
            logger.error(traceback.format_exc())
            raise Exception(f"Failed to search ArXiv: {str(e)}")

    def get_trending_papers(self, category: str = "cs.AI", max_results: int = 10) -> List[Dict[str, Any]]:
        """
        Get recently published papers from a specific category.
        
        Args:
            category: ArXiv category (e.g., 'cs.AI', 'cs.LG', 'cs.CL')
            max_results: Maximum number of results
            
        Returns:
            List of paper metadata dictionaries
        """
        try:
            logger.info(f"Fetching trending papers from {category}")
            
            # Create client
            client = arxiv.Client()
            
            # Create search for category
            search = arxiv.Search(
                query=f"cat:{category}",
                max_results=max_results,
                sort_by=arxiv.SortCriterion.SubmittedDate
            )
            
            results = []
            for result in client.results(search):
                try:
                    # Extract clean arxiv_id
                    entry_id = result.entry_id
                    if "/" in entry_id:
                        arxiv_id = entry_id.split("/")[-1]
                    elif ":" in entry_id:
                        arxiv_id = entry_id.split(":")[-1]
                    else:
                        arxiv_id = entry_id
                    
                    paper_info = {
                        "arxiv_id": arxiv_id,
                        "title": result.title,
                        "authors": [author.name for author in result.authors],
                        "summary": result.summary[:300] + "..." if len(result.summary) > 300 else result.summary,
                        "published": result.published.isoformat() if hasattr(result, 'published') and result.published else None,
                        "pdf_url": result.pdf_url if hasattr(result, 'pdf_url') else None,
                        "categories": result.categories if hasattr(result, 'categories') else [],
                    }
                    results.append(paper_info)
                except Exception as e:
                    logger.warning(f"Error processing trending paper: {e}")
                    continue
            
            logger.info(f"Found {len(results)} trending papers in {category}")
            return results
            
        except Exception as e:
            logger.error(f"Error fetching trending papers: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return []  # Return empty list instead of raising

    def fetch_metadata(self, arxiv_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch metadata for a specific paper without downloading.
        
        Args:
            arxiv_id: ArXiv paper ID
            
        Returns:
            Paper metadata dictionary or None
        """
        try:
            # Strip version suffix
            clean_id = arxiv_id.split('v')[0] if 'v' in arxiv_id and arxiv_id.split('v')[-1].isdigit() else arxiv_id
            
            # Create client
            client = arxiv.Client()
            
            # Search for paper
            search = arxiv.Search(id_list=[clean_id])
            
            # Get first result
            try:
                result = next(client.results(search))
            except StopIteration:
                logger.warning(f"Paper {arxiv_id} not found")
                return None
            
            return {
                "arxiv_id": arxiv_id,
                "title": result.title,
                "authors": [author.name for author in result.authors],
                "summary": result.summary,
                "published": result.published.isoformat() if hasattr(result, 'published') and result.published else None,
                "updated": result.updated.isoformat() if hasattr(result, 'updated') and result.updated else None,
                "pdf_url": result.pdf_url if hasattr(result, 'pdf_url') else None,
                "categories": result.categories if hasattr(result, 'categories') else [],
                "primary_category": result.primary_category if hasattr(result, 'primary_category') else None,
            }
            
        except Exception as e:
            logger.error(f"Error fetching metadata for {arxiv_id}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None