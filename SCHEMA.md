# Schema and data contracts

## Delta / Unity Catalog

### `jobsignal_capstone.bronze_jobs`
Normalized third-party API records with original HTML/text description, source IDs, URLs, salary fields, tags, and ingestion/run metadata.

### `jobsignal_capstone.silver_jobs`
Bronze plus deterministic transformations:

- cleaned `description_text`
- `quality_score INT`
- `quality_flags ARRAY<STRING>`
- `relevance_score INT`
- `extracted_skills ARRAY<STRING>`
- SHA-256 `dedup_key`
- quality/relevance booleans

### `jobsignal_capstone.gold_jobs`
Deduplicated trusted Data/AI job rows. `job_id` is the primary serving key and includes the source prefix.

## Lakebase synced table

Expected destination:

`jobsignal_capstone.gold_jobs_synced`

Primary key: `job_id`.

## Lakebase operational schema: `jobsignal_app`

### `profiles`
Candidate preferences and resume text.

### `skills`
Normalized candidate skills. FK → `profiles.profile_id`.

### `job_embeddings`
Chunk-level vectors:

- `job_id`
- `chunk_index`
- `chunk_text`
- `embedding VECTOR(384)`
- `model_name`

Unique `(job_id, chunk_index, model_name)`. HNSW index uses `vector_cosine_ops`.

### `saved_jobs`
Persistent user bookmarks. FK → `profiles.profile_id`.

### `applications`
Pipeline stages constrained to `saved`, `applied`, `interviewing`, `rejected`, `offer`, `withdrawn`.

### `interview_notes`
FK → `applications.application_id`.

### `contacts`
Optional recruiter/contact notes.

### `agent_action_log`
Auditable record of agent write tools, arguments, and results.
