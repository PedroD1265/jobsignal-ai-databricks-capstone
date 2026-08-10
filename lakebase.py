"""Lakebase connection and operational persistence for JobSignal AI.

The Databricks App database resource injects PGHOST, PGPORT, PGDATABASE,
PGUSER and PGSSLMODE. A short-lived OAuth credential is generated for each
new connection, so the project never stores a database password.
"""

from __future__ import annotations

import json
import os
import re
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any

import psycopg2
from databricks.sdk import WorkspaceClient
from psycopg2.extras import Json, RealDictCursor, execute_values

_w = WorkspaceClient()

_SCHEMA_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_TABLE_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*\.[A-Za-z_][A-Za-z0-9_]*$")


def _schema() -> str:
    value = os.getenv("JOBSIGNAL_SCHEMA", "jobsignal_app")
    if not _SCHEMA_RE.fullmatch(value):
        raise ValueError("Invalid JOBSIGNAL_SCHEMA")
    return value


def _job_table() -> str:
    value = os.getenv("JOB_POSTINGS_TABLE", "jobsignal_capstone.gold_jobs_synced")
    if not _TABLE_RE.fullmatch(value):
        raise ValueError("JOB_POSTINGS_TABLE must be schema.table using simple identifiers")
    schema, table = value.split(".", 1)
    return f'"{schema}"."{table}"'


def _qname(name: str) -> str:
    if not _SCHEMA_RE.fullmatch(name):
        raise ValueError("Unsafe SQL identifier")
    return f'"{name}"'


def _database_token() -> str:
    endpoint_name = os.environ["ENDPOINT_NAME"]
    credential = _w.postgres.generate_database_credential(endpoint=endpoint_name)
    return credential.token


@contextmanager
def get_connection():
    conn = psycopg2.connect(
        host=os.environ["PGHOST"],
        port=int(os.environ.get("PGPORT", "5432")),
        dbname=os.environ["PGDATABASE"],
        user=os.environ["PGUSER"],
        password=_database_token(),
        sslmode=os.environ.get("PGSSLMODE", "require"),
        connect_timeout=15,
        cursor_factory=RealDictCursor,
    )
    try:
        yield conn
    finally:
        conn.close()


def run_query(sql: str, params: tuple | list | None = None) -> list[dict]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return [dict(row) for row in cur.fetchall()]


def run_write(sql: str, params: tuple | list | None = None) -> int:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            affected = cur.rowcount
        conn.commit()
        return affected


def run_write_returning(sql: str, params: tuple | list | None = None) -> dict:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            row = dict(cur.fetchone())
        conn.commit()
        return row


def ensure_schema() -> None:
    schema = _schema()
    qschema = _qname(schema)
    statements = [
        f"CREATE SCHEMA IF NOT EXISTS {qschema}",
        f"""
        CREATE TABLE IF NOT EXISTS {qschema}.profiles (
            profile_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            display_name TEXT NOT NULL,
            headline TEXT,
            target_roles JSONB NOT NULL DEFAULT '[]'::jsonb,
            preferred_locations JSONB NOT NULL DEFAULT '[]'::jsonb,
            remote_only BOOLEAN NOT NULL DEFAULT TRUE,
            min_salary INTEGER,
            resume_text TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """,
        f"""
        CREATE TABLE IF NOT EXISTS {qschema}.skills (
            skill_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            profile_id BIGINT NOT NULL REFERENCES {qschema}.profiles(profile_id) ON DELETE CASCADE,
            skill_name TEXT NOT NULL,
            normalized_skill TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE(profile_id, normalized_skill)
        )
        """,
        f"""
        CREATE TABLE IF NOT EXISTS {qschema}.job_embeddings (
            embedding_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            job_id TEXT NOT NULL,
            chunk_index INTEGER NOT NULL CHECK (chunk_index >= 0),
            chunk_text TEXT NOT NULL,
            embedding VECTOR(384) NOT NULL,
            model_name TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE(job_id, chunk_index, model_name)
        )
        """,
        f"""
        CREATE TABLE IF NOT EXISTS {qschema}.saved_jobs (
            saved_job_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            profile_id BIGINT NOT NULL REFERENCES {qschema}.profiles(profile_id) ON DELETE CASCADE,
            job_id TEXT NOT NULL,
            notes TEXT,
            saved_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE(profile_id, job_id)
        )
        """,
        f"""
        CREATE TABLE IF NOT EXISTS {qschema}.applications (
            application_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            profile_id BIGINT NOT NULL REFERENCES {qschema}.profiles(profile_id) ON DELETE CASCADE,
            job_id TEXT NOT NULL,
            company_snapshot TEXT,
            title_snapshot TEXT,
            stage TEXT NOT NULL DEFAULT 'saved'
                CHECK (stage IN ('saved','applied','interviewing','rejected','offer','withdrawn')),
            follow_up_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE(profile_id, job_id)
        )
        """,
        f"""
        CREATE TABLE IF NOT EXISTS {qschema}.interview_notes (
            note_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            application_id BIGINT NOT NULL REFERENCES {qschema}.applications(application_id) ON DELETE CASCADE,
            note_text TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """,
        f"""
        CREATE TABLE IF NOT EXISTS {qschema}.contacts (
            contact_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            profile_id BIGINT NOT NULL REFERENCES {qschema}.profiles(profile_id) ON DELETE CASCADE,
            job_id TEXT,
            name TEXT NOT NULL,
            company TEXT,
            role TEXT,
            contact_url TEXT,
            notes TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """,
        f"""
        CREATE TABLE IF NOT EXISTS {qschema}.agent_action_log (
            action_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            profile_id BIGINT REFERENCES {qschema}.profiles(profile_id) ON DELETE SET NULL,
            tool_name TEXT NOT NULL,
            arguments JSONB NOT NULL DEFAULT '{{}}'::jsonb,
            result JSONB NOT NULL DEFAULT '{{}}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """,
        f"CREATE INDEX IF NOT EXISTS job_embeddings_hnsw_idx ON {qschema}.job_embeddings USING hnsw (embedding vector_cosine_ops)",
        f"CREATE INDEX IF NOT EXISTS applications_stage_idx ON {qschema}.applications(stage)",
        f"CREATE INDEX IF NOT EXISTS applications_updated_idx ON {qschema}.applications(updated_at)",
    ]
    with get_connection() as conn:
        with conn.cursor() as cur:
            for statement in statements:
                cur.execute(statement)
        conn.commit()


