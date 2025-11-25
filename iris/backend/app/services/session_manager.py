"""
Improved JSON-backed Session Manager + MemoryBank

Improvements added:
✔ Better error handling (FileNotFoundError instead of silent None)
✔ New query/search methods (get_sessions_by_user, get_sessions_by_date)
✔ Optional file-size tracking (stored in session JSON)
✔ Same atomic write guarantees
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
    return datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def date_only() -> str:
    """YYYY-MM-DD (for date-based queries)"""
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
        session_id = str(uuid.uuid4())
        session_obj = {
            "session_id": session_id,
            "user_id": user_id,
            "created_at": iso_now(),
            "date": date_only(),            # <-- NEW: easier filtering
            "updated_at": iso_now(),
            "metadata": metadata or {},
            "papers": [],
            "analyses": [],
            "notes": [],
            "file_sizes": {}               # <-- NEW: tracks analysis file sizes
        }

        self._atomic_write(self._session_path(session_id), session_obj)
        return session_id

    # ------------------ Add paper & analysis ------------------
    def add_paper_to_session(self, session_id: str, paper_id: str, analysis: Optional[Dict[str, Any]] = None) -> None:
        session = self.get_session(session_id)

        # Save analysis to MemoryBank
        if analysis is not None:
            mb = MemoryBank(self.base_dir)
            file_path = mb.store(paper_id, analysis)

            # Track file size (for capstone: nice engineering touch)
            session["file_sizes"][paper_id] = os.path.getsize(file_path)

        # Update session structure
        if paper_id not in session["papers"]:
            session["papers"].append(paper_id)

        session["analyses"].append({
            "paper_id": paper_id,
            "added_at": iso_now()
        })

        session["updated_at"] = iso_now()
        self._atomic_write(self._session_path(session_id), session)

    # ------------------ Notes ------------------
    def add_note_to_session(self, session_id: str, note: str) -> None:
        session = self.get_session(session_id)
        session["notes"].append({
            "text": note,
            "created_at": iso_now()
        })
        session["updated_at"] = iso_now()
        self._atomic_write(self._session_path(session_id), session)

    # ------------------ Retrieval ------------------
    def get_session(self, session_id: str) -> Dict[str, Any]:
        path = self._session_path(session_id)
        if not path.exists():
            raise FileNotFoundError(f"❌ Session not found: {session_id}")
        return json.loads(path.read_text(encoding="utf-8"))

    def list_sessions(self) -> List[str]:
        return [f.stem for f in self.sessions_dir.glob("*.json")]

    def delete_session(self, session_id: str) -> bool:
        p = self._session_path(session_id)
        if p.exists():
            p.unlink()
            return True
        return False

    # ---------------------------------------------------------
    # NEW: Search / Query Methods
    # ---------------------------------------------------------
    def get_sessions_by_user(self, user_id: str) -> List[str]:
        """Return all session_ids belonging to a given user."""
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
        """Return sessions created on a specific date YYYY-MM-DD."""
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
        return self.sessions_dir / f"{session_id}.json"

    def _atomic_write(self, path: Path, obj: Any) -> None:
        """Write JSON atomically to prevent corruption."""
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
# MemoryBank (unchanged except minor cleanup)
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
        return pid.replace("/", "_").replace(":", "_")

    def store(self, paper_id: str, analysis_obj: Dict[str, Any]) -> Path:
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
        fname = self._sanitize(paper_id) + ".json"
        path = self.memory_dir / fname
        if not path.exists():
            return None
        wrapper = json.loads(path.read_text(encoding="utf-8"))
        return wrapper.get("analysis")

    def list_papers(self) -> List[str]:
        return [p.stem.replace("_", ":") for p in self.memory_dir.glob("*.json")]
