# backend/app/agents/search_agent.py
from typing import List, Dict, Any, Optional
import arxiv
from app.tools.arxiv_fetcher import ArxivFetcher
from app.utils.observability import agent_call, logger

class SearchAgent:
    """
    Agent responsible for searching and discovering papers from ArXiv.
    Provides smart suggestions based on session context and trending papers.
    """
    
    def __init__(self):
        self.fetcher = ArxivFetcher()
        
    @agent_call("SearchAgent")
    def search_papers(self, query: str, max_results: int = 10, trace_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Search for papers on ArXiv based on a query.
        
        Args:
            query: Search query string
            max_results: Maximum number of results to return
            trace_id: Optional trace ID for observability
            
        Returns:
            List of paper metadata dictionaries
        """
        logger.info(f"Searching ArXiv for: {query}")
        
        try:
            results = self.fetcher.search(query, max_results=max_results)
            return results
        except Exception as e:
            logger.error(f"Search failed for query '{query}': {e}")
            raise
    
    @agent_call("SearchAgent")
    def get_trending_papers(self, category: str = "cs.AI", max_results: int = 10, trace_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get recently published trending papers from a category.
        
        Args:
            category: ArXiv category (cs.AI, cs.LG, cs.CL, etc.)
            max_results: Maximum number of results
            trace_id: Optional trace ID for observability
            
        Returns:
            List of paper metadata dictionaries
        """
        logger.info(f"Fetching trending papers from {category}")
        
        try:
            results = self.fetcher.get_trending_papers(category, max_results)
            return results
        except Exception as e:
            logger.error(f"Failed to fetch trending papers: {e}")
            return []  # Return empty list on error
    
    @agent_call("SearchAgent")
    def suggest_papers(self, session_context: Dict[str, Any], max_suggestions: int = 8, trace_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Generate smart paper suggestions based on session context.
        
        Args:
            session_context: Dictionary containing session info (papers, analyses, etc.)
            max_suggestions: Maximum number of suggestions
            trace_id: Optional trace ID for observability
            
        Returns:
            List of suggested papers
        """
        logger.info(f"Generating smart suggestions for session {session_context.get('session_id', 'unknown')}")
        
        suggestions = []
        
        # Strategy 1: If session has analyzed papers, find related work
        analyzed_papers = session_context.get("papers", [])
        if analyzed_papers:
            # Get categories from existing papers
            categories = self._extract_categories_from_session(session_context)
            if categories:
                # Search for papers in similar categories
                for category in categories[:2]:  # Limit to top 2 categories
                    try:
                        related = self.fetcher.get_trending_papers(category, max_results=4)
                        suggestions.extend(related)
                    except Exception as e:
                        logger.warning(f"Could not fetch papers for category {category}: {e}")
        
        # Strategy 2: If no papers yet, show popular recent papers
        if not suggestions:
            try:
                suggestions = self.fetcher.get_trending_papers("cs.AI", max_results=max_suggestions)
            except Exception as e:
                logger.error(f"Error fetching trending papers: {e}")
                suggestions = []
        
        # Deduplicate and limit
        seen_ids = set()
        unique_suggestions = []
        for paper in suggestions:
            paper_id = paper.get("arxiv_id")
            if paper_id and paper_id not in seen_ids:
                seen_ids.add(paper_id)
                unique_suggestions.append(paper)
                if len(unique_suggestions) >= max_suggestions:
                    break
        
        logger.info(f"Generated {len(unique_suggestions)} unique suggestions")
        return unique_suggestions
    
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