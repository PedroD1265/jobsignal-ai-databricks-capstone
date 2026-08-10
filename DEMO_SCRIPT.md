# 4-minute capstone demo script

## 0:00–0:40 — The data problem
Show the Spark notebook output. Explain that a public job API is useful but noisy, so the pipeline does not send raw feed data directly to an agent. Point out Bronze → Silver → Gold and the number of records rejected by trust/relevance rules.

## 0:40–1:15 — Serving architecture
Show the Gold Delta table, then the Lakebase synced table and operational tables. Explain: Delta/Spark handles analytical transformation; Lakebase handles low-latency serving and mutable application state.

## 1:15–2:15 — Semantic matching frontend
Open JobSignal AI. Show Data Health metrics and search:

`remote data engineering roles using Python SQL Spark and Databricks`

Open the top results and call out match score, data quality, matched skills, and missing skills.

## 2:15–3:30 — Agent that actually acts
In AI Playground / Agent Bricks ask:

`Find me the best five remote Data Engineer roles for my profile and explain the biggest gap in each.`

Then:

`Save the best one with the note Review this tonight.`

Finally:

`I applied to that role. Record it as applied.`

Show the tool calls and refresh the frontend so the write appears in the application pipeline.

## 3:30–4:00 — Close
State the complete data flow:

`Third-party API → Spark Bronze/Silver/Gold → Lakebase → vectors → Databricks App → MCP agent → persistent actions.`

End by showing the GitHub README requirement mapping and evidence.