def source_table_available() -> bool:
    try:
        run_query(f"SELECT job_id FROM {_job_table()} LIMIT 1")
        return True
    except Exception:
        return False


def get_profile(profile_id: int = 1) -> dict | None:
    ensure_schema()
    schema = _qname(_schema())
    rows = run_query(
        f"SELECT * FROM {schema}.profiles WHERE profile_id = %s",
        (profile_id,),
    )
    if not rows:
        return None
    profile = rows[0]
    profile["skills"] = [
        row["skill_name"]
        for row in run_query(
            f"SELECT skill_name FROM {schema}.skills WHERE profile_id = %s ORDER BY skill_name",
            (profile_id,),
        )
    ]
    return profile


def upsert_profile(data: dict, profile_id: int | None = None) -> dict:
    ensure_schema()
    schema = _qname(_schema())
    target_roles = data.get("target_roles") or []
    preferred_locations = data.get("preferred_locations") or []
    skills = [str(x).strip() for x in (data.get("skills") or []) if str(x).strip()]

    with get_connection() as conn:
        with conn.cursor() as cur:
            if profile_id:
                cur.execute(
                    f"""
                    UPDATE {schema}.profiles
                    SET display_name=%s, headline=%s, target_roles=%s,
                        preferred_locations=%s, remote_only=%s, min_salary=%s,
                        resume_text=%s, updated_at=NOW()
                    WHERE profile_id=%s
                    RETURNING *
                    """,
                    (
                        data.get("display_name") or "Candidate",
                        data.get("headline"),
                        Json(target_roles),
                        Json(preferred_locations),
                        bool(data.get("remote_only", True)),
                        data.get("min_salary"),
                        data.get("resume_text"),
                        profile_id,
                    ),
                )
                row = cur.fetchone()
                if row is None:
                    profile_id = None
            if not profile_id:
                cur.execute(
                    f"""
                    INSERT INTO {schema}.profiles
                    (display_name, headline, target_roles, preferred_locations,
                     remote_only, min_salary, resume_text)
                    VALUES (%s,%s,%s,%s,%s,%s,%s)
                    RETURNING *
                    """,
                    (
                        data.get("display_name") or "Candidate",
                        data.get("headline"),
                        Json(target_roles),
                        Json(preferred_locations),
                        bool(data.get("remote_only", True)),
                        data.get("min_salary"),
                        data.get("resume_text"),
                    ),
                )
                row = cur.fetchone()
                profile_id = row["profile_id"]

            cur.execute(f"DELETE FROM {schema}.skills WHERE profile_id=%s", (profile_id,))
            if skills:
                execute_values(
                    cur,
                    f"INSERT INTO {schema}.skills (profile_id, skill_name, normalized_skill) VALUES %s ON CONFLICT DO NOTHING",
                    [(profile_id, skill, skill.lower()) for skill in skills],
                    template="(%s,%s,%s)",
                )
        conn.commit()
    return get_profile(int(profile_id))


