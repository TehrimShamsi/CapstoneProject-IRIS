# iris/backend/app/tools/arxiv_fetcher.py
import arxiv
import os
import time
from typing import List, Dict, Any, Optional
from app.utils.observability import logger

class ArxivFetcher:
    """
    Enhanced ArxivFetcher with search capabilities and rate limiting.
    
    Features:
    - Search papers by query
    - Download PDFs by arXiv ID
    - Automatic retry with exponential backoff
    - Rate limiting compliance
    """
    
    def __init__(self, download_dir="papers"):
        self.download_dir = download_dir
        os.makedirs(download_dir, exist_ok=True)
        
        # Rate limiting: ArXiv recommends 1 request per 3 seconds
        self.last_request_time = 0
        self.min_request_interval = 3.0  # seconds
        
    def _rate_limit(self):
        """Ensure we don't exceed ArXiv rate limits."""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.min_request_interval:
            sleep_time = self.min_request_interval - elapsed
            logger.info(f"Rate limiting: sleeping {sleep_time:.2f}s")
            time.sleep(sleep_time)
        self.last_request_time = time.time()
    
    def _retry_with_backoff(self, func, max_retries=3, initial_delay=5.0):
        """
        Retry a function with exponential backoff.
        
        Args:
            func: Function to retry
            max_retries: Maximum number of retry attempts
            initial_delay: Initial delay in seconds (doubles each retry)
        """
        delay = initial_delay
        last_error = None
        
        for attempt in range(max_retries):
            try:
                return func()
            except arxiv.HTTPError as e:
                last_error = e
                status = e.status if hasattr(e, 'status') else 0
                
                if status == 429:  # Too Many Requests
                    logger.warning(f"Rate limited (429). Retry {attempt + 1}/{max_retries} after {delay}s")
                elif status == 503:  # Service Unavailable
                    logger.warning(f"Service unavailable (503). Retry {attempt + 1}/{max_retries} after {delay}s")
                else:
                    logger.error(f"HTTP error {status}. Retry {attempt + 1}/{max_retries} after {delay}s")
                
                if attempt < max_retries - 1:
                    time.sleep(delay)
                    delay *= 2  # Exponential backoff
                else:
                    logger.error(f"Max retries ({max_retries}) exceeded")
                    raise last_error
            except Exception as e:
                logger.error(f"Unexpected error in retry: {e}")
                raise
        
        raise last_error

    def search(
        self, 
        query: str, 
        max_results: int = 10,
        sort_by: arxiv.SortCriterion = arxiv.SortCriterion.Relevance,
        sort_order: arxiv.SortOrder = arxiv.SortOrder.Descending
    ) -> List[Dict[str, Any]]:
        """
        Search ArXiv for papers matching the query.
        
        Args:
            query: Search query string
            max_results: Maximum number of results to return
            sort_by: Sort criterion (Relevance, LastUpdatedDate, SubmittedDate)
            sort_order: Sort order (Ascending, Descending)
            
        Returns:
            List of paper metadata dictionaries
            
        Raises:
            RuntimeError: If search fails after retries
        """
        logger.info(f"Searching ArXiv: '{query}' (max_results={max_results})")
        
        def _search():
            self._rate_limit()
            
            search = arxiv.Search(
                query=query,
                max_results=max_results,
                sort_by=sort_by,
                sort_order=sort_order
            )
            
            results = []
            try:
                for result in search.results():
                    results.append({
                        "arxiv_id": result.entry_id.split("/")[-1],
                        "title": result.title,
                        "authors": [author.name for author in result.authors],
                        "abstract": result.summary,
                        "published": str(result.published.date()),
                        "updated": str(result.updated.date()) if result.updated else None,
                        "pdf_url": result.pdf_url,
                        "categories": result.categories,
                        "primary_category": result.primary_category,
                    })
            except StopIteration:
                pass
            
            return results
        
        try:
            results = self._retry_with_backoff(_search)
            logger.info(f"Found {len(results)} papers for query '{query}'")
            return results
        except Exception as e:
            error_msg = f"Failed to search ArXiv: {str(e)}"
            logger.error(error_msg)
            raise RuntimeError(error_msg) from e

    def fetch(self, arxiv_id: str) -> str:
        """
        Download a PDF from arXiv by paper ID.
        
        Args:
            arxiv_id: ArXiv paper ID (e.g., "2301.12345")
            
        Returns:
            Path to downloaded PDF file
            
        Raises:
            ValueError: If paper not found
            RuntimeError: If download fails after retries
        """
        logger.info(f"Fetching paper: {arxiv_id}")
        
        def _fetch():
            self._rate_limit()
            
            search = arxiv.Search(id_list=[arxiv_id])
            result = next(search.results(), None)

            if not result:
                raise ValueError(f"Paper {arxiv_id} not found on ArXiv")

            # Save into the download directory with a sanitized filename.
            filename = f"{arxiv_id.replace('/', '_')}.pdf"
            dirpath = self.download_dir

            # The `arxiv` library expects a directory path (dirpath) and optional filename.
            # Passing a full filepath previously caused the library to treat it as a directory
            # which led to errors like: No such file or directory: 'papers\\<id>.pdf\\<file>.pdf'
            result.download_pdf(dirpath=dirpath, filename=filename)

            paper_path = os.path.join(dirpath, filename)
            return paper_path
        
        try:
            path = self._retry_with_backoff(_fetch)
            logger.info(f"Downloaded {arxiv_id} to {path}")
            return path
        except ValueError:
            # Paper not found - don't retry
            raise
        except Exception as e:
            error_msg = f"Failed to fetch {arxiv_id}: {str(e)}"
            logger.error(error_msg)
            raise RuntimeError(error_msg) from e
    
    def get_trending_papers(
        self, 
        category: str = "cs.AI", 
        max_results: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get recently published papers in a category.
        
        Args:
            category: ArXiv category (e.g., "cs.AI", "cs.LG")
            max_results: Maximum number of results
            
        Returns:
            List of recent paper metadata
        """
        logger.info(f"Fetching trending papers from {category}")
        
        query = f"cat:{category}"
        return self.search(
            query=query,
            max_results=max_results,
            sort_by=arxiv.SortCriterion.SubmittedDate,
            sort_order=arxiv.SortOrder.Descending
        )
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