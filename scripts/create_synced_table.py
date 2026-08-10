"""Create a Lakebase synced table for the Spark Gold Delta table.

Run after pipelines/jobs_spark_pipeline.py. The script uses the documented
Lakebase Autoscaling synced-table API through the Databricks SDK.
"""

from __future__ import annotations

import os

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.postgres import (
    SyncedTable,
    SyncedTableSyncedTableSpec,
    SyncedTableSyncedTableSpecSyncedTableSchedulingPolicy,
)

SOURCE_TABLE = os.environ["JOBSIGNAL_SOURCE_TABLE"]
SYNCED_TABLE_ID = os.environ["JOBSIGNAL_SYNCED_TABLE_ID"]
LAKEBASE_BRANCH = os.getenv(
    "LAKEBASE_BRANCH",
    "projects/dataexpert-support-app/branches/production",
)
POSTGRES_DATABASE = os.getenv("PGDATABASE", "databricks_postgres")

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