def seed_demo_profile() -> dict:
    ensure_schema()
    schema = _qname(_schema())
    rows = run_query(
        f"SELECT profile_id FROM {schema}.profiles WHERE display_name = %s ORDER BY profile_id LIMIT 1",
        ("Demo Data Engineer",),
    )
    if rows:
        return get_profile(int(rows[0]["profile_id"]))
    return upsert_profile(
        {
            "display_name": "Demo Data Engineer",
            "headline": "Data Engineer building cloud data and AI systems",
            "target_roles": ["Data Engineer", "Analytics Engineer", "AI Data Engineer"],
            "preferred_locations": ["Worldwide", "Latin America", "Remote"],
            "remote_only": True,
            "min_salary": 45000,
            "skills": [
                "Python", "SQL", "Spark", "Databricks", "Postgres", "AWS",
                "Azure", "Airflow", "Docker", "Git", "Delta Lake",
            ],
            "resume_text": (
                "Data Engineer with hands-on experience in Python, SQL, Apache Spark, "
                "Databricks, Delta Lake, Postgres, AWS and Azure. Builds ETL/ELT pipelines, "
                "Lakehouse solutions, APIs and AI-enabled data applications."
            ),
        }
    )


def get_job(job_id: str) -> dict | None:
    rows = run_query(
        f"SELECT * FROM {_job_table()} WHERE job_id=%s LIMIT 1",
        (job_id,),
    )
    return rows[0] if rows else None


def get_unembedded_jobs(model_name: str, limit: int = 500) -> list[dict]:
    ensure_schema()
    schema = _qname(_schema())
    return run_query(
        f"""
        SELECT j.job_id, j.company, j.title, j.location, j.description_text,
               j.extracted_skills, j.quality_score
        FROM {_job_table()} j
        WHERE NOT EXISTS (
            SELECT 1 FROM {schema}.job_embeddings e
            WHERE e.job_id=j.job_id AND e.model_name=%s
        )
        ORDER BY j.quality_score DESC, j.published_at DESC NULLS LAST
        LIMIT %s
        """,
        (model_name, limit),
    )


def insert_embedding_rows(rows: list[tuple], page_size: int = 100) -> int:
    if not rows:
        return 0
    ensure_schema()
    schema = _qname(_schema())
    with get_connection() as conn:
        with conn.cursor() as cur:
            execute_values(
                cur,
                f"""
                INSERT INTO {schema}.job_embeddings
                    (job_id, chunk_index, chunk_text, embedding, model_name)
                VALUES %s
                ON CONFLICT (job_id, chunk_index, model_name)
                DO UPDATE SET chunk_text=EXCLUDED.chunk_text,
                              embedding=EXCLUDED.embedding,
                              created_at=NOW()
                """,
                rows,
                template="(%s,%s,%s,%s::vector,%s)",
                page_size=page_size,
            )
        conn.commit()
    return len(rows)


def vector_search(query_vector: str, top_k: int = 10) -> list[dict]:
    ensure_schema()
    schema = _qname(_schema())
    return run_query(
        f"""
        SELECT j.job_id, j.source, j.source_url, j.apply_url, j.company, j.title,
               j.location, j.salary_min, j.salary_max, j.description_text,
               j.quality_score, j.relevance_score, j.extracted_skills,
               e.chunk_index, e.chunk_text,
               1 - (e.embedding <=> %s::vector) AS similarity
        FROM {schema}.job_embeddings e
        JOIN {_job_table()} j ON j.job_id=e.job_id
        ORDER BY e.embedding <=> %s::vector
        LIMIT %s
        """,
        (query_vector, query_vector, max(1, min(top_k * 4, 80))),
    )


def save_job(profile_id: int, job_id: str, notes: str | None = None) -> dict:
    ensure_schema()
    schema = _qname(_schema())
    if not get_job(job_id):
        raise ValueError(f"Unknown job_id: {job_id}")
    run_write(
        f"""
        INSERT INTO {schema}.saved_jobs (profile_id, job_id, notes)
        VALUES (%s,%s,%s)
        ON CONFLICT (profile_id, job_id)
        DO UPDATE SET notes=COALESCE(EXCLUDED.notes, {schema}.saved_jobs.notes), saved_at=NOW()
        """,
        (profile_id, job_id, notes),
    )
    return {"profile_id": profile_id, "job_id": job_id, "status": "saved"}


