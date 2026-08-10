# Spark Pipeline

`jobs_spark_pipeline.py` is the required Spark data pipeline for the capstone.

It creates three Delta tables:

- `bronze_jobs`: normalized raw API feed plus ingestion metadata.
- `silver_jobs`: cleaned and deduplicated jobs with transparent quality and Data/AI relevance scores.
- `gold_jobs`: trusted Data/AI opportunities for low-latency serving.

The Gold table is synced into Lakebase with `scripts/create_synced_table.py`.
This separation deliberately keeps large-scale transformation in the lakehouse
and transactional application state in Lakebase.
