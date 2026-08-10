"""Lakebase adapter for the JobSignal MCP server.

All SQL, embeddings and persistence live here so MCP tool functions remain
thin orchestration wrappers. No third-party HTTP calls occur inside tools.
"""

from __future__ import annotations

import os
import re
from contextlib import contextmanager

import psycopg2
from databricks.sdk import WorkspaceClient
from psycopg2.extras import Json, RealDictCursor
from sentence_transformers import SentenceTransformer

_w = WorkspaceClient()
_MODEL = None
_SCHEMA_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_TABLE_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*\.[A-Za-z_][A-Za-z0-9_]*$")
MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME", "sentence-transformers/all-MiniLM-L6-v2")


def _schema() -> str:
    value = os.getenv("JOBSIGNAL_SCHEMA", "jobsignal_app")
    if not _SCHEMA_RE.fullmatch(value):
        raise ValueError("Invalid JOBSIGNAL_SCHEMA")
    return f'"{value}"'


def _jobs() -> str:
    value = os.getenv("JOB_POSTINGS_TABLE", "jobsignal_capstone.gold_jobs_synced")
    if not _TABLE_RE.fullmatch(value):
        raise ValueError("Invalid JOB_POSTINGS_TABLE")
    a, b = value.split(".", 1)
    return f'"{a}"."{b}"'


def _token() -> str:
    return _w.postgres.generate_database_credential(
        endpoint=os.environ["ENDPOINT_NAME"]
    ).token


@contextmanager
def connection():
    conn = psycopg2.connect(
        host=os.environ["PGHOST"],
        port=int(os.environ.get("PGPORT", "5432")),
        dbname=os.environ["PGDATABASE"],
        user=os.environ["PGUSER"],
        password=_token(),
        sslmode=os.environ.get("PGSSLMODE", "require"),
        connect_timeout=15,
        cursor_factory=RealDictCursor,
    )
    try:
        yield conn
    finally:
        conn.close()


def _model():
    global _MODEL
    if _MODEL is None:
        _MODEL = SentenceTransformer(MODEL_NAME)
    return _MODEL


def _vector_literal(text: str) -> str:
    vector = _model().encode(text, normalize_embeddings=True, show_progress_bar=False)
    values = vector.tolist()
    if len(values) != 384:
        raise ValueError("Embedding model must output 384 dimensions")
    return "[" + ",".join(f"{float(v):.9f}" for v in values) + "]"


def _query(sql: str, params=()) -> list[dict]:
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return [dict(row) for row in cur.fetchall()]


def _write_returning(sql: str, params=()) -> dict:
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            row = dict(cur.fetchone())
        conn.commit()
        return row


def _write(sql: str, params=()) -> int:
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            count = cur.rowcount
        conn.commit()
        return count


def _profile_skills(profile_id: int) -> set[str]:
    rows = _query(
        f"SELECT normalized_skill FROM {_schema()}.skills WHERE profile_id=%s",
        (profile_id,),
    )
    return {row["normalized_skill"] for row in rows}


def search_jobs(query: str, profile_id: int = 1, top_k: int = 5) -> list[dict]:
    vector = _vector_literal(query)
    rows = _query(
        f"""
        SELECT j.job_id, j.company, j.title, j.location, j.salary_min, j.salary_max,
               j.source, j.source_url, j.apply_url, j.quality_score,
               j.extracted_skills, j.description_text,
               1 - (e.embedding <=> %s::vector) AS similarity
        FROM {_schema()}.job_embeddings e
        JOIN {_jobs()} j ON j.job_id=e.job_id
        ORDER BY e.embedding <=> %s::vector
        LIMIT %s
        """,
        (vector, vector, max(10, min(top_k * 5, 60))),
    )
    profile_skills = _profile_skills(profile_id)
    best = {}
    for row in rows:
        job_id = row["job_id"]
        if job_id in best and float(best[job_id]["similarity"]) >= float(row["similarity"]):
            continue
        skills = row.get("extracted_skills") or []
        if isinstance(skills, str):
            skills = [skills]
        skills_norm = {str(x).lower() for x in skills}
        matched = sorted(profile_skills & skills_norm)
        overlap = len(matched) / len(skills_norm) if skills_norm else 0.5
        similarity = max(0.0, min(float(row["similarity"]), 1.0))
        quality = max(0.0, min(float(row.get("quality_score") or 0) / 100.0, 1.0))
        score = 100 * (0.65 * similarity + 0.25 * overlap + 0.10 * quality)
        row["similarity"] = round(similarity, 4)
        row["match_score"] = round(score, 1)
        row["matched_skills"] = matched
        row["missing_skills"] = sorted(skills_norm - profile_skills)
        # Keep tool responses compact enough for agent context.
        row["description_preview"] = (row.pop("description_text") or "")[:700]
        best[job_id] = row
    result = sorted(best.values(), key=lambda x: x["match_score"], reverse=True)
    return result[: max(1, min(top_k, 10))]


