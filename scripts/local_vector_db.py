"""LocalVectorDB — base vectorielle LOCALE (SQLite + numpy) pour Android.

Exigence produit : le calcul d'embedding est **distant** (API OpenAI/Ollama/Azure),
seul le **stockage** des vecteurs est local. Implémentation pure Python + numpy
(le seul module natif, déjà fourni par le dépôt de wheels Android) :

- stockage : SQLite (`DATA_DIR/vector_db/local_vectors.sqlite3`), vecteurs
  float32 sérialisés ;
- recherche : force brute par produit scalaire vectorisé numpy — exacte, et
  rapide pour les volumes personnels (10^3 à 10^5 fragments sur téléphone) ;
- score : similarité cosinus ramenée dans [0,1] (1 = meilleur), convention
  open_webui (identique au backend chroma).
"""
from __future__ import annotations

import json
import logging
import sqlite3
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import numpy as np

from open_webui.env import DATA_DIR
from open_webui.retrieval.vector.main import (
    GetResult,
    SearchResult,
    VectorDBBase,
    VectorItem,
)
from open_webui.retrieval.vector.utils import metadata_matches_filter

log = logging.getLogger(__name__)

DB_PATH = Path(str(DATA_DIR)) / 'vector_db' / 'local_vectors.sqlite3'


