import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { getEvaluationReport } from "../services/api";
import { Chart, registerables } from "chart.js";
Chart.register(...registerables);

export default function EvaluationReport() {
  const navigate = useNavigate();
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    loadReport();
  }, []);

  async function loadReport() {
    try {
      const data = await getEvaluationReport();
      // The API returns { report: {...} }, so unwrap it
      const reportData = data.report || data;
      setReport(reportData);
    } catch (err) {
      console.error(err);
      setError("Failed to load evaluation report");
    } finally {
      setLoading(false);
    }
  }

  // Chart helpers ----------------
  function renderBarChart(canvasId, labels, values, label) {
    const ctx = document.getElementById(canvasId);
    if (!ctx) return;

    new Chart(ctx, {
      type: "bar",
      data: {
        labels,
        datasets: [
          {
            label,
            data: values,
            borderWidth: 1,
          },
        ],
      },
      options: {
        responsive: true,
        plugins: { legend: { display: false } },
        scales: { y: { beginAtZero: true } },
      },
    });
  }

  function downloadJSON() {
    const blob = new Blob([JSON.stringify(report, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "evaluation_report.json";
    a.click();
    URL.revokeObjectURL(url);
  }

  function downloadPDF() {
    const pdf = window.open("", "_blank");
    pdf.document.write(`<pre>${JSON.stringify(report, null, 2)}</pre>`);
    pdf.document.close();
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <div className="border-4 border-blue-600 border-b-transparent h-10 w-10 rounded-full animate-spin mx-auto" />
          <p className="mt-3 text-gray-600">Generating evaluation report...</p>
        </div>
      </div>
    );
  }

  if (error) return (
    <div className="max-w-2xl mx-auto mt-20 p-6 bg-red-50 border border-red-200 rounded-xl">
      <h2 className="text-xl font-bold text-red-700">Error</h2>
      <p className="text-red-600 mt-2">{error}</p>
    </div>
  );

  if (!report) {
    return (
      <div className="max-w-2xl mx-auto mt-20 p-6 bg-yellow-50 border border-yellow-200 rounded-xl">
        <h2 className="text-xl font-bold text-yellow-700">No Report Available</h2>
        <p className="text-yellow-600 mt-2">Analyze and synthesize papers first to generate an evaluation report.</p>
      </div>
    );
  }

  const summary = report?.summary || {};
  const analyses = report?.analyses || [];
  const synthesis = report?.synthesis || {};

  return (
    <div className="max-w-5xl mx-auto px-6 py-12">
      {/* Home Icon Button */}
      <button
        onClick={() => navigate("/")}
        className="mb-6 p-2 text-gray-600 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition"
        title="Go to Home"
      >
        🏠
      </button>

      <div className="flex items-center justify-between mb-8">
        <h1 className="text-3xl font-bold">Evaluation Report</h1>

        <div className="flex gap-3">
          <button
            onClick={downloadJSON}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
          >
            Download JSON
          </button>
        </div>
      </div>

      {/* Summary Section */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
        <div className="bg-white p-6 rounded-xl shadow">
          <h3 className="text-lg font-semibold text-gray-800 mb-4">Overview</h3>
          <p className="text-gray-700 mb-2">Papers Analyzed: <b>{summary.total_papers || 0}</b></p>
          <p className="text-gray-700 mb-2">Total Claims: <b>{summary.total_claims || 0}</b></p>
          <p className="text-gray-700 mb-2">Avg Provenance Coverage: <b>{(summary.avg_provenance_coverage * 100).toFixed(1)}%</b></p>
          <p className="text-gray-700">Avg Claim Confidence: <b>{(summary.avg_claim_confidence * 100).toFixed(1)}%</b></p>
        </div>

        <div className="bg-white p-6 rounded-xl shadow">
          <h3 className="text-lg font-semibold text-gray-800 mb-4">Hallucination Risk</h3>
          <p className="text-gray-700 mb-4">
            Hallucinated Claims: <b className="text-red-600">{summary.total_hallucinated_claims || 0}</b>
          </p>
          <p className="text-sm text-gray-500">
            Low-confidence claims without provenance are flagged as potential hallucinations.
          </p>
        </div>
      </div>

      {/* Synthesis Results */}
      <div className="bg-white p-6 rounded-xl shadow mb-8">
        <h2 className="text-2xl font-semibold mb-4">Synthesis Analysis</h2>
        <div className="grid grid-cols-2 gap-4">
          <div className="bg-green-50 p-4 rounded-lg">
            <p className="text-green-700 text-sm">Consensus Statements Found</p>
            <p className="text-3xl font-bold text-green-600">{synthesis.num_consensus || 0}</p>
          </div>
          <div className="bg-red-50 p-4 rounded-lg">
            <p className="text-red-700 text-sm">Contradictions Found</p>
            <p className="text-3xl font-bold text-red-600">{synthesis.num_contradictions || 0}</p>
          </div>
        </div>
      </div>

      {/* Per-Paper Analysis Details */}
      {analyses.length > 0 && (
        <div className="bg-white p-6 rounded-xl shadow mb-8">
          <h2 className="text-xl font-semibold mb-4">Per-Paper Analysis</h2>
          <div className="space-y-4">
            {analyses.map((analysis, i) => (
              <div key={i} className="border-l-4 border-blue-500 pl-4 py-2">
                <p className="text-sm text-gray-500">{analysis.paper_id}</p>
                <div className="flex gap-6 mt-2 text-sm">
                  <span>Claims: <b>{analysis.total_claims}</b></span>
                  <span>Provenance: <b>{(analysis.provenance_coverage * 100).toFixed(0)}%</b></span>
                  <span>Avg Confidence: <b>{(analysis.avg_claim_confidence * 100).toFixed(0)}%</b></span>
                  <span className="text-red-600">Hallucinated: <b>{analysis.hallucinated_claims}</b></span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
