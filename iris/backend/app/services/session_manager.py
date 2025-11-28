"""
Improved JSON-backed Session Manager + MemoryBank

Improvements:
✔ Better error handling
✔ Query/search methods (get_sessions_by_user, get_sessions_by_date)
✔ File-size tracking
✔ Atomic write guarantees
✔ Fixed papers structure (dict instead of list)
"""

from __future__ import annotations
import os
import json
import uuid
import datetime
import tempfile
from pathlib import Path
from typing import Optional, Dict, Any, List

DEFAULT_BASE = Path.cwd() / "backend" / "app" / "data"


# ---------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------
def iso_now() -> str:
    """Return ISO 8601 timestamp with Z suffix"""
    return datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def date_only() -> str:
    """Return YYYY-MM-DD format"""
    return datetime.datetime.utcnow().strftime("%Y-%m-%d")


# ---------------------------------------------------------
# Main SessionManager
# ---------------------------------------------------------
class SessionManager:
    """
    File-based session manager.
    Sessions stored at: base_dir/sessions/<session_id>.json
    """

    def __init__(self, base_dir: Optional[Path | str] = None):
        self.base_dir = Path(base_dir) if base_dir else DEFAULT_BASE
        self.sessions_dir = self.base_dir / "sessions"
        self.memory_dir = self.base_dir / "memory_bank"

        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        self.memory_dir.mkdir(parents=True, exist_ok=True)

    # ------------------ Session creation ------------------
    def create_session(self, user_id: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """Create a new session and return session_id"""
        session_id = str(uuid.uuid4())
        session_obj = {
            "session_id": session_id,
            "user_id": user_id,
            "created_at": iso_now(),
            "date": date_only(),
            "updated_at": iso_now(),
            "metadata": metadata or {},
            "papers": {},           # ← FIX: Changed from [] to {}
            "analyses": [],
            # Backwards compatibility: legacy key used elsewhere in code
            "analysis_results": {},
            "notes": [],
            "file_sizes": {},
            "synthesis_result": None
        }

        self._atomic_write(self._session_path(session_id), session_obj)
        return session_id

    # ------------------ Add paper & analysis ------------------
    def add_paper_to_session(self, session_id: str, paper_id: str, analysis: Optional[Dict[str, Any]] = None) -> None:
        """Add a paper with its analysis to a session"""
        session = self.get_session(session_id)

        # Save analysis to MemoryBank
        if analysis is not None:
            mb = MemoryBank(self.base_dir)
            file_path = mb.store(paper_id, analysis)
            session["file_sizes"][paper_id] = os.path.getsize(file_path)

        # Update session structure (papers is now a dict)
        if paper_id not in session["papers"]:
            session["papers"][paper_id] = {}

        session["papers"][paper_id]["analysis"] = analysis

        # Try to populate a human-friendly title for UI
        title = None
        # Prefer title inside the analysis if the agent extracted it
        if isinstance(analysis, dict):
            title = analysis.get("title")

        # Next, try to read a stored paper metadata file if present
        try:
            papers_dir = self.base_dir / "papers"
            paper_meta_file = papers_dir / f"{paper_id}.json"
            if paper_meta_file.exists():
                meta = json.loads(paper_meta_file.read_text(encoding="utf-8"))
                meta_info = meta.get("metadata") if isinstance(meta, dict) else None
                if meta_info:
                    title = title or meta_info.get("title") or meta_info.get("filename") or meta_info.get("arxiv_id")
                    # persist pdf_path and source if present so UI can use them
                    if meta_info.get("pdf_path"):
                        session["papers"][paper_id]["pdf_path"] = meta_info.get("pdf_path")
                    if meta_info.get("source"):
                        session["papers"][paper_id]["source"] = meta_info.get("source")
                title = title or meta.get("title")
        except Exception:
            title = title or None

        # Fallback: derive from pdf filename if available
        if not title:
            pdf_path = None
            try:
                pdf_path = session["papers"][paper_id].get("pdf_path") or (analysis.get("pdf_path") if isinstance(analysis, dict) else None)
            except Exception:
                pdf_path = None
            if pdf_path:
                try:
                    from pathlib import Path as _P
                    title = _P(pdf_path).stem
                except Exception:
                    title = None

        # Try to read PDF embedded metadata (Title) if available
        if not title:
            try:
                pdf_path = session["papers"][paper_id].get("pdf_path") or (analysis.get("pdf_path") if isinstance(analysis, dict) else None)
                if pdf_path and os.path.exists(pdf_path):
                    try:
                        import PyPDF2
                        reader = PyPDF2.PdfReader(pdf_path)
                        meta = None
                        # PyPDF2 exposes metadata in different attributes depending on version
                        if hasattr(reader, "metadata"):
                            meta = reader.metadata
                        elif hasattr(reader, "documentInfo"):
                            meta = reader.documentInfo

                        if meta:
                            # metadata may be Mapping-like or object with attributes
                            title_candidate = None
                            try:
                                title_candidate = getattr(meta, "title", None)
                            except Exception:
                                title_candidate = None

                            if not title_candidate:
                                try:
                                    title_candidate = meta.get("/Title") if isinstance(meta, dict) else None
                                except Exception:
                                    title_candidate = None

                            if title_candidate:
                                title = str(title_candidate).strip()
                    except Exception:
                        # ignore PDF metadata read errors
                        pass
            except Exception:
                pass

        session["papers"][paper_id]["title"] = title

        session["papers"][paper_id]["added_at"] = iso_now()

        # Mirror into legacy `analysis_results` for backward compatibility
        if "analysis_results" not in session:
            session["analysis_results"] = {}
        session["analysis_results"][paper_id] = analysis

        session["analyses"].append({
            "paper_id": paper_id,
            "added_at": iso_now()
        })

        session["updated_at"] = iso_now()
        self._atomic_write(self._session_path(session_id), session)

    def create_paper_entry(self, paper_id: str, metadata: Dict[str, Any]) -> None:
        """Create a paper entry without a session (for direct uploads)"""
        papers_dir = self.base_dir / "papers"
        papers_dir.mkdir(parents=True, exist_ok=True)

        paper_file = papers_dir / f"{paper_id}.json"
        paper_obj = {
            "paper_id": paper_id,
            "created_at": iso_now(),
            "metadata": metadata,
        }
        self._atomic_write(paper_file, paper_obj)

    # ------------------ Notes ------------------
    def add_note_to_session(self, session_id: str, note: str) -> None:
        """Add a note to a session"""
        session = self.get_session(session_id)
        session["notes"].append({
            "text": note,
            "created_at": iso_now()
        })
        session["updated_at"] = iso_now()
        self._atomic_write(self._session_path(session_id), session)

    # ------------------ Retrieval ------------------
    def get_session(self, session_id: str) -> Dict[str, Any]:
        """Get session data by ID (raises FileNotFoundError if not found)"""
        path = self._session_path(session_id)
        if not path.exists():
            raise FileNotFoundError(f"❌ Session not found: {session_id}")
        return json.loads(path.read_text(encoding="utf-8"))

    def list_sessions(self) -> List[str]:
        """List all session IDs"""
        return [f.stem for f in self.sessions_dir.glob("*.json")]

    def delete_session(self, session_id: str) -> bool:
        """Delete a session"""
        p = self._session_path(session_id)
        if p.exists():
            p.unlink()
            return True
        return False

    def load_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Alias for get_session() - returns None if missing (backwards compatible)"""
        try:
            return self.get_session(session_id)
        except FileNotFoundError:
            return None

    def save_session(self, session_id: str, session: Dict[str, Any]) -> None:
        """Save session data"""
        session["updated_at"] = iso_now()
        self._atomic_write(self._session_path(session_id), session)

    # ---------------------------------------------------------
    # Search / Query Methods
    # ---------------------------------------------------------
    def get_sessions_by_user(self, user_id: str) -> List[str]:
        """Return all session_ids belonging to a given user"""
        matches = []
        for sid in self.list_sessions():
            try:
                s = self.get_session(sid)
                if s.get("user_id") == user_id:
                    matches.append(sid)
            except FileNotFoundError:
                continue
        return matches

    def get_sessions_by_date(self, date_str: str) -> List[str]:
        """Return sessions created on a specific date YYYY-MM-DD"""
        matches = []
        for sid in self.list_sessions():
            try:
                s = self.get_session(sid)
                if s.get("date") == date_str:
                    matches.append(sid)
            except FileNotFoundError:
                continue
        return matches

    # ---------------------------------------------------------
    # Internal helpers
    # ---------------------------------------------------------
    def _session_path(self, session_id: str) -> Path:
        """Get file path for a session"""
        return self.sessions_dir / f"{session_id}.json"

    def _atomic_write(self, path: Path, obj: Any) -> None:
        """Write JSON atomically to prevent corruption"""
        tmp_fd, tmp_path = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
        try:
            with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
                json.dump(obj, f, indent=2, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, path)
        finally:
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass


# ---------------------------------------------------------
# MemoryBank: Long-term memory for analysis objects
# ---------------------------------------------------------
class MemoryBank:
    """
    JSON-file backed "long-term memory" for storing analysis objects.
    Files: memory_bank/<paper_id_sanitized>.json
    """

    def __init__(self, base_dir: Optional[Path | str] = None):
        self.base_dir = Path(base_dir) if base_dir else DEFAULT_BASE
        self.memory_dir = self.base_dir / "memory_bank"
        self.memory_dir.mkdir(parents=True, exist_ok=True)

    def _sanitize(self, pid: str) -> str:
        """Sanitize paper ID for file path"""
        return pid.replace("/", "_").replace(":", "_")

    def store(self, paper_id: str, analysis_obj: Dict[str, Any]) -> Path:
        """Store analysis object and return file path"""
        fname = self._sanitize(paper_id) + ".json"
        path = self.memory_dir / fname

        wrapper = {
            "paper_id": paper_id,
            "stored_at": iso_now(),
            "analysis": analysis_obj
        }

        # Atomic write
        tmp_fd, tmp_path = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
        try:
            with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
                json.dump(wrapper, f, indent=2, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, path)
        finally:
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass

        return path

    def retrieve(self, paper_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve analysis object by paper ID"""
        fname = self._sanitize(paper_id) + ".json"
        path = self.memory_dir / fname
        if not path.exists():
            return None
        wrapper = json.loads(path.read_text(encoding="utf-8"))
        return wrapper.get("analysis")

    def list_papers(self) -> List[str]:
        """List all stored paper IDs"""
        return [p.stem.replace("_", ":") for p in self.memory_dir.glob("*.json")]