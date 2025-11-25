import numpy as np
# local FAISS example
import faiss

class VectorDB:
    def __init__(self, dim=768):
        self.dim = dim
        self.index = faiss.IndexFlatIP(dim)  # cosine sim if vectors normalized
        self.id_map = []

    def add(self, vector: np.ndarray, metadata: dict):
        self.index.add(np.array([vector]).astype('float32'))
        self.id_map.append(metadata)

    def search(self, query_vec: np.ndarray, top_k=5):
        D, I = self.index.search(np.array([query_vec]).astype('float32'), top_k)
        results = []
        for dist, idx in zip(D[0], I[0]):
            meta = self.id_map[idx]
            results.append({"score": float(dist), "metadata": meta})
        return results
