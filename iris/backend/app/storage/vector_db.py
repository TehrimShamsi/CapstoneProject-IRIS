# backend/app/storage/vector_db.py
"""
Enhanced Vector Database with Sentence Transformers
Supports semantic search over research paper embeddings
"""

import numpy as np
try:
    import faiss
except Exception:
    faiss = None
from typing import List, Dict, Any, Optional
_HAS_SENTENCE_TRANSFORMERS = True
try:
    from sentence_transformers import SentenceTransformer
except Exception:
    SentenceTransformer = None
    _HAS_SENTENCE_TRANSFORMERS = False
import json
from pathlib import Path

from app.utils.observability import logger


class VectorDB:
    """
    Vector database for semantic search using FAISS + sentence-transformers
    
    Features:
    - Automatic embedding generation
    - Semantic similarity search
    - Metadata storage and retrieval
    - Persistence to disk
    """
    
    def __init__(self, model_name: str = "all-MiniLM-L6-v2", dim: int = 384, 
                 index_path: Optional[str] = None):
        """
        Initialize vector database
        
        Args:
            model_name: Sentence transformer model name
            dim: Embedding dimension (384 for MiniLM-L6, 768 for mpnet)
            index_path: Path to save/load index
        """
        self.dim = dim
        self.model_name = model_name
        self.index_path = Path(index_path) if index_path else Path("data/vector_db")
        self.index_path.mkdir(parents=True, exist_ok=True)
        
        # Initialize sentence transformer if available, otherwise run in degraded mode
        self.encoder = None
        if _HAS_SENTENCE_TRANSFORMERS and SentenceTransformer is not None:
            try:
                logger.info(f"Loading sentence transformer: {model_name}")
                self.encoder = SentenceTransformer(model_name)
            except Exception as e:
                logger.warning(f"Failed to load SentenceTransformer: {e}. Running without embeddings.")

        # Local embeddings buffer as a fallback if FAISS persistence fails
        self.embeddings: List[np.ndarray] = []

        # Initialize FAISS index (cosine similarity) if faiss available and encoder loaded
        if faiss is not None and self.encoder is not None:
            try:
                self.index = faiss.IndexFlatIP(dim)  # Inner product for normalized vectors
            except Exception:
                self.index = None
        else:
            self.index = None
        
        # Metadata storage
        self.id_map: List[Dict[str, Any]] = []
        self.doc_count = 0
        
        # Try to load existing index
        self._load_index()
    
    def add_document(self, text: str, metadata: Dict[str, Any]) -> int:
        """
        Add document to vector DB
        
        Args:
            text: Document text to embed
            metadata: Associated metadata (paper_id, chunk_id, etc.)
        
        Returns:
            Document ID (index in vector store)
        """
        # Generate embedding (if encoder available)
        embedding = None
        if self.encoder is not None:
            embedding = self.encoder.encode(text, convert_to_numpy=True, show_progress_bar=False)
            # Normalize for cosine similarity
            try:
                embedding = embedding / np.linalg.norm(embedding)
            except Exception:
                pass
            # Add to FAISS index if available
            if self.index is not None:
                try:
                    self.index.add(np.array([embedding]).astype('float32'))
                except Exception:
                    logger.warning("Failed to add embedding to FAISS index")

        # Keep a local copy of the embedding for fallback persistence
        if embedding is not None:
            try:
                self.embeddings.append(np.array(embedding, dtype='float32'))
            except Exception:
                pass
        
        # Store metadata
        doc_id = self.doc_count
        metadata['doc_id'] = doc_id
        metadata['text'] = text  # Store original text
        self.id_map.append(metadata)
        
        self.doc_count += 1
        
        logger.debug(f"Added document {doc_id}: {text[:50]}...")
        
        return doc_id
    
    def add_paper_chunks(self, paper_id: str, chunks: List[str], 
                         paper_metadata: Optional[Dict[str, Any]] = None) -> List[int]:
        """
        Add all chunks from a paper
        
        Args:
            paper_id: Unique paper identifier
            chunks: List of text chunks
            paper_metadata: Optional metadata for the paper
        
        Returns:
            List of document IDs
        """
        doc_ids = []
        paper_meta = paper_metadata or {}
        
        for i, chunk in enumerate(chunks):
            metadata = {
                "paper_id": paper_id,
                "chunk_id": i,
                **paper_meta
            }
            doc_id = self.add_document(chunk, metadata)
            doc_ids.append(doc_id)
        
        logger.info(f"Added {len(chunks)} chunks for paper {paper_id}")
        
        return doc_ids
    
    def search(self, query: str, top_k: int = 5, 
               filter_metadata: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Semantic search for similar documents
        
        Args:
            query: Search query text
            top_k: Number of results to return
            filter_metadata: Optional metadata filters (e.g., {"paper_id": "123"})
        
        Returns:
            List of results with scores and metadata
        """
        # Generate query embedding
        query_embedding = self.encoder.encode(query, convert_to_numpy=True, show_progress_bar=False)
        query_embedding = query_embedding / np.linalg.norm(query_embedding)
        
        # Search FAISS index (if available). Otherwise return empty results.
        if self.index is None:
            logger.warning("Vector search requested but vector index is not available; returning empty results")
            return []

        distances, indices = self.index.search(
            np.array([query_embedding]).astype('float32'), 
            min(top_k * 3, self.doc_count)  # Get more results for filtering
        )
        
        # Build results
        results = []
        for dist, idx in zip(distances[0], indices[0]):
            if idx < 0 or idx >= len(self.id_map):
                continue
            
            metadata = self.id_map[idx].copy()
            
            # Apply metadata filters
            if filter_metadata:
                match = all(metadata.get(k) == v for k, v in filter_metadata.items())
                if not match:
                    continue
            
            results.append({
                "score": float(dist),
                "metadata": metadata,
                "text": metadata.get("text", "")
            })
            
            if len(results) >= top_k:
                break
        
        logger.info(f"Search for '{query[:50]}...' returned {len(results)} results")
        
        return results
    
    def find_similar_papers(self, paper_id: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Find papers similar to a given paper
        
        Args:
            paper_id: Reference paper ID
            top_k: Number of similar papers to return
        
        Returns:
            List of similar papers with scores
        """
        # Get all chunks for this paper
        paper_chunks = [m for m in self.id_map if m.get("paper_id") == paper_id]
        
        if not paper_chunks:
            logger.warning(f"Paper {paper_id} not found in vector DB")
            return []
        
        # Use average embedding of all chunks
        paper_texts = [chunk.get("text", "") for chunk in paper_chunks]
        avg_text = " ".join(paper_texts[:5])  # Use first 5 chunks
        
        # Search excluding the source paper
        results = self.search(avg_text, top_k=top_k * 2)
        
        # Group by paper_id and exclude source paper
        paper_scores: Dict[str, List[float]] = {}
        for result in results:
            pid = result["metadata"].get("paper_id")
            if pid and pid != paper_id:
                if pid not in paper_scores:
                    paper_scores[pid] = []
                paper_scores[pid].append(result["score"])
        
        # Average scores per paper
        similar_papers = [
            {
                "paper_id": pid,
                "avg_score": float(np.mean(scores)),
                "num_chunks": len(scores)
            }
            for pid, scores in paper_scores.items()
        ]
        
        # Sort by score
        similar_papers.sort(key=lambda x: x["avg_score"], reverse=True)
        
        return similar_papers[:top_k]
    
    def get_document_count(self) -> int:
        """Get total number of documents in DB"""
        return self.doc_count
    
    def get_paper_chunks(self, paper_id: str) -> List[Dict[str, Any]]:
        """Get all chunks for a paper"""
        return [m for m in self.id_map if m.get("paper_id") == paper_id]
    
    def _save_index(self):
        """Save FAISS index and metadata to disk"""
        try:
            # Try to save FAISS index (preferred)
            index_file = self.index_path / "faiss.index"
            metadata_path = self.index_path / "metadata.json"

            if self.index is not None and faiss is not None:
                try:
                    faiss.write_index(self.index, str(index_file))
                except Exception as e:
                    logger.warning(f"faiss.write_index failed: {e}. Will try raw-embeddings fallback.")

            # Save metadata
            with open(metadata_path, 'w') as f:
                json.dump({
                    "id_map": self.id_map,
                    "doc_count": self.doc_count,
                    "model_name": self.model_name,
                    "dim": self.dim
                }, f, indent=2)

            # If FAISS index wasn't saved, save raw embeddings as fallback
            embeddings_path = self.index_path / "embeddings.npy"
            if (self.index is None or faiss is None) and len(self.embeddings) > 0:
                try:
                    np.save(embeddings_path, np.vstack(self.embeddings))
                    logger.info(f"Saved raw embeddings to {embeddings_path}")
                except Exception as e:
                    logger.warning(f"Failed to save raw embeddings fallback: {e}")

            logger.info(f"Saved vector DB metadata to {self.index_path}")
        except Exception as e:
            logger.error(f"Failed to save vector DB: {e}")
    
    def _load_index(self):
        """Load FAISS index and metadata from disk"""
        try:
            index_file = self.index_path / "faiss.index"
            metadata_file = self.index_path / "metadata.json"
            # Load metadata if present
            if metadata_file.exists():
                with open(metadata_file, 'r') as f:
                    data = json.load(f)
                    self.id_map = data.get("id_map", [])
                    self.doc_count = data.get("doc_count", 0)

            # Try to load faiss index if available
            if index_file.exists() and faiss is not None:
                try:
                    self.index = faiss.read_index(str(index_file))
                    logger.info(f"Loaded faiss index from {index_file} ({self.doc_count} docs)")
                    return
                except Exception as e:
                    logger.warning(f"Failed to load faiss index: {e}")

            # If FAISS index not available, try loading raw embeddings
            embeddings_path = self.index_path / "embeddings.npy"
            if embeddings_path.exists() and faiss is not None:
                try:
                    arr = np.load(embeddings_path)
                    if arr is not None and arr.shape[0] > 0:
                        self.index = faiss.IndexFlatIP(self.dim)
                        self.index.add(arr.astype('float32'))
                        self.embeddings = [arr[i] for i in range(arr.shape[0])]
                        logger.info(f"Reconstructed FAISS index from raw embeddings ({arr.shape[0]} vectors)")
                        return
                except Exception as e:
                    logger.warning(f"Failed to reconstruct FAISS index from embeddings: {e}")

            logger.info(f"No existing vector DB found at {self.index_path}")
        except Exception as e:
            logger.warning(f"Could not load existing vector DB: {e}")
    
    def save(self):
        """Public method to save index"""
        self._save_index()
    
    def clear(self):
        """Clear all data"""
        self.index = faiss.IndexFlatIP(self.dim)
        self.id_map = []
        self.doc_count = 0
        logger.info("Cleared vector DB")


# ============================================
# Singleton instance
# ============================================

_vector_db_instance: Optional[VectorDB] = None


def get_vector_db() -> VectorDB:
    """Get singleton vector DB instance"""
    global _vector_db_instance
    if _vector_db_instance is None:
        _vector_db_instance = VectorDB()
    return _vector_db_instance