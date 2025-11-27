import { useEffect, useState } from "react";
import { useParams, useSearchParams, useNavigate } from "react-router-dom";
import { analyzePaper, getSession } from "../services/api";

export default function AnalysisView() {
  const { paperId } = useParams();
  const [searchParams] = useSearchParams();
  const sessionId = searchParams.get("session");
  const navigate = useNavigate();

  const [loading, setLoading] = useState(true);
  const [analysis, setAnalysis] = useState(null);
  const [error, setError] = useState(null);
  const [progress, setProgress] = useState(0);

  // ─────────────────────────────────────────────
  // Polling until backend finishes analysis
  // ─────────────────────────────────────────────
  useEffect(() => {
    if (!sessionId) {
      setError("Missing session ID. Please upload a paper again.");
      setLoading(false);
      return;
    }

    async function fetchAnalysis() {
      try {
        console.log("Starting analysis for paperId:", paperId, "sessionId:", sessionId);
        
        // Step 1: Trigger backend analysis
        const res = await analyzePaper(sessionId, paperId);
        console.log("Analysis request sent, response:", res);

        // Step 2: Poll session until analysis is ready
        let pollCount = 0;
        const maxPolls = 30; // Max 45 seconds of polling
        
        const interval = setInterval(async () => {
          pollCount++;
          setProgress(Math.min((pollCount / maxPolls) * 100, 95));
          
          try {
            const sessionData = await getSession(sessionId);
            console.log("Poll attempt", pollCount, "session data:", sessionData);

            // Check if analysis is complete
            // papers is now a dict, not a list
            const paperData = sessionData.papers?.[paperId];
            if (paperData && paperData.analysis) {
              const analysisData = paperData.analysis;
              console.log("Analysis found:", analysisData);
              
              // Check if it has claims (indicates completion)
              if (analysisData.claims && analysisData.claims.length > 0) {
                clearInterval(interval);
                setAnalysis(analysisData);
                setProgress(100);
                setLoading(false);
                console.log("Analysis complete with", analysisData.claims.length, "claims");
              } else {
                console.log("Analysis exists but no claims yet");
              }
            } else {
              console.log("Analysis not found yet in session");
            }
          } catch (pollErr) {
            console.error("Polling error:", pollErr);
          }
        }, 1500);

        // Optional timeout stop (safety)
        setTimeout(() => {
          clearInterval(interval);
          if (loading) {
            setError("Analysis taking too long. Please try again.");
            setLoading(false);
          }
        }, 45000);

      } catch (err) {
        console.error("Analysis error:", err);
        setError(err.response?.data?.detail || "Failed to analyze paper.");
        setLoading(false);
      }
    }

    fetchAnalysis();
  }, [sessionId, paperId]);

  // ─────────────────────────────────────────────
  // Loading UI
  // ─────────────────────────────────────────────
  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center mt-20">
        <div className="h-10 w-10 border-4 border-blue-600 border-b-transparent rounded-full animate-spin"></div>
        <p className="mt-4 text-blue-700 font-medium">
          Analyzing paper… this may take a few seconds
        </p>
        <div className="mt-4 w-64 bg-gray-200 h-2 rounded-full overflow-hidden">
          <div
            className="h-full bg-blue-600 transition-all duration-300"
            style={{ width: `${progress}%` }}
          ></div>
        </div>
        <p className="mt-2 text-sm text-gray-500">{Math.floor(progress)}%</p>
      </div>
    );
  }

  // ─────────────────────────────────────────────
  // Error UI
  // ─────────────────────────────────────────────
  if (error) {
    return (
      <div className="max-w-xl mx-auto mt-20 p-6 bg-red-50 border border-red-200 rounded-xl text-center">
        <h2 className="text-xl font-bold text-red-700">Analysis Failed</h2>
        <p className="text-red-600 mt-3">{error}</p>
        <button
          onClick={() => navigate("/")}
          className="mt-4 px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700"
        >
          Try Another Paper
        </button>
      </div>
    );
  }

  // ─────────────────────────────────────────────
  // Parse backend results
  // ─────────────────────────────────────────────
  const { num_claims, claims = [] } = analysis || {};

  // Collect all methods + metrics across claims
  const allMethods = [...new Set(claims.flatMap((c) => c.methods || []))];
  const allMetrics = [...new Set(claims.flatMap((c) => c.metrics || []))];

  // ─────────────────────────────────────────────
  // Main UI
  // ─────────────────────────────────────────────
  return (
    <div className="max-w-4xl mx-auto p-6">
      <h1 className="text-3xl font-bold text-gray-800 mb-6">
        Paper Analysis Results
      </h1>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-8">
        <div className="bg-white p-4 rounded-lg shadow text-center">
          <h3 className="text-lg font-semibold text-gray-700">Claims</h3>
          <p className="text-3xl font-bold text-blue-600">{num_claims || 0}</p>
        </div>

        <div className="bg-white p-4 rounded-lg shadow text-center">
          <h3 className="text-lg font-semibold text-gray-700">Methods</h3>
          <p className="text-3xl font-bold text-green-600">{allMethods.length}</p>
        </div>

        <div className="bg-white p-4 rounded-lg shadow text-center">
          <h3 className="text-lg font-semibold text-gray-700">Metrics</h3>
          <p className="text-3xl font-bold text-purple-600">{allMetrics.length}</p>
        </div>
      </div>

      {/* Methods */}
      {allMethods.length > 0 && (
        <div className="mb-8">
          <h2 className="text-xl font-bold text-gray-700 mb-4">Detected Methods</h2>
          <div className="flex flex-wrap gap-2">
            {allMethods.map((m, i) => (
              <span
                key={i}
                className="px-3 py-1 bg-blue-100 text-blue-700 rounded-full text-sm font-medium"
              >
                {m}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Metrics */}
      {allMetrics.length > 0 && (
        <div className="mb-8">
          <h2 className="text-xl font-bold text-gray-700 mb-4">Extracted Metrics</h2>
          <div className="flex flex-wrap gap-2">
            {allMetrics.map((m, i) => (
              <span
                key={i}
                className="px-3 py-1 bg-purple-100 text-purple-700 rounded-full text-sm font-medium"
              >
                {m}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* CLAIMS */}
      <div>
        <h2 className="text-xl font-bold text-gray-700 mb-4">
          Extracted Claims ({claims.length})
        </h2>

        {claims.length === 0 ? (
          <div className="p-4 bg-yellow-50 border border-yellow-200 rounded-lg text-yellow-800">
            No claims extracted. The paper might be empty or unreadable.
          </div>
        ) : (
          <div className="space-y-4">
            {claims.map((c, i) => (
              <div
                key={i}
                className="p-4 bg-white border border-gray-200 rounded-xl shadow-sm hover:shadow-md transition"
              >
                <div className="flex items-start justify-between">
                  <p className="font-medium text-gray-800 flex-1">{c.text}</p>
                  <span className="ml-4 flex-shrink-0 px-2 py-1 bg-gray-100 text-gray-600 rounded text-xs font-semibold">
                    Claim {i + 1}
                  </span>
                </div>

                {/* Confidence */}
                {c.confidence != null && (
                  <div className="mt-3 flex items-center gap-2">
                    <span className="text-sm text-gray-600">Confidence:</span>
                    <div className="w-32 bg-gray-200 h-2 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-green-500"
                        style={{ width: `${c.confidence * 100}%` }}
                      ></div>
                    </div>
                    <span className="text-sm font-semibold text-gray-700">
                      {(c.confidence * 100).toFixed(0)}%
                    </span>
                  </div>
                )}

                {/* Methods */}
                {c.methods?.length > 0 && (
                  <div className="mt-3">
                    <p className="text-xs font-semibold text-gray-600 mb-2">Methods:</p>
                    <div className="flex flex-wrap gap-1">
                      {c.methods.map((m, idx) => (
                        <span
                          key={idx}
                          className="px-2 py-1 bg-blue-50 text-blue-700 rounded text-xs"
                        >
                          {m}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {/* Metrics */}
                {c.metrics?.length > 0 && (
                  <div className="mt-3">
                    <p className="text-xs font-semibold text-gray-600 mb-2">Metrics:</p>
                    <div className="flex flex-wrap gap-1">
                      {c.metrics.map((m, idx) => (
                        <span
                          key={idx}
                          className="px-2 py-1 bg-purple-50 text-purple-700 rounded text-xs"
                        >
                          {m}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {/* Provenance */}
                {c.provenance?.length > 0 && (
                  <div className="mt-3">
                    <p className="text-xs font-semibold text-gray-600">
                      Source: {c.provenance.map(p => p.chunk_id || p).join(", ")}
                    </p>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

<div className="mt-10 flex flex-col sm:flex-row justify-center gap-4">
  <button
    onClick={() => navigate("/")}
    className="px-6 py-3 rounded-lg bg-gray-200 text-gray-700 hover:bg-gray-300 transition"
  >
    Upload Another Paper
  </button>

  <button
    onClick={() => navigate(`/find-papers?session=${sessionId}`)}
    className="px-6 py-3 rounded-lg bg-blue-600 text-white hover:bg-blue-700 transition shadow"
  >
    🔍 Find Related Papers
  </button>

  <button
    onClick={() => navigate(`/synthesize?session=${sessionId}`)}
    className="px-6 py-3 rounded-lg bg-indigo-600 text-white hover:bg-indigo-700 transition shadow"
  >
    Continue to Synthesis →
  </button>
</div>
    </div>
  );
}