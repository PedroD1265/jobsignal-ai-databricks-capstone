"""Sentence-transformer embedding pipeline for trusted job descriptions."""

from __future__ import annotations

import os

from sentence_transformers import SentenceTransformer

import lakebase

MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME", "sentence-transformers/all-MiniLM-L6-v2")
EMBEDDING_DIM = 384
CHUNK_SIZE = int(os.getenv("JOB_CHUNK_SIZE", "1200"))
CHUNK_OVERLAP = int(os.getenv("JOB_CHUNK_OVERLAP", "150"))
_MODEL: SentenceTransformer | None = None


def get_model() -> SentenceTransformer:
    global _MODEL
    if _MODEL is None:
        _MODEL = SentenceTransformer(MODEL_NAME)
    return _MODEL


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    text = (text or "").strip()
    if not text:
        return []
    if chunk_size <= 0 or overlap < 0 or overlap >= chunk_size:
        raise ValueError("Invalid chunking configuration")
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(text):
            break
        start = end - overlap
    return chunks


def _vector_literal(vector) -> str:
    values = vector.tolist() if hasattr(vector, "tolist") else list(vector)
    if len(values) != EMBEDDING_DIM:
        raise ValueError(f"Expected {EMBEDDING_DIM} dimensions, got {len(values)}")
    return "[" + ",".join(f"{float(v):.9f}" for v in values) + "]"


def embed_query(text: str) -> str:
    vector = get_model().encode(text, normalize_embeddings=True, show_progress_bar=False)
    return _vector_literal(vector)


def embed_pending_jobs(limit: int = 500) -> dict:
    jobs = lakebase.get_unembedded_jobs(MODEL_NAME, limit=limit)
    if not jobs:
        return {"jobs_processed": 0, "chunks_embedded": 0, "model": MODEL_NAME, "dimensions": 384}

    model = get_model()
    rows: list[tuple] = []
    processed = 0
    for job in jobs:
        skills = job.get("extracted_skills") or []
        if isinstance(skills, str):
            skills = [skills]
        semantic_text = (
            f"Role: {job.get('title') or ''}. Company: {job.get('company') or ''}. "
            f"Location: {job.get('location') or ''}. Skills: {', '.join(skills)}. "
            f"Description: {job.get('description_text') or ''}"
        )
        chunks = chunk_text(semantic_text)
        if not chunks:
            continue
        vectors = model.encode(chunks, normalize_embeddings=True, show_progress_bar=False, batch_size=32)
        for index, (chunk, vector) in enumerate(zip(chunks, vectors)):
            rows.append((job["job_id"], index, chunk, _vector_literal(vector), MODEL_NAME))
        processed += 1

    inserted = lakebase.insert_embedding_rows(rows)
    return {
        "jobs_processed": processed,
        "chunks_embedded": inserted,
        "model": MODEL_NAME,
        "dimensions": EMBEDDING_DIM,
        "chunk_size": CHUNK_SIZE,
        "chunk_overlap": CHUNK_OVERLAP,
    }