class LocalVectorDB(VectorDBBase):
    def __init__(self) -> None:
        self._lock = threading.Lock()
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS vectors (
                collection TEXT NOT NULL,
                id TEXT NOT NULL,
                text TEXT,
                vector BLOB NOT NULL,
                metadata TEXT,
                PRIMARY KEY (collection, id)
            )
            """
        )
        self._conn.execute(
            'CREATE INDEX IF NOT EXISTS idx_vectors_collection ON vectors (collection)'
        )
        self._conn.commit()

    # ---------- helpers ----------
    @staticmethod
    def _pack(vector: List[float | int]) -> bytes:
        return np.asarray(vector, dtype=np.float32).tobytes()

    @staticmethod
    def _unpack(blob: bytes) -> np.ndarray:
        return np.frombuffer(blob, dtype=np.float32)

    @staticmethod
    def _load_metadata(raw: Optional[str]) -> Dict[str, Any]:
        if not raw:
            return {}
        try:
            value = json.loads(raw)
            return value if isinstance(value, dict) else {}
        except Exception:
            return {}

    def _rows(self, collection_name: str, filter: Optional[Dict] = None):
        with self._lock:
            cur = self._conn.execute(
                'SELECT id, text, vector, metadata FROM vectors WHERE collection = ?',
                (collection_name,),
            )
            rows = cur.fetchall()
        if filter:
            rows = [r for r in rows if metadata_matches_filter(self._load_metadata(r[3]), filter)]
        return rows

    # ---------- API ----------
    def get_collections(self) -> List[str]:
        """P36 — liste des collections existantes (nécessaire au nettoyage des
        collections orphelines : la route /fm/fix-index appelait cette méthode
        qui n'existait sur aucun backend)."""
        with self._lock:
            cur = self._conn.execute('SELECT DISTINCT collection FROM vectors')
            return sorted(row[0] for row in cur.fetchall())

    def has_collection(self, collection_name: str) -> bool:
        with self._lock:
            cur = self._conn.execute(
                'SELECT 1 FROM vectors WHERE collection = ? LIMIT 1', (collection_name,)
            )
            return cur.fetchone() is not None

    def delete_collection(self, collection_name: str) -> None:
        with self._lock:
            self._conn.execute('DELETE FROM vectors WHERE collection = ?', (collection_name,))
            self._conn.commit()

    def insert(self, collection_name: str, items: List[VectorItem]) -> None:
        self._write(collection_name, items)

    def upsert(self, collection_name: str, items: List[VectorItem]) -> None:
        self._write(collection_name, items)

    def _write(self, collection_name: str, items: List[VectorItem]) -> None:
        # Les appelants passent indifféremment des VectorItem ou des dicts bruts
        # (ex. upsert_memory_vectors_or_reindex) — normalisation ici.
        norm = [VectorItem(**item) if isinstance(item, dict) else item for item in items]
        payload = [
            (
                collection_name,
                item.id,
                item.text,
                self._pack(item.vector),
                json.dumps(item.metadata, ensure_ascii=False, default=str)
                if item.metadata is not None
                else None,
            )
            for item in norm
        ]
        with self._lock:
            self._conn.executemany(
                'INSERT OR REPLACE INTO vectors (collection, id, text, vector, metadata) '
                'VALUES (?, ?, ?, ?, ?)',
                payload,
            )
            self._conn.commit()

    def search(
        self,
        collection_name: str,
        vectors: List[List[Union[float, int]]],
        filter: Optional[Dict] = None,
        limit: int = 10,
    ) -> Optional[SearchResult]:
        rows = self._rows(collection_name, filter)
        if not rows:
            return SearchResult(ids=[[] for _ in vectors], documents=[[] for _ in vectors],
                                metadatas=[[] for _ in vectors], distances=[[] for _ in vectors])

        ids = [r[0] for r in rows]
        documents = [r[1] for r in rows]
        metadatas = [self._load_metadata(r[2 + 1]) for r in rows]
        matrix = np.vstack([self._unpack(r[2]) for r in rows])
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        matrix = matrix / norms

        out_ids: List[List[str]] = []
        out_documents: List[List[Optional[str]]] = []
        out_metadatas: List[List[Dict]] = []
        out_scores: List[List[float]] = []

        k = max(1, int(limit or 10))
        for query in vectors:
            q = np.asarray(query, dtype=np.float32)
            q_norm = float(np.linalg.norm(q))
            if q_norm == 0:
                q_norm = 1.0
            scores = matrix @ (q / q_norm)
            k_eff = min(k, scores.shape[0])
            top = np.argpartition(-scores, k_eff - 1)[:k_eff]
            top = top[np.argsort(-scores[top])]
            out_ids.append([ids[i] for i in top])
            out_documents.append([documents[i] for i in top])
            out_metadatas.append([metadatas[i] for i in top])
            # convention open_webui (cf. chroma) : score ramené dans [0,1]
            out_scores.append([float((1.0 + scores[i]) / 2.0) for i in top])

        return SearchResult(
            ids=out_ids,
            documents=out_documents,
            metadatas=out_metadatas,
            distances=out_scores,
        )

    def query(self, collection_name: str, filter: Dict, limit: Optional[int] = None) -> Optional[GetResult]:
        rows = self._rows(collection_name, filter)
        if limit is not None:
            rows = rows[: int(limit)]
        return GetResult(
            ids=[[r[0] for r in rows]],
            documents=[[r[1] for r in rows]],
            metadatas=[[self._load_metadata(r[3]) for r in rows]],
        )

    def get(self, collection_name: str) -> Optional[GetResult]:
        rows = self._rows(collection_name)
        return GetResult(
            ids=[[r[0] for r in rows]],
            documents=[[r[1] for r in rows]],
            metadatas=[[self._load_metadata(r[3]) for r in rows]],
        )

    def delete(
        self,
        collection_name: str,
        ids: Optional[List[str]] = None,
        filter: Optional[Dict] = None,
    ) -> None:
        if ids:
            with self._lock:
                self._conn.executemany(
                    'DELETE FROM vectors WHERE collection = ? AND id = ?',
                    [(collection_name, i) for i in ids],
                )
                self._conn.commit()
            return
        if filter:
            doomed = [r[0] for r in self._rows(collection_name, filter)]
            self.delete(collection_name, ids=doomed)
            return
        self.delete_collection(collection_name)

    def reset(self) -> None:
        with self._lock:
            self._conn.execute('DELETE FROM vectors')
            self._conn.commit()
