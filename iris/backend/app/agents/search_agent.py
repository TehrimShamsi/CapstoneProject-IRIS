# backend/app/agents/search_agent.py
from typing import List, Dict, Any, Optional
import arxiv
from app.tools.arxiv_fetcher import ArxivFetcher
from app.utils.observability import agent_call, logger
from typing import List, Dict, Any, Optional
from app.tools.arxiv_fetcher import ArxivFetcher
from app.utils.observability import agent_call, logger
import arxiv

class SearchAgent:
    """
    Agent responsible for searching and discovering research papers.
    
    Features:
    - Search ArXiv by keyword
    - Get trending papers by category
    - Smart paper suggestions based on session history
    """
    
    def __init__(self):
        self.fetcher = ArxivFetcher()
    
    @agent_call("SearchAgent")
    def search_papers(
        self, 
        query: str, 
        max_results: int = 10,
        trace_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Search for papers on ArXiv.
        
        Args:
            query: Search query string
            max_results: Maximum number of results
            trace_id: Optional trace ID for observability
            
        Returns:
            Dictionary with search results and metadata
        """
        try:
            results = self.fetcher.search(query, max_results=max_results)
            
            return {
                "query": query,
                "total_results": len(results),
                "papers": results,
                "status": "success"
            }
        except Exception as e:
            logger.error(f"Search failed for query '{query}': {str(e)}")
            return {
                "query": query,
                "total_results": 0,
                "papers": [],
                "status": "error",
                "error": str(e)
            }
    
    @agent_call("SearchAgent")
    def get_trending_papers(
        self,
        category: str = "cs.AI",
        max_results: int = 10,
        trace_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get trending papers in a specific category.
        
        Args:
            category: ArXiv category code (e.g., "cs.AI", "cs.LG", "cs.CL")
            max_results: Maximum number of results
            trace_id: Optional trace ID for observability
            
        Returns:
            Dictionary with trending papers
        """
        logger.info(f"Fetching trending papers from {category}")
        
        try:
            papers = self.fetcher.get_trending_papers(
                category=category,
                max_results=max_results
            )
            
            return {
                "category": category,
                "total_results": len(papers),
                "papers": papers,
                "status": "success"
            }
        except Exception as e:
            logger.error(f"Failed to get trending papers: {str(e)}")
            return {
                "category": category,
                "total_results": 0,
                "papers": [],
                "status": "error",
                "error": str(e)
            }
    
    @agent_call("SearchAgent")
    def suggest_papers(
        self,
        session_id: str = "unknown",
        max_suggestions: int = 8,
        trace_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate smart paper suggestions.
        
        For now, returns trending papers. In the future, this could
        be enhanced with collaborative filtering, user preferences, etc.
        
        Args:
            session_id: User session ID (for future personalization)
            max_suggestions: Maximum number of suggestions
            trace_id: Optional trace ID for observability
            
        Returns:
            Dictionary with suggested papers
        """
        logger.info(f"Generating smart suggestions for session {session_id}")
        
        # For now, return trending AI papers
        # TODO: Implement personalized recommendations based on:
        # - Papers user has already analyzed
        # - Citation networks
        # - Topic modeling
        
        trending = self.get_trending_papers(
            category="cs.AI",
            max_results=max_suggestions
        )
        
        # Add uniqueness check
        unique_papers = []
        seen_ids = set()
        
        for paper in trending.get("papers", []):
            paper_id = paper.get("arxiv_id")
            if paper_id and paper_id not in seen_ids:
                seen_ids.add(paper_id)
                unique_papers.append(paper)
        
        logger.info(f"Generated {len(unique_papers)} unique suggestions")
        
        return {
            "session_id": session_id,
            "total_suggestions": len(unique_papers),
            "suggestions": unique_papers,
            "status": "success"
        }
    
    @agent_call("SearchAgent")
    def search_by_author(self, author_name: str, max_results: int = 10, trace_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Search for papers by a specific author.
        
        Args:
            author_name: Author name to search for
            max_results: Maximum number of results
            trace_id: Optional trace ID for observability
            
        Returns:
            List of papers by the author
        """
        query = f"au:{author_name}"
        logger.info(f"Searching papers by author: {author_name}")
        
        try:
            results = self.fetcher.search(query, max_results=max_results)
            return results
        except Exception as e:
            logger.error(f"Author search failed for '{author_name}': {e}")
            raise
    
    @agent_call("SearchAgent")
    def search_similar_papers(self, paper_id: str, max_results: int = 5, trace_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Find papers similar to a given paper (based on categories and authors).
        
        Args:
            paper_id: ArXiv ID of the reference paper
            max_results: Maximum number of similar papers
            trace_id: Optional trace ID for observability
            
        Returns:
            List of similar papers
        """
        logger.info(f"Finding papers similar to {paper_id}")
        
        try:
            # Get metadata for reference paper
            metadata = self.fetcher.fetch_metadata(paper_id)
            if not metadata:
                logger.warning(f"Could not fetch metadata for {paper_id}")
                return []
            
            # Search using primary category
            category = metadata.get("primary_category", "cs.AI")
            similar_papers = self.fetcher.get_trending_papers(category, max_results=max_results * 2)
            
            # Filter out the reference paper itself
            similar_papers = [p for p in similar_papers if p.get("arxiv_id") != paper_id][:max_results]
            
            logger.info(f"Found {len(similar_papers)} similar papers")
            return similar_papers
            
        except Exception as e:
            logger.error(f"Failed to find similar papers: {e}")
            return []
    
    def _extract_categories_from_session(self, session_context: Dict[str, Any]) -> List[str]:
        """
        Extract ArXiv categories from papers in the session.
        
        Args:
            session_context: Session data
            
        Returns:
            List of category strings
        """
        categories = set()
        
        # Try to extract from analyses
        analyses = session_context.get("analysis_results", {})
        for paper_id, analysis in analyses.items():
            # If we stored categories in analysis metadata
            if isinstance(analysis, dict):
                paper_cats = analysis.get("categories", [])
                if paper_cats:
                    categories.update(paper_cats)
        
        # Default categories if none found
        if not categories:
            categories = {"cs.AI", "cs.LG", "cs.CL"}
        
        return list(categories)