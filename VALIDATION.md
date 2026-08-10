# Scaffold validation

Validation performed before first Databricks deployment:

- Python source compilation: **PASS** (`python -m compileall`)
- Unit tests: **PASS — 3/3**
- Frontend JavaScript syntax: **PASS** (`node --check static/app.js`)
- Secret-pattern scan: **PASS — no committed credentials found**

Integration validation still required in the target Databricks workspace:

- live Spark pipeline execution
- Lakebase synced table creation
- vector embedding run
- frontend deployment
- MCP deployment/tool discovery
- agent read/write demonstrations
