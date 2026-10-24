"""Index vectoriel local : un seul fichier SQLite, recherche cosinus en numpy.

À l'échelle d'un programme scolaire (quelques milliers de passages), une
recherche exhaustive en numpy suffit et ne demande aucune extension SQLite.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence

import numpy as np

from . import config
from .chunking import Chunk

Embedder = Callable[[Sequence[str]], np.ndarray]


@dataclass
class Hit:
    id: int
    score: float
    chunk: Chunk


def load_embedder() -> Embedder:
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(config.EMBEDDING_MODEL, cache_folder=str(config.MODELS_DIR / "hf"))
    dim = getattr(model, "get_embedding_dimension", model.get_sentence_embedding_dimension)()
    if dim != config.EMBEDDING_DIM:
        raise RuntimeError("Le modèle d'embedding ne correspond pas à EMBEDDING_DIM.")
    return lambda texts: model.encode(list(texts), normalize_embeddings=True, convert_to_numpy=True)


class Index:
    def __init__(self, path: Path = config.INDEX_PATH,
                 model: str = config.EMBEDDING_MODEL, dim: int = config.EMBEDDING_DIM):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.model, self.dim = model, dim
        self.db.executescript(
            """
            CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
            CREATE TABLE IF NOT EXISTS chunks (
                id INTEGER PRIMARY KEY, source TEXT, chapitre TEXT, lecon TEXT,
                page INTEGER, text TEXT, vec BLOB);
            """
        )
        self._check_meta()
        self._cache: tuple[np.ndarray, list[int]] | None = None

    def _check_meta(self):
        stored = dict(self.db.execute("SELECT key, value FROM meta"))
        if not stored:
            self.db.executemany("INSERT INTO meta VALUES (?, ?)",
                                [("embedding_model", self.model), ("embedding_dim", str(self.dim))])
            self.db.commit()
        elif stored.get("embedding_model") != self.model or stored.get("embedding_dim") != str(self.dim):
            raise RuntimeError(
                f"Index construit avec {stored.get('embedding_model')} ({stored.get('embedding_dim')}) : "
                "réindexer avec `python -m kalan.ingest --reset`.")

    def reset_source(self, source: str):
        self.db.execute("DELETE FROM chunks WHERE source = ?", (source,))
        self.db.commit()
        self._cache = None

    def add(self, chunks: list[Chunk], vectors: np.ndarray):
        assert vectors.shape == (len(chunks), self.dim)
        self.db.executemany(
            "INSERT INTO chunks (source, chapitre, lecon, page, text, vec) VALUES (?, ?, ?, ?, ?, ?)",
            [(c.source, c.chapitre, c.lecon, c.page, c.text, v.astype(np.float32).tobytes())
             for c, v in zip(chunks, vectors)])
        self.db.commit()
        self._cache = None

    def count(self) -> int:
        return self.db.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]

    def _matrix(self):
        if self._cache is None:
            rows = self.db.execute("SELECT id, vec FROM chunks").fetchall()
            ids = [r[0] for r in rows]
            mat = (np.stack([np.frombuffer(r[1], dtype=np.float32) for r in rows])
                   if rows else np.zeros((0, self.dim), dtype=np.float32))
            self._cache = (mat, ids)
        return self._cache

    def get(self, chunk_id: int) -> Chunk:
        r = self.db.execute("SELECT source, chapitre, lecon, page, text FROM chunks WHERE id = ?",
                            (chunk_id,)).fetchone()
        return Chunk(*r)

    def search(self, query_vec: np.ndarray, k: int = config.TOP_K) -> list[Hit]:
        mat, ids = self._matrix()
        if not ids:
            return []
        scores = mat @ query_vec.astype(np.float32).ravel()
        best = np.argsort(-scores)[:k]
        return [Hit(ids[i], float(scores[i]), self.get(ids[i])) for i in best]
