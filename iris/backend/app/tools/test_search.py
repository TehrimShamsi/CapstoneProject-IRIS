# iris/backend/tools/test_search.py
"""
Test script for ArXiv search functionality.

Usage:
    python -m tools.test_search
    
Or from backend folder:
    .venv\Scripts\python tools\test_search.py
"""

import sys
import pathlib

# Add backend to path
ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.agents.search_agent import SearchAgent
from app.utils.observability import logger
import json

def test_basic_search():
    """Test basic search functionality."""
    print("\n" + "="*60)
    print("TEST 1: Basic Search")
    print("="*60)
    
    agent = SearchAgent()
    
    # Test with a simple query
    result = agent.search_papers("machine learning", max_results=3)
    
    print(f"\nQuery: 'machine learning'")
    print(f"Status: {result['status']}")
    print(f"Results found: {result['total_results']}")
    
    if result['status'] == 'success' and result['papers']:
        print(f"\nFirst result:")
        paper = result['papers'][0]
        print(f"  Title: {paper['title'][:80]}...")
        print(f"  ArXiv ID: {paper['arxiv_id']}")
        print(f"  Authors: {', '.join(paper['authors'][:2])}...")
        print(f"  Published: {paper['published']}")
    else:
        print(f"Error: {result.get('error', 'No papers found')}")

def test_trending_papers():
    """Test trending papers functionality."""
    print("\n" + "="*60)
    print("TEST 2: Trending Papers")
    print("="*60)
    
    agent = SearchAgent()
    
    result = agent.get_trending_papers(category="cs.AI", max_results=5)
    
    print(f"\nCategory: cs.AI")
    print(f"Status: {result['status']}")
    print(f"Results found: {result['total_results']}")
    
    if result['status'] == 'success' and result['papers']:
        print(f"\nRecent papers:")
        for i, paper in enumerate(result['papers'][:3], 1):
            print(f"\n  {i}. {paper['title'][:70]}...")
            print(f"     ID: {paper['arxiv_id']}")
            print(f"     Published: {paper['published']}")
    else:
        print(f"Error: {result.get('error', 'No papers found')}")

def test_suggestions():
    """Test paper suggestions."""
    print("\n" + "="*60)
    print("TEST 3: Paper Suggestions")
    print("="*60)
    
    agent = SearchAgent()
    
    result = agent.suggest_papers(session_id="test_session", max_suggestions=5)
    
    print(f"\nSession: test_session")
    print(f"Status: {result['status']}")
    print(f"Suggestions: {result['total_suggestions']}")
    
    if result['status'] == 'success' and result['suggestions']:
        print(f"\nSuggested papers:")
        for i, paper in enumerate(result['suggestions'][:3], 1):
            print(f"\n  {i}. {paper['title'][:70]}...")
            print(f"     ID: {paper['arxiv_id']}")
    else:
        print(f"Error: {result.get('error', 'No suggestions')}")

def test_rate_limiting():
    """Test rate limiting behavior."""
    print("\n" + "="*60)
    print("TEST 4: Rate Limiting")
    print("="*60)
    
    agent = SearchAgent()
    
    print("\nMaking 3 consecutive requests (should be rate-limited)...")
    
    import time
    start = time.time()
    
    for i in range(3):
        print(f"\nRequest {i+1}...")
        result = agent.search_papers(f"test query {i}", max_results=1)
        print(f"  Status: {result['status']}")
    
    elapsed = time.time() - start
    print(f"\nTotal time: {elapsed:.2f}s")
    print(f"Expected minimum: ~6s (3s between requests)")

def test_error_handling():
    """Test error handling with invalid queries."""
    print("\n" + "="*60)
    print("TEST 5: Error Handling")
    print("="*60)
    
    agent = SearchAgent()
    
    # Test with empty query
    print("\nTest 5a: Empty query")
    result = agent.search_papers("", max_results=5)
    print(f"Status: {result['status']}")
    if result['status'] == 'error':
        print(f"Error (expected): {result.get('error', 'Unknown')[:80]}...")
    
    # Test with very specific query
    print("\nTest 5b: Highly specific query")
    result = agent.search_papers("xyzabc123nonexistent", max_results=5)
    print(f"Status: {result['status']}")
    print(f"Results: {result['total_results']}")

if __name__ == "__main__":
    print("\n" + "="*60)
    print("ARXIV SEARCH FUNCTIONALITY TEST SUITE")
    print("="*60)
    
    try:
        test_basic_search()
        test_trending_papers()
        test_suggestions()
        test_rate_limiting()
        test_error_handling()
        
        print("\n" + "="*60)
        print("ALL TESTS COMPLETED")
        print("="*60)
        print("\n✅ If you see results above, the search functionality is working!")
        print("⚠️  If you see errors, check:")
        print("   1. Internet connection")
        print("   2. ArXiv API status (https://arxiv.org/)")
        print("   3. Rate limiting (wait 3-5 seconds between tests)")
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Tests interrupted by user")
    except Exception as e:
        print(f"\n\n❌ FATAL ERROR: {e}")
        import traceback
        traceback.print_exc()