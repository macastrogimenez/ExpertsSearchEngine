import json
import os
from pathlib import Path
from threading import Lock
from typing import Literal
from uuid import uuid4

import faiss
import numpy as np
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

app = FastAPI(title="Academic FAISS Service")

DIMENSIONS = 768  # nomic-embed-text
DATA_DIR = Path("/data")
CURRENT = DATA_DIR / "CURRENT"

DATA_DIR.mkdir(parents=True, exist_ok=True)

lock = Lock()


# ---------- API models ----------

class VectorDocument(BaseModel):
    documentType: Literal["paper", "project", "course"]
    documentId: str
    embedding: list[float]


class BatchRequest(BaseModel):
    documents: list[VectorDocument] = Field(
        min_length=1,
        max_length=100
    )


class SearchRequest(BaseModel):
    embedding: list[float]
    k: int = Field(default=10, ge=1, le=1000)


# ---------- Index persistence ----------

def create_index():
    return faiss.IndexIDMap2(
        faiss.IndexFlatIP(DIMENSIONS)
    )


def load_index():
    if not CURRENT.exists():
        return create_index(), {}

    version = CURRENT.read_text().strip()

    index = faiss.read_index(
        str(DATA_DIR / f"index-{version}.faiss")
    )

    mapping = json.loads(
        (DATA_DIR / f"mapping-{version}.json").read_text()
    )

    if index.d != DIMENSIONS or index.ntotal != len(mapping):
        raise RuntimeError("Invalid persisted FAISS index")

    stored_ids = set(
        faiss.vector_to_array(index.id_map).tolist()
    )

    if stored_ids != {int(i) for i in mapping}:
        raise RuntimeError("Index and mapping IDs differ")

    return index, mapping


def save_snapshot(new_index, new_mapping):
    version = uuid4().hex

    index_path = DATA_DIR / f"index-{version}.faiss"
    mapping_path = DATA_DIR / f"mapping-{version}.json"

    # Write both files before activating the snapshot.
    faiss.write_index(new_index, str(index_path))

    mapping_path.write_text(
        json.dumps(new_mapping),
        encoding="utf-8"
    )

    # Atomically switch the active snapshot.
    temporary = DATA_DIR / f"CURRENT-{version}.tmp"
    temporary.write_text(version, encoding="utf-8")
    os.replace(temporary, CURRENT)

    # Remove older snapshots after the new one is active.
    for pattern, active in [
        ("index-*.faiss", index_path),
        ("mapping-*.json", mapping_path),
    ]:
        for path in DATA_DIR.glob(pattern):
            if path != active:
                try:
                    path.unlink()
                except OSError:
                    pass


index, mapping = load_index()


# ---------- Vector validation ----------

def prepare_vectors(embeddings):
    if any(len(v) != DIMENSIONS for v in embeddings):
        raise HTTPException(400, "Incorrect vector dimensions")

    vectors = np.asarray(embeddings, dtype=np.float32)

    if (
        not np.isfinite(vectors).all()
        or np.any(np.linalg.norm(vectors, axis=1) == 0)
    ):
        raise HTTPException(400, "Invalid embeddings")

    faiss.normalize_L2(vectors)

    return vectors


# ---------- Add documents ----------

@app.post("/vectors/batch")
def add_documents(request: BatchRequest):
    global index, mapping

    documents = request.documents

    keys = [
        (doc.documentType, doc.documentId)
        for doc in documents
    ]

    if len(set(keys)) != len(keys):
        raise HTTPException(400, "Duplicate documents in batch")

    vectors = prepare_vectors(
        [doc.embedding for doc in documents]
    )

    with lock:
        existing = {
            (item["documentType"], item["documentId"])
            for item in mapping.values()
        }

        if any(key in existing for key in keys):
            raise HTTPException(409, "Document already indexed")

        next_index = faiss.clone_index(index)
        next_mapping = mapping.copy()

        first_id = max(
            (int(i) for i in mapping),
            default=0
        ) + 1

        ids = np.arange(
            first_id,
            first_id + len(documents),
            dtype=np.int64
        )

        for numeric_id, doc in zip(ids, documents):
            next_mapping[str(int(numeric_id))] = {
                "documentType": doc.documentType,
                "documentId": doc.documentId
            }

        next_index.add_with_ids(vectors, ids)

        # Persist before publishing the updated state.
        save_snapshot(next_index, next_mapping)

        index = next_index
        mapping = next_mapping

        return {
            "inserted": len(documents),
            "totalVectors": index.ntotal
        }


# ---------- Search documents ----------

@app.post("/search")
def search(request: SearchRequest):
    vector = prepare_vectors([request.embedding])

    with lock:
        scores, ids = index.search(vector, request.k)

        results = []

        for numeric_id, score in zip(ids[0], scores[0]):
            if numeric_id == -1:
                continue

            document = mapping[str(int(numeric_id))]

            results.append({
                "documentType": document["documentType"],
                "documentId": document["documentId"],
                "score": float(score)
            })

    return {"results": results}


# ---------- Health check ----------

@app.get("/health")
def health():
    with lock:
        return {
            "status": "ok",
            "totalVectors": index.ntotal,
            "dimensions": DIMENSIONS
        }