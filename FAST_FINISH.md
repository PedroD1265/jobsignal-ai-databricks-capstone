# JobSignal AI — Fast Finish

The codebase is complete. The Spark pipeline and Lakebase synced table are already validated in the target workspace.

## Completed

1. Remote OK third-party API ingestion.
2. Spark Bronze → Silver → Gold.
3. Gold Delta table: 97 serving-ready rows from the validated run.
4. Lakebase synced table `jobsignal_capstone.gold_jobs_synced`: Online / Active.

## Remaining critical path

### 1. Deploy the frontend Databricks App
Deploy the repository root as a custom Databricks App. Add the existing Lakebase Autoscaling database as an App resource:

- Project: `dataexpert-support-app`
- Branch: `production`
- Database: `databricks_postgres`

The app uses `app.yaml`, creates the `jobsignal_app` operational schema on first API use, and seeds a demo profile automatically from the frontend.

### 2. Create embeddings
Open the deployed JobSignal frontend and click **Embed Jobs**. The app writes MiniLM 384-dimensional vectors to `jobsignal_app.job_embeddings` and creates an HNSW pgvector index.

Then search:

`remote data engineering roles using Python SQL Spark and Databricks`

### 3. Deploy the MCP App
Create a second Databricks App named `mcp-jobsignal-ai` using repository source path `mcp_server`. Add the same Lakebase resource. The MCP endpoint is `/mcp`.

### 4. Agent proof
Connect the MCP App in AI Playground / an agent and run:

1. `Find the best five remote jobs for Python, SQL, Spark and Databricks.`
2. `Save the best one with the note Review this tonight.`
3. `I applied to that role. Record it as applied.`

Refresh the frontend and show the persisted write.

## Submission evidence still needed

- frontend overview
- semantic matches
- MCP server active/tool discovery
- agent `search_matching_jobs` call
- agent `save_job` write
- agent `move_application` write and persisted application stage
