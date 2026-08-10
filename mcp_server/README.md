# JobSignal AI MCP Server

Deploy this directory as a separate Databricks App named `mcp-jobsignal-ai`.
Attach the same Lakebase database resource as the frontend app.

Expected endpoint:

`https://<mcp-app-url>/mcp`

Tools:

1. `search_matching_jobs` - semantic + skills + quality retrieval.
2. `get_job_details` - authoritative job lookup.
3. `save_job` - durable write to saved jobs.
4. `move_application` - durable application-stage write.
5. `add_interview_note` - durable note write.
6. `get_stale_applications` - follow-up workflow support.

The MCP app follows Databricks' stateless FastMCP HTTP pattern so it is safe
across horizontally scaled app replicas.
