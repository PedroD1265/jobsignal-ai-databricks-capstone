# Evidence capture plan

Use screenshots with visible UI labels and successful results. Suggested filenames:

1. `01_spark_pipeline_metrics.png` — notebook output showing Bronze, Silver, Gold and rejected counts.
2. `02_gold_delta_table.png` — Unity Catalog Gold rows with quality/relevance scores and extracted skills.
3. `03_lakebase_synced_and_operational.png` — synced Gold table plus `jobsignal_app` operational tables.
4. `04_frontend_overview.png` — JobSignal dashboard with Data Health metrics.
5. `05_semantic_matches.png` — ranked search with match score, matched and missing skills.
6. `06_application_pipeline_write.png` — persisted application stage visible after refresh.
7. `07_mcp_server_active.png` — MCP Databricks App / AI Gateway connection.
8. `08_agent_search_tool.png` — agent calling `search_matching_jobs` and returning ranked jobs.
9. `09_agent_save_write.png` — agent calling `save_job`.
10. `10_agent_application_write.png` — agent calling `move_application` and confirmation reflected in the app.

Do not include credentials, tokens, app client secrets, database passwords, or API keys in screenshots.