def set_application_stage(
    profile_id: int,
    job_id: str,
    stage: str,
    follow_up_at: str | None = None,
) -> dict:
    allowed = {"saved", "applied", "interviewing", "rejected", "offer", "withdrawn"}
    if stage not in allowed:
        raise ValueError(f"stage must be one of {sorted(allowed)}")
    ensure_schema()
    schema = _qname(_schema())
    job = get_job(job_id)
    if not job:
        raise ValueError(f"Unknown job_id: {job_id}")
    row = run_write_returning(
        f"""
        INSERT INTO {schema}.applications
            (profile_id, job_id, company_snapshot, title_snapshot, stage, follow_up_at)
        VALUES (%s,%s,%s,%s,%s,%s)
        ON CONFLICT (profile_id, job_id)
        DO UPDATE SET stage=EXCLUDED.stage,
                      follow_up_at=COALESCE(EXCLUDED.follow_up_at, {schema}.applications.follow_up_at),
                      company_snapshot=EXCLUDED.company_snapshot,
                      title_snapshot=EXCLUDED.title_snapshot,
                      updated_at=NOW()
        RETURNING *
        """,
        (profile_id, job_id, job.get("company"), job.get("title"), stage, follow_up_at),
    )
    return row


def list_applications(profile_id: int = 1) -> list[dict]:
    ensure_schema()
    schema = _qname(_schema())
    return run_query(
        f"""
        SELECT application_id, profile_id, job_id, company_snapshot AS company,
               title_snapshot AS title, stage, follow_up_at, created_at, updated_at
        FROM {schema}.applications
        WHERE profile_id=%s
        ORDER BY updated_at DESC
        """,
        (profile_id,),
    )


def add_interview_note(profile_id: int, job_id: str, note_text: str) -> dict:
    ensure_schema()
    schema = _qname(_schema())
    apps = run_query(
        f"SELECT application_id FROM {schema}.applications WHERE profile_id=%s AND job_id=%s",
        (profile_id, job_id),
    )
    if not apps:
        raise ValueError("Create an application tracker entry before adding interview notes")
    row = run_write_returning(
        f"""
        INSERT INTO {schema}.interview_notes (application_id, note_text)
        VALUES (%s,%s) RETURNING *
        """,
        (apps[0]["application_id"], note_text),
    )
    return row


def stale_applications(profile_id: int = 1, days: int = 7) -> list[dict]:
    ensure_schema()
    schema = _qname(_schema())
    return run_query(
        f"""
        SELECT application_id, job_id, company_snapshot AS company,
               title_snapshot AS title, stage, updated_at,
               EXTRACT(DAY FROM NOW() - updated_at)::INT AS days_stale
        FROM {schema}.applications
        WHERE profile_id=%s
          AND stage IN ('saved','applied','interviewing')
          AND updated_at < NOW() - (%s * INTERVAL '1 day')
        ORDER BY updated_at ASC
        """,
        (profile_id, max(1, min(days, 90))),
    )


def log_agent_action(profile_id: int | None, tool_name: str, arguments: dict, result: dict) -> None:
    ensure_schema()
    schema = _qname(_schema())
    run_write(
        f"INSERT INTO {schema}.agent_action_log (profile_id, tool_name, arguments, result) VALUES (%s,%s,%s,%s)",
        (profile_id, tool_name, Json(arguments), Json(result)),
    )


def stats(profile_id: int = 1) -> dict:
    ensure_schema()
    schema = _qname(_schema())
    source = {"jobs": 0, "high_quality_jobs": 0, "avg_quality": 0, "last_ingested_at": None}
    try:
        source = run_query(
            f"""
            SELECT COUNT(*) AS jobs,
                   COUNT(*) FILTER (WHERE quality_score >= 80) AS high_quality_jobs,
                   ROUND(AVG(quality_score)::numeric, 1) AS avg_quality,
                   MAX(ingested_at) AS last_ingested_at
            FROM {_job_table()}
            """
        )[0]
    except Exception:
        pass

    app_counts = run_query(
        f"""
        SELECT
          (SELECT COUNT(*) FROM {schema}.saved_jobs WHERE profile_id=%s) AS saved,
          (SELECT COUNT(*) FROM {schema}.applications WHERE profile_id=%s) AS applications,
          (SELECT COUNT(*) FROM {schema}.job_embeddings) AS embedding_chunks,
          (SELECT COUNT(DISTINCT job_id) FROM {schema}.job_embeddings) AS embedded_jobs
        """,
        (profile_id, profile_id),
    )[0]
    return {**source, **app_counts, "source_table_available": source_table_available()}
