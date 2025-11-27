// frontend/src/components/SynthesisView.jsx
import { useEffect, useState, useMemo } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import { getSession, synthesizePapers } from "../services/api";

export default function SynthesisView() {
  const [searchParams] = useSearchParams();
  const sessionId = searchParams.get("session");
  const navigate = useNavigate();

  const [session, setSession] = useState(null);
  const [selectedPapers, setSelectedPapers] = useState([]);
  const [synthesis, setSynthesis] = useState(null);

  const [loading, setLoading] = useState(false);
  const [sessionLoading, setSessionLoading] = useState(true);
  const [progress, setProgress] = useState(0);
  const [retryCount, setRetryCount] = useState(0);

  const [error, setError] = useState("");

  // -----------------------------
  // Load session on mount
  // -----------------------------
  useEffect(() => {
    if (!sessionId) {
      setError("Missing session ID");
      setSessionLoading(false);
      return;
    }

    async function loadSession() {
      try {
        console.log("Loading session:", sessionId);
        const s = await getSession(sessionId);
        console.log("Session loaded:", s);
        setSession(s);

        // Get papers that have been analyzed
        // papers is now a dict
        const analyzedPapers = Object.keys(s.papers || {}).filter(
          (pid) => s.papers[pid]?.analysis
        );
        console.log("Analyzed papers:", analyzedPapers);
        
        if (analyzedPapers.length > 0) {
          setSelectedPapers(analyzedPapers);
        }
      } catch (err) {
        console.error("Failed to load session:", err);
        setError("Failed to load session.");
      } finally {
        setSessionLoading(false);
      }
    }

    loadSession();
  }, [sessionId]);

  // -----------------------------
  // Keyboard Shortcuts (Ctrl + S)
  // -----------------------------
  useEffect(() => {
    const handleKeyPress = (e) => {
      if (e.ctrlKey && e.key === "s") {
        e.preventDefault();
        if (synthesis) {
          downloadJSON(synthesis, `synthesis_${sessionId}.json`);
        }
      }
    };

    window.addEventListener("keydown", handleKeyPress);
    return () => window.removeEventListener("keydown", handleKeyPress);
  }, [synthesis, sessionId]);

  // -----------------------------
  // Paper toggle
  // -----------------------------
  const togglePaper = (paperId) => {
    setSelectedPapers((prev) =>
      prev.includes(paperId)
        ? prev.filter((p) => p !== paperId)
        : [...prev, paperId]
    );
  };

  // -----------------------------
  // Run synthesis + Polling + Retry + Progress
  // -----------------------------
  const runSynthesis = async () => {
    if (selectedPapers.length < 2) {
      setError("Select at least 2 papers for synthesis.");
      return;
    }

    setError("");
    setLoading(true);
    setProgress(0);

    try {
      console.log("Starting synthesis for papers:", selectedPapers);
      await synthesizePapers(sessionId, selectedPapers);

      let attempts = 0;
      const maxAttempts = 30;
      
      const interval = setInterval(async () => {
        attempts++;
        setProgress(Math.min((attempts / maxAttempts) * 100, 95));

        try {
          const sessionData = await getSession(sessionId);
          console.log("Synthesis poll attempt", attempts, "synthesis_result:", sessionData.synthesis_result);

          if (sessionData.synthesis_result) {
            clearInterval(interval);
            setSynthesis(sessionData.synthesis_result);
            setProgress(100);
            setLoading(false);
            console.log("Synthesis complete");
          }
        } catch (pollErr) {
          console.error("Poll error:", pollErr);
        }
      }, 1500);

      // Global timeout
      setTimeout(() => {
        clearInterval(interval);
        if (loading) {
          setError("Synthesis taking longer than expected. Refresh or retry.");
          setLoading(false);
        }
      }, 45000);
    } catch (err) {
      console.error("Synthesis error:", err);
      if (retryCount < 3) {
        console.log("Retrying synthesis... attempt", retryCount + 1);
        setRetryCount((prev) => prev + 1);
        setTimeout(() => runSynthesis(), 2000);
      } else {
        setError("Failed after 3 retries. Try again later.");
        setLoading(false);
      }
    }
  };

  // -----------------------------
  // Method Comparison Matrix
  // -----------------------------
  const { comparisonMatrix, allMethods } = useMemo(() => {
    if (!session?.papers) return { comparisonMatrix: {}, allMethods: [] };

    const matrix = {};
    const methodSet = new Set();

    selectedPapers.forEach((pid) => {
      const paperData = session.papers[pid];
      if (!paperData?.analysis) return;
      
      matrix[pid] = {};

      paperData.analysis?.claims?.forEach((claim) => {
        claim.methods?.forEach((m) => {
          methodSet.add(m);
          matrix[pid][m] = true;
        });
      });
    });

    return {
      comparisonMatrix: matrix,
      allMethods: Array.from(methodSet)
    };
  }, [session, selectedPapers]);

  // ─────────────────────────────────────────────
  // Loading state
  // ─────────────────────────────────────────────
  if (sessionLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen text-center">
        <div>
          <div className="h-10 w-10 border-4 border-blue-600 border-b-transparent rounded-full animate-spin mx-auto"></div>
          <p className="mt-4 text-gray-600">Loading session...</p>
        </div>
      </div>
    );
  }

  if (error && !session) {
    return (
      <div className="max-w-xl mx-auto mt-20 p-6 bg-red-50 border border-red-200 rounded-xl text-center">
        <h2 className="text-xl font-bold text-red-700">Error</h2>
        <p className="mt-3 text-red-600">{error}</p>
        <button
          onClick={() => navigate("/")}
          className="mt-4 w-full bg-red-600 text-white py-2 rounded-lg hover:bg-red-700"
        >
          Back to Upload
        </button>
      </div>
    );
  }

  const analyzedPapers = Object.keys(session?.papers || {}).filter(
    (pid) => session.papers[pid]?.analysis
  );

  // ─────────────────────────────────────────────
  // UI Rendering
  // ─────────────────────────────────────────────
  return (
    <div className="max-w-6xl mx-auto py-10 px-6">

      <h1 className="text-3xl font-bold mb-2">Multi-Paper Synthesis</h1>
      <p className="text-gray-600 mb-8">
        Analyze consensus, contradictions, and cross-paper patterns
      </p>

      {/* ---------- Paper Selection ---------- */}
      <div className="bg-white p-6 rounded-xl shadow-md mb-8">
        <h2 className="text-xl font-semibold mb-4">
          Select Papers ({analyzedPapers.length} available)
        </h2>

        {analyzedPapers.length === 0 ? (
          <p className="text-gray-500">No analyzed papers found. Upload and analyze papers first.</p>
        ) : (
          <>
            <div className="space-y-3 mb-6">
              {analyzedPapers.map((pid) => {
                const claims = session.papers[pid]?.analysis?.claims || [];
                return (
                  <label
                    key={pid}
                    className="flex items-center gap-3 p-3 bg-gray-50 rounded-lg hover:bg-gray-100 cursor-pointer"
                  >
                    <input
                      type="checkbox"
                      className="w-5 h-5 text-blue-600"
                      checked={selectedPapers.includes(pid)}
                      onChange={() => togglePaper(pid)}
                    />
                    <div className="flex-1">
                      <span className="font-medium text-gray-800">{pid}</span>
                      <span className="text-sm text-gray-500 ml-2">({claims.length} claims)</span>
                    </div>
                  </label>
                );
              })}
            </div>

            {/* Synthesize button */}
            <button
              onClick={runSynthesis}
              disabled={selectedPapers.length < 2 || loading}
              className={`w-full py-3 rounded-lg font-semibold ${
                selectedPapers.length < 2 || loading
                  ? "bg-gray-300 text-gray-500 cursor-not-allowed"
                  : "bg-blue-600 text-white hover:bg-blue-700 shadow"
              }`}
            >
              {loading ? "Synthesizing..." : `Synthesize ${selectedPapers.length} Papers`}
            </button>

            {/* Progress bar */}
            {loading && (
              <div className="w-full bg-gray-200 h-2 rounded mt-4 overflow-hidden">
                <div
                  className="bg-blue-600 h-2 rounded transition-all"
                  style={{ width: `${progress}%` }}
                ></div>
              </div>
            )}
          </>
        )}
      </div>

      {/* ---------- No synthesis yet ---------- */}
      {!synthesis && !loading && (
        <div className="text-center py-12 bg-gray-50 rounded-xl">
          <p className="text-gray-500 text-lg">Select papers and click "Synthesize"</p>
        </div>
      )}

      {/* ---------- Synthesis Results ---------- */}
      {synthesis && (
        <>
          {/* Summary cards */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-10">
            <SummaryCard label="Papers Analyzed" value={synthesis.num_papers} color="blue" />
            <SummaryCard label="Consensus Found" value={synthesis.num_consensus} color="green" />
            <SummaryCard label="Contradictions" value={synthesis.num_contradictions} color="red" />
          </div>

          {/* Consensus */}
          <Section title="🤝 Consensus Statements">
            {(!synthesis.consensus || synthesis.consensus.length === 0) ? (
              <EmptyBox>No consensus found</EmptyBox>
            ) : synthesis.consensus.map((c, i) => (
              <ConsensusBox key={i} item={c} />
            ))}
          </Section>

          {/* Contradictions */}
          <Section title="⚔️ Contradictions">
            {(!synthesis.contradictions || synthesis.contradictions.length === 0) ? (
              <EmptyBox>No contradictions found</EmptyBox>
            ) : synthesis.contradictions.map((c, i) => (
              <ContradictionBox key={i} item={c} />
            ))}
          </Section>

          {/* Method matrix */}
          {allMethods.length > 0 && (
            <Section title="📊 Method Comparison">
              <MethodMatrix
                allMethods={allMethods}
                selectedPapers={selectedPapers}
                comparisonMatrix={comparisonMatrix}
              />
            </Section>
          )}

          {/* Buttons */}
          <div className="flex justify-between gap-4 mt-12">
            <button
              onClick={() => navigate(`/analyze/${selectedPapers[0]}?session=${sessionId}`)}
              className="px-6 py-3 bg-gray-600 text-white rounded-lg hover:bg-gray-700 font-medium"
            >
              ← Back to Analysis
            </button>

            <div className="flex gap-4">
              <button
                onClick={() => navigate(`/evaluation/${sessionId}`)}
                className="px-6 py-3 bg-purple-600 text-white rounded-lg hover:bg-purple-700 font-medium"
              >
                View Evaluation Report
              </button>

              <button
                onClick={() => downloadJSON(synthesis, `synthesis_${sessionId}.json`)}
                className="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 font-medium"
              >
                📥 Export JSON
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

/* -------------------- Reusable Components -------------------- */

function SummaryCard({ label, value, color }) {
  const colors = {
    blue: "text-blue-600",
    green: "text-green-600",
    red: "text-red-600"
  };

  return (
    <div className="bg-white p-6 rounded-xl shadow-md text-center">
      <p className="text-gray-500 text-sm">{label}</p>
      <p className={`text-4xl font-bold mt-2 ${colors[color]}`}>{value}</p>
    </div>
  );
}

function Section({ title, children }) {
  return (
    <div className="mb-10">
      <h2 className="text-2xl font-bold mb-4">{title}</h2>
      {children}
    </div>
  );
}

function EmptyBox({ children }) {
  return (
    <div className="bg-gray-50 p-6 rounded-xl text-center text-gray-500">
      {children}
    </div>
  );
}

function ConsensusBox({ item }) {
  return (
    <div className="bg-white p-6 rounded-xl shadow-md border-l-4 border-green-500 mb-4">
      <p className="font-semibold text-lg text-gray-800 mb-3">{item.text}</p>
      <div className="flex flex-wrap gap-2 mb-2">
        {item.papers?.map((pid, i) => (
          <span key={i} className="px-3 py-1 bg-green-100 text-green-700 rounded-full text-sm">
            {pid}
          </span>
        ))}
      </div>
      <p className="text-sm text-gray-600">
        Avg Confidence:{" "}
        <span className="font-semibold">{(item.average_confidence * 100).toFixed(1)}%</span>
      </p>
    </div>
  );
}

function ContradictionBox({ item }) {
  return (
    <div className="bg-white p-6 rounded-xl shadow-md border-l-4 border-red-500 mb-4">
      <p className="font-bold text-red-600 mb-4">Conflicting Findings:</p>

      <div className="space-y-3">
        <div className="bg-red-50 p-4 rounded-lg">
          <p className="text-sm text-red-700 font-semibold mb-1">{item.paper_a}</p>
          <p className="text-gray-800">{item.claim_a}</p>
        </div>

        <p className="text-center text-gray-400">vs</p>

        <div className="bg-red-50 p-4 rounded-lg">
          <p className="text-sm text-red-700 font-semibold mb-1">{item.paper_b}</p>
          <p className="text-gray-800">{item.claim_b}</p>
        </div>
      </div>
    </div>
  );
}

function MethodMatrix({ allMethods, selectedPapers, comparisonMatrix }) {
  return (
    <div className="bg-white rounded-xl shadow-md overflow-hidden">
      <table className="w-full">
        <thead className="bg-gray-100">
          <tr>
            <th className="p-4 text-left font-semibold">Method</th>
            {selectedPapers.map((pid) => (
              <th key={pid} className="p-4 text-center font-semibold">
                {pid.split(":")[1] || pid.substring(0, 8)}
              </th>
            ))}
          </tr>
        </thead>

        <tbody>
          {allMethods.map((method, idx) => (
            <tr key={method} className={idx % 2 === 0 ? "bg-white" : "bg-gray-50"}>
              <td className="p-4 font-medium">{method}</td>

              {selectedPapers.map((pid) => (
                <td key={pid} className="p-4 text-center">
                  {comparisonMatrix[pid]?.[method] ? (
                    <span className="text-green-600 text-xl">✓</span>
                  ) : (
                    <span className="text-gray-300">—</span>
                  )}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/* -------------------- Download Helper -------------------- */
function downloadJSON(data, filename) {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}