// frontend/src/services/api.js
import axios from "axios";

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

const api = axios.create({
  baseURL: API_BASE,
  headers: { "Content-Type": "application/json" },
});

// Upload PDF
export async function uploadPDF(file) {
  const formData = new FormData();
  formData.append("file", file);

  const res = await api.post("/upload", formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });

  return res.data;
}

// Create session
export async function createSession(userId = "demo_user") {
  const res = await api.post("/session", { user_id: userId });
  return res.data;
}

export async function getSession(sessionId) {
  const res = await api.get(`/session/${sessionId}`);
  return res.data;
}

// Analyze paper
export async function analyzePaper(sessionId, paperId) {
  const res = await api.post("/analyze", {
    session_id: sessionId,
    paper_id: paperId,
  });
  return res.data;
}

// Synthesize
export async function synthesizePapers(sessionId, paperIds) {
  const res = await api.post("/synthesize", {
    session_id: sessionId,
    paper_ids: paperIds,
  });
  return res.data;
}

// Metrics
export async function getMetrics() {
  const res = await api.get("/metrics");
  return res.data;
}

// Evaluation
export async function getEvaluation(sessionId) {
  const res = await api.get(`/evaluation/${sessionId}`);
  return res.data;
}

// Backwards-compatible alias used by components
export async function getEvaluationReport(sessionId = null) {
  // If no sessionId provided, callers should pass one; using 'demo' as fallback.
  const sid = sessionId || "demo";
  return getEvaluation(sid);
}
