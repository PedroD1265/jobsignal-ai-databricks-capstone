# JobSignal AI Architecture

```mermaid
flowchart LR
    R[Remote OK API] --> B[Bronze Delta]
    A[Optional Adzuna API] --> B
    B -->|Spark cleaning| S[Silver Delta]
    S -->|quality + relevance + dedup| G[Gold Delta]
    G -->|Lakebase synced table| P[(Lakebase Postgres)]
    P --> E[MiniLM embeddings + pgvector HNSW]
    E --> W[Databricks App frontend]
    E --> M[FastMCP Databricks App]
    M --> AG[Databricks Agent / Playground]
    W --> O[(Operational tables)]
    AG -->|save / stage / note| O
```

## Why the architecture is split

- **Delta + Spark** is the data-engineering plane: ingestion, cleaning, deduplication, quality scoring, skill extraction, and curated Gold data.
- **Lakebase** is the low-latency serving and operational plane: synced Gold jobs plus mutable profiles, saves, application stages, notes, contacts, embeddings, and agent-action audit records.
- **pgvector** handles semantic retrieval of unstructured job descriptions.
- **FastMCP** turns retrieval and transactional career actions into standardized tools for an AI agent.

This division makes each required capstone technology solve a real problem instead of existing only to satisfy a checkbox.
