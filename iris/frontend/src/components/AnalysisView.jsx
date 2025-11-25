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
        // Step 1: Trigger backend analysis (background task)
        const res = await analyzePaper(sessionId, paperId);

        if (res.status === "accepted") {
          // Step 2: Poll session until analysis is ready
          const interval = setInterval(async () => {
            try {
              const sessionData = await getSession(sessionId);

              if (sessionData.papers?.[paperId]?.analysis) {
                // Found completed analysis
                clearInterval(interval);
                setAnalysis(sessionData.papers[paperId].analysis);
                setLoading(false);
              }
            } catch (pollErr) {
              console.error("Polling error:", pollErr);
            }
          }, 1500);

          // Optional timeout stop (safety)
          setTimeout(() => clearInterval(interval), 45000);
        } else {
          setError("Unexpected backend response.");
          setLoading(false);
        }

      } catch (err) {
        console.error(err);
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
        Paper Analysis
      </h1>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-8">
        <div className="bg-white p-4 rounded-lg shadow text-center">
          <h3 className="text-lg font-semibold text-gray-700">Claims</h3>
          <p className="text-3xl font-bold text-blue-600">{num_claims}</p>
        </div>

        <div className="bg-white p-4 rounded-lg shadow text-center">
          <h3 className="text-lg font-semibold text-gray-700">Methods</h3>
          <p className="text-xl font-medium text-gray-800">
            {allMethods.length}
          </p>
        </div>

        <div className="bg-white p-4 rounded-lg shadow text-center">
          <h3 className="text-lg font-semibold text-gray-700">Metrics</h3>
          <p className="text-xl font-medium text-gray-800">
            {allMetrics.length}
          </p>
        </div>
      </div>

      {/* Methods */}
      {allMethods.length > 0 && (
        <div className="mb-8">
          <h2 className="text-xl font-bold text-gray-700 mb-2">Detected Methods</h2>
          <div className="flex flex-wrap gap-2">
            {allMethods.map((m, i) => (
              <span
                key={i}
                className="px-3 py-1 bg-blue-100 text-blue-700 rounded-full text-sm"
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
          <h2 className="text-xl font-bold text-gray-700 mb-2">Extracted Metrics</h2>
          <div className="flex flex-wrap gap-2">
            {allMetrics.map((m, i) => (
              <span
                key={i}
                className="px-3 py-1 bg-green-100 text-green-700 rounded-full text-sm"
              >
                {m}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* CLAIMS */}
      <div>
        <h2 className="text-xl font-bold text-gray-700 mb-4">Claims</h2>

        <div className="space-y-4">
          {claims.map((c, i) => (
            <div
              key={i}
              className="p-4 bg-white border rounded-xl shadow-sm"
            >
              <p className="font-medium text-gray-800">{c.text}</p>

              {/* Confidence */}
              {c.confidence != null && (
                <p className="text-sm text-gray-500 mt-1">
                  Confidence: {(c.confidence * 100).toFixed(1)}%
                </p>
              )}

              {/* Methods */}
              {c.methods?.length > 0 && (
                <div className="mt-2 flex flex-wrap gap-2">
                  {c.methods.map((m, idx) => (
                    <span
                      key={idx}
                      className="px-2 py-1 bg-blue-50 text-blue-700 rounded text-xs"
                    >
                      {m}
                    </span>
                  ))}
                </div>
              )}

              {/* Metrics */}
              {c.metrics?.length > 0 && (
                <div className="mt-2 flex flex-wrap gap-2">
                  {c.metrics.map((m, idx) => (
                    <span
                      key={idx}
                      className="px-2 py-1 bg-green-50 text-green-700 rounded text-xs"
                    >
                      {m}
                    </span>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Navigation Buttons */}
      <div className="mt-10 flex justify-center gap-4">
        <button
          onClick={() => navigate("/")}
          className="px-6 py-3 rounded-lg bg-gray-200 text-gray-700 hover:bg-gray-300 transition"
        >
          Upload Another Paper
        </button>

        <button
          onClick={() =>
            navigate(`/synthesize?session=${sessionId}&paper=${paperId}`)
          }
          className="px-6 py-3 rounded-lg bg-indigo-600 text-white hover:bg-indigo-700 transition shadow"
        >
          Continue to Synthesis →
        </button>
      </div>
    </div>
  );
}
