"""
Test script for ArXiv fetcher
Run this to verify the ArXiv API is working correctly

Usage:
    python test_arxiv.py
"""

import sys
from pathlib import Path

# Add backend to path
backend_root = Path(__file__).parent
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

print("Testing ArXiv Fetcher...")
print("=" * 60)

try:
    from app.tools.arxiv_fetcher import ArxivFetcher
    print("✓ Successfully imported ArxivFetcher")
except Exception as e:
    print(f"✗ Failed to import ArxivFetcher: {e}")
    sys.exit(1)

# Create fetcher instance
fetcher = ArxivFetcher()
print("✓ Created ArxivFetcher instance")

# Test 1: Search
print("\n" + "=" * 60)
print("Test 1: Searching for 'attention mechanism'")
print("=" * 60)
try:
    results = fetcher.search("attention mechanism", max_results=3)
    print(f"✓ Search successful! Found {len(results)} papers")
    
    if results:
        print("\nFirst result:")
        first = results[0]
        print(f"  ID: {first['arxiv_id']}")
        print(f"  Title: {first['title'][:80]}...")
        print(f"  Authors: {', '.join(first['authors'][:3])}")
        print(f"  Categories: {', '.join(first['categories'][:3])}")
except Exception as e:
    print(f"✗ Search failed: {e}")
    import traceback
    traceback.print_exc()

# Test 2: Trending papers
print("\n" + "=" * 60)
print("Test 2: Getting trending papers from cs.AI")
print("=" * 60)
try:
    trending = fetcher.get_trending_papers("cs.AI", max_results=3)
    print(f"✓ Trending papers retrieved! Found {len(trending)} papers")
    
    if trending:
        print("\nFirst trending paper:")
        first = trending[0]
        print(f"  ID: {first['arxiv_id']}")
        print(f"  Title: {first['title'][:80]}...")
        print(f"  Published: {first['published']}")
except Exception as e:
    print(f"✗ Trending papers failed: {e}")
    import traceback
    traceback.print_exc()

# Test 3: Fetch metadata
print("\n" + "=" * 60)
print("Test 3: Fetching metadata for a specific paper")
print("=" * 60)
try:
    # Use a well-known paper ID
    paper_id = "1706.03762"  # "Attention is All You Need"
    metadata = fetcher.fetch_metadata(paper_id)
    
    if metadata:
        print(f"✓ Metadata retrieved successfully!")
        print(f"  Title: {metadata['title']}")
        print(f"  Authors: {', '.join(metadata['authors'][:3])}")
    else:
        print(f"✗ No metadata found for {paper_id}")
except Exception as e:
    print(f"✗ Metadata fetch failed: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
print("All tests completed!")
print("=" * 60)