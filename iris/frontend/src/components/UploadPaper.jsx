// frontend/src/components/UploadPaper.jsx
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { uploadPDF, createSession } from "../services/api";

export default function UploadPaper() {
  const navigate = useNavigate();

  const [file, setFile] = useState(null);
  const [isDragging, setIsDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [paperId, setPaperId] = useState(null);
  const [sessionId, setSessionId] = useState(null);
  const [error, setError] = useState(null);

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files?.[0]) {
      const droppedFile = e.dataTransfer.files[0];
      if (droppedFile.type === "application/pdf") {
        setFile(droppedFile);
        setError(null);
      } else {
        setError("Please upload a PDF file");
      }
    }
  };

  const handleFileSelect = (e) => {
    const selectedFile = e.target.files?.[0];
    if (selectedFile) {
      if (selectedFile.type === "application/pdf") {
        setFile(selectedFile);
        setError(null);
      } else {
        setError("Please select a PDF file");
      }
    }
  };

  const handleUpload = async () => {
    if (!file) return;

    setUploading(true);
    setError(null);

    try {
      const uploadRes = await uploadPDF(file);
      setPaperId(uploadRes.paper_id);

      const sessionRes = await createSession();
      setSessionId(sessionRes.session_id);

      setTimeout(() => {
        navigate(`/analyze/${uploadRes.paper_id}?session=${sessionRes.session_id}`);
      }, 1500);
    } catch (err) {
      console.error("Upload error:", err);
      if (err.message && err.message.toLowerCase().includes("network")) {
        setError("Network error: cannot reach backend. Is the backend running at http://localhost:8000 ?");
      } else if (err.response) {
        const status = err.response.status;
        const detail = err.response.data?.detail || err.response.data || err.message;
        setError(`Upload failed (${status}): ${detail}`);
      } else {
        setError(err.message || "Upload failed. Please try again.");
      }
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="max-w-2xl mx-auto p-6">
      <div className="text-center mb-8">
        <h1 className="text-4xl font-bold mb-3 text-gray-800">
          IRIS Research Assistant
        </h1>
        <p className="text-gray-600">
          Upload a PDF or discover papers from ArXiv
        </p>
      </div>

      {/* Quick action buttons */}
      <div className="flex gap-4 mb-8">
        <button
          onClick={() => navigate("/search")}
          className="flex-1 py-3 px-6 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition shadow-md font-semibold"
        >
          🔍 Search ArXiv Papers
        </button>
        
        <button
          onClick={() => navigate("/metrics")}
          className="flex-1 py-3 px-6 bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition shadow-md font-semibold"
        >
          📊 View Metrics
        </button>
      </div>

      <div className="mb-6 text-center">
        <h2 className="text-2xl font-bold text-gray-800">
          Upload Your Paper
        </h2>
      </div>

      <div
        className={`
          border-2 border-dashed rounded-xl p-12 text-center transition-all
          ${isDragging 
            ? "border-blue-500 bg-blue-50 scale-105" 
            : "border-gray-300 bg-white hover:border-gray-400"
          }
        `}
        onDragOver={(e) => {
          e.preventDefault();
          setIsDragging(true);
        }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={handleDrop}
      >
        {file ? (
          <div>
            <p className="text-lg font-medium text-gray-700">{file.name}</p>
            <p className="text-sm text-gray-500 mt-1">
              {(file.size / 1024 / 1024).toFixed(2)} MB
            </p>
          </div>
        ) : (
          <div>
            <svg 
              className="mx-auto h-12 w-12 text-gray-400" 
              stroke="currentColor" 
              fill="none" 
              viewBox="0 0 48 48"
            >
              <path 
                d="M28 8H12a4 4 0 00-4 4v20m32-12v8m0 0v8a4 4 0 01-4 4H12a4 4 0 01-4-4v-4m32-4l-3.172-3.172a4 4 0 00-5.656 0L28 28M8 32l9.172-9.172a4 4 0 015.656 0L28 28m0 0l4 4m4-24h8m-4-4v8m-12 4h.02" 
                strokeWidth={2} 
                strokeLinecap="round" 
                strokeLinejoin="round" 
              />
            </svg>
            <p className="mt-4 text-gray-600">
              Drag & drop your PDF here, or click to select
            </p>
          </div>
        )}

        <input
          type="file"
          accept="application/pdf"
          className="hidden"
          id="pdfInput"
          onChange={handleFileSelect}
        />
        
        {!file && (
          <label
            htmlFor="pdfInput"
            className="mt-6 inline-block cursor-pointer bg-blue-600 text-white px-6 py-2 rounded-lg hover:bg-blue-700 transition"
          >
            Select PDF File
          </label>
        )}
      </div>

      {uploading && (
        <div className="mt-6 text-center">
          <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
          <p className="mt-2 text-blue-600 font-medium">Uploading...</p>
        </div>
      )}

      {paperId && (
        <div className="mt-6 p-4 bg-green-50 border border-green-200 rounded-lg">
          <p className="text-green-800 text-center">✅ Upload successful!</p>
          <p className="text-sm text-green-600 text-center mt-1">
            Paper ID: <span className="font-mono font-bold">{paperId}</span>
          </p>
          <p className="text-sm text-gray-600 text-center mt-2">
            Redirecting to analysis...
          </p>
        </div>
      )}

      {error && (
        <div className="mt-6 p-4 bg-red-50 border border-red-200 rounded-lg">
          <p className="text-red-700 text-center">{error}</p>
          <div className="text-center mt-3">
            <button
              onClick={() => {
                setError(null);
              }}
              className="px-3 py-1 bg-gray-200 rounded mr-2"
            >
              Dismiss
            </button>
            <button
              onClick={() => handleUpload()}
              className="px-3 py-1 bg-blue-600 text-white rounded"
            >
              Retry Upload
            </button>
          </div>
        </div>
      )}

      <button
        onClick={handleUpload}
        disabled={!file || uploading}
        className={`
          w-full mt-6 py-3 rounded-lg text-lg font-semibold transition
          ${!file || uploading
            ? "bg-gray-300 text-gray-500 cursor-not-allowed"
            : "bg-green-600 text-white hover:bg-green-700 shadow-lg hover:shadow-xl"
          }
        `}
      >
        {uploading ? "Uploading..." : "Upload & Analyze"}
      </button>
    </div>
  );
}