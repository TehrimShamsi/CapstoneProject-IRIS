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
  const sid = sessionId || "demo";
  return getEvaluation(sid);
}

// ===== NEW: Search & Discovery Functions =====

// Search ArXiv papers
export async function searchArxiv(query, maxResults = 10) {
  const res = await api.get("/search_arxiv", {
    params: { query, max_results: maxResults }
  });
  return res.data;
}

// Get trending papers
export async function getTrendingPapers(category = "cs.AI", maxResults = 10) {
  const res = await api.get("/trending_papers", {
    params: { category, max_results: maxResults }
  });
  return res.data;
}

// Get suggested papers
export async function getSuggestedPapers(sessionId = null, maxSuggestions = 8) {
  const res = await api.post("/suggest_papers", null, {
    params: { 
      session_id: sessionId,
      max_suggestions: maxSuggestions 
    }
  });
  return res.data;
}

// Search by author
export async function searchByAuthor(authorName, maxResults = 10) {
  const res = await api.get("/search_by_author", {
    params: { author: authorName, max_results: maxResults }
  });
  return res.data;
}

// Find similar papers
export async function findSimilarPapers(paperId, maxResults = 5) {
  const res = await api.get(`/similar_papers/${paperId}`, {
    params: { max_results: maxResults }
  });
  return res.data;
}

// Download paper from ArXiv
export async function downloadArxivPaper(arxivId) {
  const res = await api.post("/download_arxiv_paper", null, {
    params: { arxiv_id: arxivId }
  });
  return res.data;
}