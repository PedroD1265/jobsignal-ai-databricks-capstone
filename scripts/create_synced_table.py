# Databricks notebook source
"""Create the JobSignal Lakebase synced table using the generic Databricks REST client.

This helper avoids importing ``databricks.sdk.service.postgres`` so it also works
in notebook environments whose preinstalled SDK is older than the generated
Postgres service module. The UI path remains an equally valid fallback.
"""

from __future__ import annotations

import os
import time
from urllib.parse import quote

from databricks.sdk import WorkspaceClient

CURRENT_CATALOG = spark.sql("SELECT current_catalog() AS catalog").first()["catalog"]
SOURCE_TABLE = os.getenv(
    "JOBSIGNAL_SOURCE_TABLE",
    f"{CURRENT_CATALOG}.jobsignal_capstone.gold_jobs",
)
SYNCED_TABLE_ID = os.getenv(
    "JOBSIGNAL_SYNCED_TABLE_ID",
    f"{CURRENT_CATALOG}.jobsignal_capstone.gold_jobs_synced",
)
LAKEBASE_BRANCH = os.getenv(
    "LAKEBASE_BRANCH",
    "projects/dataexpert-support-app/branches/production",
)
POSTGRES_DATABASE = os.getenv("PGDATABASE", "databricks_postgres")

w = WorkspaceClient()

print({
    "source_table": SOURCE_TABLE,
    "synced_table_id": SYNCED_TABLE_ID,
    "lakebase_branch": LAKEBASE_BRANCH,
    "postgres_database": POSTGRES_DATABASE,
})

try:
    existing = w.api_client.do(
        "GET",
        f"/api/2.0/postgres/synced_tables/{quote(SYNCED_TABLE_ID, safe='')}",
    )
    print("Synced table already exists.")
    print(existing)
except Exception:
    operation = w.api_client.do(
        "POST",
        "/api/2.0/postgres/synced_tables",
        query={"synced_table_id": SYNCED_TABLE_ID},
        body={
            "spec": {
                "source_table_full_name": SOURCE_TABLE,
                "branch": LAKEBASE_BRANCH,
                "primary_key_columns": ["job_id"],
                "scheduling_policy": "SNAPSHOT",
                "postgres_database": POSTGRES_DATABASE,
                "create_database_objects_if_missing": True,
            }
        },
    )
    print("Create operation submitted:", operation)
    for _ in range(30):
        time.sleep(2)
        try:
            current = w.api_client.do(
                "GET",
                f"/api/2.0/postgres/synced_tables/{quote(SYNCED_TABLE_ID, safe='')}",
            )
            state = ((current.get("status") or {}).get("detailed_state") or "").upper()
            print("status:", state or current)
            if "ONLINE" in state:
                break
        except Exception as exc:
            print("Waiting for synced table:", exc)

print(f"Synced table target: {SYNCED_TABLE_ID}")
