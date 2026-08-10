# Capstone submission checklist

## Official requirement mapping

- [x] **Spark data pipeline** — `pipelines/jobs_spark_pipeline.py` implements Bronze → Silver → Gold.
- [x] **Third-party API** — Remote OK is required and keyless; Adzuna is optional.
- [x] **Unstructured data** — HTML/free-text job descriptions are cleaned, embedded, and semantically retrieved.
- [x] **Databricks App frontend** — Flask app in the repository root.
- [x] **AI agent with read + write tools** — FastMCP server in `mcp_server/`.

## Quality / differentiation

- [x] Explainable Spark `quality_score` and `quality_flags`.
- [x] Data/AI `relevance_score` and deterministic skill extraction.
- [x] Deduplication before Gold serving.
- [x] Lakebase synced table for curated Gold serving.
- [x] `VECTOR(384)` + HNSW cosine retrieval.
- [x] Hybrid match score: semantic + skill overlap + data quality.
- [x] Persistent save/application/note actions.
- [x] Agent action audit log.
- [x] No hardcoded credentials.
- [x] Source attribution in the frontend.

## Before final ZIP

- [ ] Spark pipeline successfully executed in the target Databricks workspace.
- [ ] Gold Delta table contains trusted Data/AI jobs.
- [ ] Gold table synced into Lakebase.
- [ ] Job embeddings created.
- [ ] Frontend Databricks App deployed and tested.
- [ ] MCP Databricks App deployed with an `mcp-` name.
- [ ] Agent configured with `agent/SYSTEM_PROMPT.md`.
- [ ] At least 3 agent demonstrations captured, including at least 1 write action.
- [ ] Screenshots saved under `evidence/`.
- [ ] Databricks App URLs and repository URL added to `SUBMISSION.md`.
- [ ] No secrets present in repo or screenshots.
