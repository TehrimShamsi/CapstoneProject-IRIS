// frontend/src/components/PaperSearch.jsx
import { useState, useEffect } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { 
  searchArxiv, 
  getTrendingPapers, 
  getSuggestedPapers,
  downloadArxivPaper,
  createSession 
} from "../services/api";

export default function PaperSearch() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const sessionId = searchParams.get("session");

  const [query, setQuery] = useState("");
  const [searching, setSearching] = useState(false);
  const [results, setResults] = useState([]);
  const [suggestions, setSuggestions] = useState([]);
  const [trending, setTrending] = useState([]);
  const [activeTab, setActiveTab] = useState("search"); // search, trending, suggestions
  const [error, setError] = useState("");
  const [downloadingIds, setDownloadingIds] = useState(new Set());

  // Load suggestions and trending on mount
  useEffect(() => {
    loadSuggestions();
    loadTrending();
  }, [sessionId]);

  async function loadSuggestions() {
    try {
      const data = await getSuggestedPapers(sessionId, 8);
      setSuggestions(data.suggestions || []);
    } catch (err) {
      console.error("Failed to load suggestions:", err);
    }
  }

  async function loadTrending() {
    try {
      const data = await getTrendingPapers("cs.AI", 10);
      setTrending(data.papers || []);
    } catch (err) {
      console.error("Failed to load trending:", err);
    }
  }

  async function handleSearch(e) {
    e.preventDefault();
    if (!query.trim()) return;

    setSearching(true);
    setError("");
    setActiveTab("search");

    try {
      const data = await searchArxiv(query, 10);
      setResults(data.papers || []);
    } catch (err) {
      console.error("Search error:", err);
      setError("Search failed. Please try again.");
    } finally {
      setSearching(false);
    }
  }

  async function handleDownload(arxivId) {
    setDownloadingIds(prev => new Set(prev).add(arxivId));
    setError("");

    try {
      // Download paper
      const downloadRes = await downloadArxivPaper(arxivId);
      
      // Create or use existing session
      // Prefer session query param, else fall back to persisted session id
      let sid = sessionId || window.localStorage.getItem("iris_session_id");
      if (!sid) {
        const sessionRes = await createSession();
        sid = sessionRes.session_id;
      }

      // Persist session id so subsequent flows reuse the same session
      try {
        window.localStorage.setItem("iris_session_id", sid);
      } catch (err) {
        console.warn("Failed to persist session id to localStorage", err);
      }

      // Navigate to analysis
      navigate(`/analyze/${downloadRes.paper_id}?session=${sid}`);
      
    } catch (err) {
      console.error("Download error:", err);
      setError(`Failed to download paper ${arxivId}`);
    } finally {
      setDownloadingIds(prev => {
        const next = new Set(prev);
        next.delete(arxivId);
        return next;
      });
    }
  }

  function renderPaperCard(paper) {
    const isDownloading = downloadingIds.has(paper.arxiv_id);

    return (
      <div key={paper.arxiv_id} className="bg-white p-5 rounded-xl shadow-md hover:shadow-lg transition">
        <h3 className="font-bold text-lg text-gray-800 mb-2">{paper.title}</h3>
        
        <div className="flex flex-wrap gap-2 mb-3">
          {paper.authors?.slice(0, 3).map((author, i) => (
            <span key={i} className="text-sm text-gray-600">{author}</span>
          ))}
          {paper.authors?.length > 3 && (
            <span className="text-sm text-gray-500">+{paper.authors.length - 3} more</span>
          )}
        </div>

        <p className="text-sm text-gray-700 mb-3 line-clamp-3">{paper.summary}</p>

        <div className="flex flex-wrap gap-2 mb-4">
          {paper.categories?.slice(0, 3).map((cat, i) => (
            <span key={i} className="px-2 py-1 bg-blue-100 text-blue-700 rounded text-xs">
              {cat}
            </span>
          ))}
        </div>

        <div className="flex gap-3">
          <button
            onClick={() => handleDownload(paper.arxiv_id)}
            disabled={isDownloading}
            className={`flex-1 py-2 rounded-lg font-semibold transition ${
              isDownloading
                ? "bg-gray-300 text-gray-500 cursor-not-allowed"
                : "bg-green-600 text-white hover:bg-green-700"
            }`}
          >
            {isDownloading ? "Downloading..." : "📥 Download & Analyze"}
          </button>

          <a
            href={paper.pdf_url}
            target="_blank"
            rel="noopener noreferrer"
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
          >
            View PDF
          </a>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto p-6">
      {/* Home Icon Button */}
      <button
        onClick={() => navigate("/")}
        className="mb-6 p-2 text-gray-600 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition"
        title="Go to Home"
      >
        🏠
      </button>

      <div className="mb-8">
        <h1 className="text-3xl font-bold mb-2">Discover Research Papers</h1>
        <p className="text-gray-600">Search ArXiv or explore trending and suggested papers</p>
      </div>

      {/* Search bar */}
      <form onSubmit={handleSearch} className="mb-8">
        <div className="flex gap-3">
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search papers (e.g., 'transformer architectures', 'reinforcement learning')"
            className="flex-1 px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          />
          <button
            type="submit"
            disabled={searching || !query.trim()}
            className={`px-6 py-3 rounded-lg font-semibold ${
              searching || !query.trim()
                ? "bg-gray-300 text-gray-500"
                : "bg-blue-600 text-white hover:bg-blue-700"
            }`}
          >
            {searching ? "Searching..." : "🔍 Search"}
          </button>
        </div>
      </form>

      {error && (
        <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700">
          {error}
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-4 mb-6 border-b border-gray-200">
        <button
          onClick={() => setActiveTab("search")}
          className={`pb-3 px-4 font-semibold transition ${
            activeTab === "search"
              ? "text-blue-600 border-b-2 border-blue-600"
              : "text-gray-500 hover:text-gray-700"
          }`}
        >
          Search Results ({results.length})
        </button>

        <button
          onClick={() => setActiveTab("trending")}
          className={`pb-3 px-4 font-semibold transition ${
            activeTab === "trending"
              ? "text-blue-600 border-b-2 border-blue-600"
              : "text-gray-500 hover:text-gray-700"
          }`}
        >
          🔥 Trending ({trending.length})
        </button>

        <button
          onClick={() => setActiveTab("suggestions")}
          className={`pb-3 px-4 font-semibold transition ${
            activeTab === "suggestions"
              ? "text-blue-600 border-b-2 border-blue-600"
              : "text-gray-500 hover:text-gray-700"
          }`}
        >
          💡 Suggestions ({suggestions.length})
        </button>
      </div>

      {/* Content */}
      <div className="space-y-4">
        {activeTab === "search" && (
          <>
            {results.length === 0 ? (
              <div className="text-center py-12 bg-gray-50 rounded-xl">
                <p className="text-gray-500">
                  {query ? "No results found" : "Enter a search query to find papers"}
                </p>
              </div>
            ) : (
              results.map(renderPaperCard)
            )}
          </>
        )}

        {activeTab === "trending" && (
          <>
            {trending.length === 0 ? (
              <div className="text-center py-12 bg-gray-50 rounded-xl">
                <p className="text-gray-500">Loading trending papers...</p>
              </div>
            ) : (
              trending.map(renderPaperCard)
            )}
          </>
        )}

        {activeTab === "suggestions" && (
          <>
            {suggestions.length === 0 ? (
              <div className="text-center py-12 bg-gray-50 rounded-xl">
                <p className="text-gray-500">Loading suggestions...</p>
              </div>
            ) : (
              suggestions.map(renderPaperCard)
            )}
          </>
        )}
      </div>

      {/* Back button */}
      <div className="mt-8 text-center">
        <button
          onClick={() => navigate("/")}
          className="px-6 py-3 bg-gray-600 text-white rounded-lg hover:bg-gray-700"
        >
          ← Back to Upload
        </button>
      </div>
    </div>
  );
}