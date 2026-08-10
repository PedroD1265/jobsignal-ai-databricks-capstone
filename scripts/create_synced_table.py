"""Create a Lakebase synced table for the Spark Gold Delta table.

Run this Databricks source notebook after pipelines/jobs_spark_pipeline.py.
The fast path auto-detects the current Unity Catalog catalog, so no environment
variables are required in the bootcamp workspace. Environment variables remain
available as overrides for portability.
"""

from __future__ import annotations

import os

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.postgres import (
    SyncedTable,
    SyncedTableSyncedTableSpec,
    SyncedTableSyncedTableSpecSyncedTableSchedulingPolicy,
)

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

print(
    {
        "source_table": SOURCE_TABLE,
        "synced_table_id": SYNCED_TABLE_ID,
        "lakebase_branch": LAKEBASE_BRANCH,
        "postgres_database": POSTGRES_DATABASE,
    }
)

w = WorkspaceClient()

result = w.postgres.create_synced_table(
    synced_table=SyncedTable(
        spec=SyncedTableSyncedTableSpec(
            source_table_full_name=SOURCE_TABLE,
            branch=LAKEBASE_BRANCH,
            primary_key_columns=["job_id"],
            scheduling_policy=(
                SyncedTableSyncedTableSpecSyncedTableSchedulingPolicy.SNAPSHOT
            ),
            postgres_database=POSTGRES_DATABASE,
            create_database_objects_if_missing=True,
        )
    ),
    synced_table_id=SYNCED_TABLE_ID,
).wait()

print(f"Synced table created: {result.name}")
