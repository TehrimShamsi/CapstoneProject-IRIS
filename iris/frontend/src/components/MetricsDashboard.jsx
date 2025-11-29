// frontend/src/components/MetricsDashboard.jsx
import React, { useEffect, useState, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { getMetrics } from "../services/api";

export default function MetricsDashboard() {
  const navigate = useNavigate();
  const [metrics, setMetrics] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let mounted = true;
    async function load() {
      try {
        const res = await getMetrics();
        if (!mounted) return;
        setMetrics(res);
      } catch (err) {
        console.error("Failed to fetch metrics", err);
        setError("Failed to load metrics. Try again later.");
      } finally {
        if (mounted) setLoading(false);
      }
    }
    load();
    return () => (mounted = false);
  }, []);

  // Derived data with safe defaults
  const claimsOverTime = useMemo(
    () => (metrics?.claims_over_time ? metrics.claims_over_time : []),
    [metrics]
  );
  const confidenceValues = useMemo(
    () => (metrics?.confidence_distribution ? metrics.confidence_distribution : []),
    [metrics]
  );
  const methodFreq = useMemo(() => (metrics?.method_frequency ? metrics.method_frequency : {}), [metrics]);
  const agentPerf = useMemo(() => (metrics?.agent_performance ? metrics.agent_performance : {}), [metrics]);

  // Small helpers for SVG charts
  const svgSize = { w: 700, h: 220, pad: 40 };

  function renderLineChart(data = [], title = "Claims over time") {
    if (!data.length) return <EmptyBlock text="No time-series data available" />;
    const { w, h, pad } = svgSize;
    const xs = data.map((d) => d.time);
    const ys = data.map((d) => d.count);
    const minY = 0;
    const maxY = Math.max(...ys) || 1;
    const xStep = (w - pad * 2) / Math.max(xs.length - 1, 1);

    const points = data
      .map((d, i) => {
        const x = pad + i * xStep;
        const y = pad + (h - pad * 2) * (1 - (d.count - minY) / (maxY - minY || 1));
        return `${x},${y}`;
      })
      .join(" ");

    return (
      <div className="bg-white p-4 rounded-xl shadow">
        <h3 className="font-semibold mb-3">{title}</h3>
        <svg viewBox={`0 0 ${w} ${h}`} className="w-full">
          {/* grid lines */}
          {[0, 0.25, 0.5, 0.75, 1].map((t, i) => {
            const y = pad + (h - pad * 2) * t;
            return <line key={i} x1={pad} x2={w - pad} y1={y} y2={y} stroke="#eee" />;
          })}

          {/* polyline */}
          <polyline fill="none" stroke="#2563eb" strokeWidth="2.5" points={points} />

          {/* points */}
          {data.map((d, i) => {
            const x = pad + i * xStep;
            const y = pad + (h - pad * 2) * (1 - (d.count - minY) / (maxY - minY || 1));
            return <circle key={i} cx={x} cy={y} r={3.5} fill="#2563eb" />;
          })}

          {/* x labels - show 5 (or fewer) */}
          {data.map((d, i) => {
            const x = pad + i * xStep;
            if (i % Math.ceil(data.length / 5) !== 0 && i !== data.length - 1) return null;
            return (
              <text key={i} x={x} y={h - pad + 14} fontSize="11" textAnchor="middle" fill="#666">
                {d.label || d.time}
              </text>
            );
          })}

          {/* y axis min/max */}
          <text x={8} y={pad + 6} fontSize="11" fill="#666">
            {maxY}
          </text>
          <text x={8} y={h - pad} fontSize="11" fill="#666">
            {minY}
          </text>
        </svg>
      </div>
    );
  }

  function renderHistogram(values = [], title = "Confidence distribution") {
    if (!values.length) return <EmptyBlock text="No confidence data" />;

    // values assumed 0-1 floats
    const bins = 8;
    const counts = new Array(bins).fill(0);
    values.forEach((v) => {
      const idx = Math.min(bins - 1, Math.floor(v * bins));
      counts[idx]++;
    });
    const maxCount = Math.max(...counts) || 1;
    const w = 700;
    const h = 220;
    const pad = 40;
    const barW = (w - pad * 2) / bins - 8;

    return (
      <div className="bg-white p-4 rounded-xl shadow">
        <h3 className="font-semibold mb-3">{title}</h3>
        <svg viewBox={`0 0 ${w} ${h}`} className="w-full">
          {counts.map((c, i) => {
            const x = pad + i * (barW + 8);
            const barH = ((h - pad * 2) * c) / maxCount;
            const y = h - pad - barH;
            return (
              <g key={i}>
                <rect x={x} y={y} width={barW} height={barH} fill="#10b981" rx="4" />
                <text x={x + barW / 2} y={h - pad + 14} fontSize="11" fill="#666" textAnchor="middle">
                  {(i / bins).toFixed(2)}
                </text>
              </g>
            );
          })}
        </svg>
      </div>
    );
  }

  function renderMethodBarChart(freq = {}, title = "Top methods") {
    const entries = Object.entries(freq).sort((a, b) => b[1] - a[1]).slice(0, 12);
    if (!entries.length) return <EmptyBlock text="No method frequency data" />;

    const maxVal = Math.max(...entries.map((e) => e[1])) || 1;
    return (
      <div className="bg-white p-4 rounded-xl shadow overflow-hidden">
        <h3 className="font-semibold mb-3">{title}</h3>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {entries.map(([method, count]) => (
            <div key={method} className="flex items-center gap-4 w-full">
              <div className="min-w-0 text-sm text-gray-700">{method}</div>
              <div className="flex-1 h-6 bg-gray-100 rounded overflow-hidden">
                <div
                  className="h-6 bg-indigo-500"
                  style={{ width: `${(count / maxVal) * 100}%` }}
                />
              </div>
              <div className="w-12 text-right text-sm text-gray-700">{count}</div>
            </div>
          ))}
        </div>
      </div>
    );
  }

  function renderAgentPerf(perf = {}) {
    const entries = Object.entries(perf);
    if (!entries.length) return <EmptyBlock text="No agent performance metrics" />;

    return (
      <div className="bg-white p-4 rounded-xl shadow">
        <h3 className="font-semibold mb-3">Agent performance</h3>
        <div className="space-y-3">
          {entries.map(([agent, m]) => (
            <div key={agent} className="flex items-center justify-between">
              <div>
                <div className="font-medium">{agent}</div>
                <div className="text-sm text-gray-500">{m.description || ""}</div>
              </div>
              <div className="text-right">
                <div className="text-sm text-gray-500">Calls: {m.calls ?? 0}</div>
                <div className="text-sm text-gray-500">Errors: {m.errors ?? 0}</div>
                <div className="text-sm text-gray-500">Avg latency: {m.avg_latency ? `${m.avg_latency.toFixed(2)}s` : "—"}</div>
              </div>
            </div>
          ))}
        </div>
      </div>
    );
  }

  // Export metrics
  function exportMetrics() {
    if (!metrics) return;
    const blob = new Blob([JSON.stringify(metrics, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `metrics_export.json`;
    a.click();
    URL.revokeObjectURL(url);
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <div className="h-10 w-10 border-4 border-blue-600 border-b-transparent rounded-full animate-spin mx-auto" />
          <p className="mt-4 text-gray-600">Loading metrics...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="max-w-3xl mx-auto mt-20 p-6 bg-red-50 border border-red-200 rounded-xl text-center">
        <h2 className="text-xl font-bold text-red-700">Error</h2>
        <p className="mt-3 text-red-600">{error}</p>
      </div>
    );
  }

  return (
    <div className="w-full px-6 py-10">
      {/* Home Icon Button */}
      <button
        onClick={() => navigate("/")}
        className="mb-6 p-2 text-gray-600 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition"
        title="Go to Home"
      >
        🏠
      </button>

      <div className="flex items-start justify-between gap-4 mb-8">
        <div>
          <h1 className="text-3xl font-bold">Observability & Metrics</h1>
          <p className="text-gray-600 mt-1">Live dashboard of agent & analysis metrics</p>
        </div>

        <div className="flex gap-3 items-center">
          <button onClick={exportMetrics} className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700">
            Export JSON
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div>
          {renderLineChart(claimsOverTime, "Claims over time")}
        </div>

        <div>
          {renderHistogram(confidenceValues, "Confidence distribution")}
        </div>
      </div>

      <div className="mt-6">
        {renderMethodBarChart(methodFreq, "Top methods")}
      </div>

      <div className="mt-6">
        {renderAgentPerf(agentPerf)}
      </div>

      {/* Raw metrics removed to keep dashboard clean */}
    </div>
  );
}

// small helper component
function EmptyBlock({ text }) {
  return (
    <div className="bg-gray-50 p-4 rounded-lg text-center text-gray-500">
      {text}
    </div>
  );
}
