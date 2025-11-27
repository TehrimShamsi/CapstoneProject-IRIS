// frontend/src/App.jsx
import { BrowserRouter as Router, Routes, Route } from "react-router-dom";

import UploadPaper from "./components/UploadPaper";
import AnalysisView from "./components/AnalysisView";
import SynthesisView from "./components/SynthesisView";
import MetricsDashboard from "./components/MetricsDashboard";
import EvaluationReport from "./components/EvaluationReport";
import PaperSearch from "./components/PaperSearch";

export default function App() {
  return (
    <Router>
      <div className="min-h-screen bg-gray-50">
        <Routes>

          {/* Upload Page */}
          <Route path="/" element={<UploadPaper />} />

          {/* NEW: Paper Search & Discovery */}
          <Route path="/search" element={<PaperSearch />} />

          {/* Analysis */}
          <Route path="/analyze/:paperId" element={<AnalysisView />} />

          {/* Synthesis */}
          <Route path="/synthesize" element={<SynthesisView />} />

          {/* Metrics */}
          <Route path="/metrics" element={<MetricsDashboard />} />

          {/* Evaluation */}
          <Route path="/evaluation/:sessionId" element={<EvaluationReport />} />

        </Routes>
      </div>
    </Router>
  );
}