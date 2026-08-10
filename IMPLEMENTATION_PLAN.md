# Fastest high-quality implementation plan

## Phase A — foundation (already scaffolded)
- Spark pipeline
- source adapters
- Lakebase schema
- vector pipeline
- frontend
- MCP server
- system prompt
- tests and evidence plan

## Phase B — Databricks integration
1. Import/pull repository into the existing Azure Databricks workspace.
2. Run Spark Bronze/Silver/Gold pipeline.
3. Create Lakebase synced Gold table.
4. Deploy `jobsignal-ai` frontend with Lakebase resource.
5. Seed demo profile and embed Gold jobs.

## Phase C — agent
1. Deploy `mcp-jobsignal-ai` from `mcp_server/`.
2. Register it as MCP in AI Gateway / Playground.
3. Attach `agent/SYSTEM_PROMPT.md`.
4. Run retrieval and at least two persistent write demonstrations.

## Phase D — polish / grading
1. Capture evidence from `evidence/README.md`.
2. Fill URLs in `SUBMISSION.md`.
3. Run unit tests and secret scan.
4. Produce final ZIP containing source + README + evidence.

## Optional only after the required path is green
- Enable Adzuna as a second source.
- Add scheduled/triggered pipeline refresh.
- Add contact management UI.
- Add LLM-generated tailored resume bullet as a non-authoritative drafting feature.
- Add application funnel analytics.

Do not add these before the required end-to-end demo works; they increase surface area without improving the core rubric as much as a reliable Spark → App → Agent write flow.
