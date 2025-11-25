import React, { useEffect, useState } from "react";
import { getEvaluationReport } from "../services/api";
import { Chart, registerables } from "chart.js";
Chart.register(...registerables);

export default function EvaluationReport() {
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    loadReport();
  }, []);

  async function loadReport() {
    try {
      const data = await getEvaluationReport();
      setReport(data);
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

  if (error) return <p className="text-center text-red-500 mt-20">{error}</p>;

  const provenanceLabels = Object.keys(report?.provenance_coverage || {});
  const provenanceValues = Object.values(report?.provenance_coverage || {});

  // Render chart after DOM loads
  useEffect(() => {
    if (provenanceLabels.length) {
      renderBarChart(
        "provChart",
        provenanceLabels,
        provenanceValues,
        "Provenance Coverage"
      );
    }
  }, [report]);

  return (
    <div className="max-w-5xl mx-auto px-6 py-12">
      <div className="flex items-center justify-between mb-8">
        <h1 className="text-3xl font-bold">Evaluation Report</h1>

        <div className="flex gap-3">
          <button
            onClick={downloadJSON}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg"
          >
            Download JSON
          </button>
          <button
            onClick={downloadPDF}
            className="px-4 py-2 bg-indigo-600 text-white rounded-lg"
          >
            Download PDF
          </button>
        </div>
      </div>

      {/* Claim quality */}
      <div className="bg-white p-6 rounded-xl shadow mb-6">
        <h2 className="text-xl font-semibold mb-4">Claim Quality</h2>
        <p className="text-gray-700">
          Average Score: <b>{report.claim_quality?.average_score ?? "—"}</b>
        </p>
        <p className="text-gray-700">
          Total Claims Evaluated: <b>{report.claim_quality?.count ?? "—"}</b>
        </p>
      </div>

      {/* Hallucination */}
      <div className="bg-white p-6 rounded-xl shadow mb-6">
        <h2 className="text-xl font-semibold mb-4">Hallucination Probability</h2>
        <p className="text-gray-700 text-lg">
          Possible Hallucination Rate:{" "}
          <b>{(report.hallucination_rate * 100).toFixed(2)}%</b>
        </p>
      </div>

      {/* Provenance Chart */}
      <div className="bg-white p-6 rounded-xl shadow mb-6">
        <h2 className="text-xl font-semibold mb-4">Provenance Coverage</h2>
        <canvas id="provChart" className="w-full h-64"></canvas>
      </div>

      {/* Confidence */}
      <div className="bg-white p-6 rounded-xl shadow mb-6">
        <h2 className="text-xl font-semibold mb-4">Confidence Summary</h2>
        <p className="text-gray-700">
          Avg Confidence: <b>{report.avg_confidence?.toFixed(2)}</b>
        </p>
        <p className="text-gray-700">
          Min Confidence: <b>{report.min_confidence?.toFixed(2)}</b>
        </p>
        <p className="text-gray-700">
          Max Confidence: <b>{report.max_confidence?.toFixed(2)}</b>
        </p>
      </div>

      {/* Raw JSON */}
      <div className="bg-white p-6 rounded-xl shadow">
        <h2 className="text-xl font-semibold mb-4">Raw Output (Debug)</h2>
        <pre className="text-sm bg-gray-100 p-3 rounded overflow-auto max-h-72">
          {JSON.stringify(report, null, 2)}
        </pre>
      </div>
    </div>
  );
}
