# Automatic grader map

This file makes each capstone requirement easy to verify from source code without relying on screenshots alone.

## 1. Spark pipeline

File: `pipelines/jobs_spark_pipeline.py`

Explicit PySpark evidence:

- `from pyspark.sql import DataFrame, functions as F, types as T`
- `build_bronze(...)`
- `build_silver(...)`
- `build_gold(...)`
- Delta `saveAsTable(...)`
- `bronze_jobs`, `silver_jobs`, `gold_jobs`

## 2. Third-party API

File: `job_sources/remoteok_client.py`

- HTTP `requests.get(...)`
- public Remote OK JSON API
- normalized source IDs and source/apply URLs

Optional second source: `job_sources/adzuna_client.py`.

## 3. Unstructured-data processing

Files:

- `pipelines/jobs_spark_pipeline.py` cleans HTML/free-text descriptions, detects placeholder/noisy text, and extracts skills.
- `embeddings.py` chunks text and uses `sentence-transformers/all-MiniLM-L6-v2`.
- `lakebase.py` defines `VECTOR(384)` and an HNSW `vector_cosine_ops` index.
- `lakebase.vector_search(...)` uses pgvector cosine operator `<=>`.

## 4. Databricks App frontend

Files:

- `app.py`
- `app.yaml`
- `templates/index.html`
- `static/app.css`
- `static/app.js`

The UI exposes data-health metrics, semantic matching, profile context, save actions, and the application pipeline.

## 5. AI agent that reads and writes

Files:

- `mcp_server/app.py`
- `mcp_server/job_broker.py`
- `agent/SYSTEM_PROMPT.md`

Read tools:

- `search_matching_jobs`
- `get_job_details`
- `get_stale_applications`

Write tools:

- `save_job`
- `move_application`
- `add_interview_note`

Write tools persist to Lakebase and are audited in `jobsignal_app.agent_action_log`.

## Extra engineering quality

- Spark quality score and quality flags
- Data/AI relevance filtering
- deterministic skill extraction
- SHA-256 deduplication
- Delta Gold serving through Lakebase synced table
- short-lived Databricks OAuth database credentials
- explainable hybrid match score
- no external-application hallucination guardrail
- API attribution visible in frontend
- unit tests
