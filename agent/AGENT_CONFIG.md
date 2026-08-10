# Agent configuration

## Recommended name

`JobSignal AI Career Copilot`

## External tool

Register the deployed Databricks App whose name starts with `mcp-` and use its `/mcp` endpoint as the external MCP server.

Expected tools:

- `search_matching_jobs`
- `get_job_details`
- `save_job`
- `move_application`
- `add_interview_note`
- `get_stale_applications`

## Demo questions

1. `Find me remote Data Engineer roles where Python, SQL, Spark, or Databricks are important. Rank the best five for my profile and explain my biggest skill gap for each.`
2. `Save the best matching role from that list with the note "Review this tonight".`
3. `I applied to the role you just saved. Update my tracker to applied.`
4. `Which of my active applications have gone stale for at least 7 days?`

The first proves retrieval/ranking. The second and third prove real Lakebase write actions. The fourth proves the agent can reason over persisted application state.
