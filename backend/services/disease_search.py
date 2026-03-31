"""
services/disease_search.py
Semantic search over disease_db.json using sentence-transformers + cosine similarity.
Replaces exact string matching in lookup_static.
No FAISS needed — DB is small enough for direct cosine search.
"""

import json
import os
import numpy as np
from pathlib import Path
from functools import lru_cache

_DB_PATH = Path(__file__).parent.parent / "data" / "disease_db.json"

# Load disease DB once
with open(_DB_PATH) as f:
    DISEASE_DB = json.load(f)

_model      = None
_embeddings = None  # shape: (num_diseases, embedding_dim)
_keys       = None  # list of DB keys in same order as _embeddings


def _get_model():
    """Load sentence-transformer model once and cache it."""
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        # Small, fast model — good for farming terms
        _model = SentenceTransformer("all-MiniLM-L6-v2")
        print("[DiseaseSearch] Model loaded: all-MiniLM-L6-v2")
    return _model


def _get_embeddings():
    """Build embeddings for all DB keys once and cache them."""
    global _embeddings, _keys
    if _embeddings is None:
        model  = _get_model()
        _keys  = list(DISEASE_DB.keys())

        # Embed each key — also include display_name and crop for richer matching
        texts = []
        for key in _keys:
            entry = DISEASE_DB[key]
            # Combine key + display_name + crop + first line of symptoms
            text = (
                f"{key} "
                f"{entry.get('display_name', '')} "
                f"{entry.get('crop', '')} "
                f"{entry.get('symptoms', '')[:100]}"
            )
            texts.append(text)

        _embeddings = model.encode(texts, normalize_embeddings=True)
        print(f"[DiseaseSearch] Indexed {len(_keys)} diseases")
    return _embeddings, _keys


def semantic_search(query: str, top_k: int = 1, threshold: float = 0.35) -> dict | None:
    """
    Find the best matching disease from disease_db.json using semantic similarity.

    Args:
        query     : farmer's input e.g. "potato dark brown spots" or "Tomato Late Blight"
        top_k     : number of results to return (default 1)
        threshold : minimum similarity score to accept (0.0-1.0, default 0.35)

    Returns:
        Best matching disease dict, or None if no match above threshold.
    """
    try:
        model            = _get_model()
        embeddings, keys = _get_embeddings()

        # Embed the query
        query_embedding = model.encode([query], normalize_embeddings=True)[0]

        # Cosine similarity — since embeddings are normalized, dot product = cosine
        similarities = np.dot(embeddings, query_embedding)

        # Get top match
        best_idx   = int(np.argmax(similarities))
        best_score = float(similarities[best_idx])
        best_key   = keys[best_idx]

        print(f"[DiseaseSearch] Query: '{query}' → '{best_key}' (score: {best_score:.3f})")

        if best_score >= threshold:
            return DISEASE_DB[best_key]
        else:
            print(f"[DiseaseSearch] Score {best_score:.3f} below threshold {threshold} — no match")
            return None

    except Exception as e:
        print(f"[DiseaseSearch] Error: {e}")
        return None


def get_top_matches(query: str, top_k: int = 3) -> list:
    """
    Return top-k matches with scores — useful for debugging.
    """
    try:
        model            = _get_model()
        embeddings, keys = _get_embeddings()

        query_embedding = model.encode([query], normalize_embeddings=True)[0]
        similarities    = np.dot(embeddings, query_embedding)
        top_indices     = np.argsort(similarities)[::-1][:top_k]

        return [
            {
                "key":   keys[i],
                "score": float(similarities[i]),
                "entry": DISEASE_DB[keys[i]],
            }
            for i in top_indices
        ]
    except Exception as e:
        print(f"[DiseaseSearch] Error: {e}")
        return []