def get_job_details(job_id: str) -> dict:
    rows = _query(f"SELECT * FROM {_jobs()} WHERE job_id=%s LIMIT 1", (job_id,))
    if not rows:
        raise ValueError(f"Unknown job_id: {job_id}")
    return rows[0]


def save_job(profile_id: int, job_id: str, notes: str = "") -> dict:
    get_job_details(job_id)
    result = _write_returning(
        f"""
        INSERT INTO {_schema()}.saved_jobs (profile_id, job_id, notes)
        VALUES (%s,%s,%s)
        ON CONFLICT (profile_id, job_id)
        DO UPDATE SET notes=EXCLUDED.notes, saved_at=NOW()
        RETURNING saved_job_id, profile_id, job_id, notes, saved_at
        """,
        (profile_id, job_id, notes or None),
    )
    log_action(profile_id, "save_job", {"job_id": job_id, "notes": notes}, result)
    return result


def move_application(profile_id: int, job_id: str, stage: str, follow_up_at: str | None = None) -> dict:
    allowed = {"saved", "applied", "interviewing", "rejected", "offer", "withdrawn"}
    stage = stage.lower().strip()
    if stage not in allowed:
        raise ValueError(f"stage must be one of {sorted(allowed)}")
    job = get_job_details(job_id)
    result = _write_returning(
        f"""
        INSERT INTO {_schema()}.applications
          (profile_id, job_id, company_snapshot, title_snapshot, stage, follow_up_at)
        VALUES (%s,%s,%s,%s,%s,%s)
        ON CONFLICT (profile_id, job_id)
        DO UPDATE SET stage=EXCLUDED.stage,
                      follow_up_at=COALESCE(EXCLUDED.follow_up_at, {_schema()}.applications.follow_up_at),
                      updated_at=NOW()
        RETURNING application_id, profile_id, job_id, company_snapshot AS company,
                  title_snapshot AS title, stage, follow_up_at, updated_at
        """,
        (profile_id, job_id, job.get("company"), job.get("title"), stage, follow_up_at),
    )
    log_action(profile_id, "move_application", {"job_id": job_id, "stage": stage}, result)
    return result


def add_interview_note(profile_id: int, job_id: str, note: str) -> dict:
    if not note.strip():
        raise ValueError("note cannot be empty")
    apps = _query(
        f"SELECT application_id FROM {_schema()}.applications WHERE profile_id=%s AND job_id=%s",
        (profile_id, job_id),
    )
    if not apps:
        raise ValueError("The job must be in the application pipeline before adding notes")
    result = _write_returning(
        f"""
        INSERT INTO {_schema()}.interview_notes (application_id, note_text)
        VALUES (%s,%s)
        RETURNING note_id, application_id, note_text, created_at
        """,
        (apps[0]["application_id"], note.strip()),
    )
    log_action(profile_id, "add_interview_note", {"job_id": job_id}, result)
    return result


def get_stale_applications(profile_id: int = 1, days: int = 7) -> list[dict]:
    return _query(
        f"""
        SELECT application_id, job_id, company_snapshot AS company,
               title_snapshot AS title, stage, updated_at,
               EXTRACT(DAY FROM NOW() - updated_at)::INT AS days_stale
        FROM {_schema()}.applications
        WHERE profile_id=%s
          AND stage IN ('saved','applied','interviewing')
          AND updated_at < NOW() - (%s * INTERVAL '1 day')
        ORDER BY updated_at ASC
        """,
        (profile_id, max(1, min(days, 90))),
    )


def log_action(profile_id: int | None, tool_name: str, arguments: dict, result: dict) -> None:
    _write(
        f"INSERT INTO {_schema()}.agent_action_log (profile_id, tool_name, arguments, result) VALUES (%s,%s,%s,%s)",
        (profile_id, tool_name, Json(arguments), Json(result)),
    )
