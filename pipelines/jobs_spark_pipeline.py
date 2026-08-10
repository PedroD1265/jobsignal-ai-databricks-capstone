# Databricks notebook source
"""JobSignal AI Spark pipeline: Remote OK -> Bronze -> Silver -> Gold.

Run this file as a Databricks notebook/source file from the repository root.
The pipeline intentionally keeps ingestion separate from transformation:

Bronze: raw normalized API records + ingestion metadata
Silver: cleaned text, deduplication, data-quality scoring, skill extraction
Gold: trusted job opportunities ready for application serving; Data/AI relevance is retained as a ranking signal

The Gold Delta table is designed to be synced to Lakebase with a Databricks
Lakebase synced table (reverse ETL). See scripts/create_synced_table.py.
"""

from __future__ import annotations

import os
import sys
import uuid

# Databricks Git folders execute this notebook from the pipelines/ directory.
# Add the repository root so sibling source adapters import reliably.
_repo_root = os.path.abspath(os.path.join(os.getcwd(), "..")) if os.path.basename(os.getcwd()) == "pipelines" else os.getcwd()
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

from pyspark.sql import DataFrame, functions as F, types as T

from job_sources.remoteok_client import fetch_jobs as fetch_remoteok_jobs

try:
    from job_sources.adzuna_client import fetch_jobs as fetch_adzuna_jobs, is_configured as adzuna_is_configured
except Exception:
    fetch_adzuna_jobs = None
    adzuna_is_configured = lambda: False

PIPELINE_RUN_ID = str(uuid.uuid4())
TARGET_SCHEMA = os.getenv("JOBSIGNAL_UC_SCHEMA", "jobsignal_capstone")
CURRENT_CATALOG = spark.sql("SELECT current_catalog() AS catalog").first()["catalog"]
TARGET_CATALOG = os.getenv("JOBSIGNAL_UC_CATALOG", CURRENT_CATALOG)

BRONZE_TABLE = f"{TARGET_CATALOG}.{TARGET_SCHEMA}.bronze_jobs"
SILVER_TABLE = f"{TARGET_CATALOG}.{TARGET_SCHEMA}.silver_jobs"
GOLD_TABLE = f"{TARGET_CATALOG}.{TARGET_SCHEMA}.gold_jobs"

DATA_AI_TITLE_REGEX = (
    r"(?i)(data engineer|analytics engineer|data platform|data scientist|"
    r"machine learning|ml engineer|ai engineer|artificial intelligence|"
    r"business intelligence|bi engineer|etl engineer|database engineer|"
    r"data architect|data analyst|analytics developer)"
)

PLACEHOLDER_REGEX = (
    r"(?i)(your job description here|job title$|how apply$|lorem ipsum|"
    r"career at|sorry, no results|classic get a job)"
)

SKILL_PATTERNS = {
    "python": r"(?i)\bpython\b",
    "sql": r"(?i)\bsql\b",
    "spark": r"(?i)\b(apache\s+spark|pyspark|spark)\b",
    "databricks": r"(?i)\bdatabricks\b",
    "airflow": r"(?i)\bairflow\b",
    "dbt": r"(?i)\bdbt\b",
    "kafka": r"(?i)\bkafka\b",
    "aws": r"(?i)\b(aws|amazon web services)\b",
    "azure": r"(?i)\b(azure|microsoft azure)\b",
    "gcp": r"(?i)\b(gcp|google cloud)\b",
    "snowflake": r"(?i)\bsnowflake\b",
    "postgres": r"(?i)\b(postgres|postgresql)\b",
    "docker": r"(?i)\bdocker\b",
    "kubernetes": r"(?i)\b(kubernetes|k8s)\b",
    "terraform": r"(?i)\bterraform\b",
    "mlflow": r"(?i)\bmlflow\b",
    "delta lake": r"(?i)\bdelta lake\b",
}

SCHEMA = T.StructType(
    [
        T.StructField("job_id", T.StringType(), False),
        T.StructField("source", T.StringType(), False),
        T.StructField("source_native_id", T.StringType(), True),
        T.StructField("source_url", T.StringType(), True),
        T.StructField("apply_url", T.StringType(), True),
        T.StructField("company", T.StringType(), True),
        T.StructField("title", T.StringType(), True),
        T.StructField("location", T.StringType(), True),
        T.StructField("salary_min", T.LongType(), True),
        T.StructField("salary_max", T.LongType(), True),
        T.StructField("tags", T.ArrayType(T.StringType()), True),
        T.StructField("description_html", T.StringType(), True),
        T.StructField("description_text", T.StringType(), True),
        T.StructField("published_at", T.StringType(), True),
        T.StructField("ingested_at", T.StringType(), True),
    ]
)


def fetch_sources() -> list[dict]:
    rows = fetch_remoteok_jobs()

    # Adzuna is intentionally optional so the required capstone path has no
    # API-key blocker. If secrets are configured, it becomes a second source.
    if fetch_adzuna_jobs and adzuna_is_configured():
        rows.extend(fetch_adzuna_jobs(query="data engineer"))
        rows.extend(fetch_adzuna_jobs(query="analytics engineer"))
        rows.extend(fetch_adzuna_jobs(query="machine learning engineer"))

    return rows


def build_bronze(rows: list[dict]) -> DataFrame:
    df = spark.createDataFrame(rows, schema=SCHEMA)
    return (
        df.withColumn("pipeline_run_id", F.lit(PIPELINE_RUN_ID))
        .withColumn("ingested_at_ts", F.to_timestamp("ingested_at"))
        .withColumn("published_at_ts", F.to_timestamp("published_at"))
        .drop("ingested_at", "published_at")
    )


def build_silver(bronze: DataFrame) -> DataFrame:
    text_blob = F.lower(
        F.concat_ws(
            " ",
            F.coalesce(F.col("title"), F.lit("")),
            F.coalesce(F.col("company"), F.lit("")),
            F.coalesce(F.col("location"), F.lit("")),
            F.coalesce(F.col("description_text"), F.lit("")),
            F.concat_ws(" ", F.col("tags")),
        )
    )

    # A transparent quality score deliberately penalizes the kinds of noisy
    # feed records that make raw job APIs unreliable for an AI assistant.
    score = F.lit(100)
    score = score - F.when(F.length(F.trim(F.col("description_text"))) < 180, 40).otherwise(0)
    score = score - F.when(F.col("title").rlike(PLACEHOLDER_REGEX), 35).otherwise(0)
    score = score - F.when(F.col("description_text").rlike(PLACEHOLDER_REGEX), 25).otherwise(0)
    score = score - F.when(F.length(F.trim(F.col("title"))) < 4, 20).otherwise(0)
    score = score - F.when(F.length(F.trim(F.col("company"))) < 2, 20).otherwise(0)
    score = score - F.when(~F.col("source_url").rlike(r"(?i)^https?://"), 10).otherwise(0)

    relevance = F.lit(0)
    relevance = relevance + F.when(F.col("title").rlike(DATA_AI_TITLE_REGEX), 55).otherwise(0)
    relevance = relevance + F.when(text_blob.rlike(r"(?i)\bpython\b"), 10).otherwise(0)
    relevance = relevance + F.when(text_blob.rlike(r"(?i)\bsql\b"), 10).otherwise(0)
    relevance = relevance + F.when(text_blob.rlike(r"(?i)\b(spark|databricks)\b"), 15).otherwise(0)
    relevance = relevance + F.when(text_blob.rlike(r"(?i)\b(data pipeline|etl|elt|lakehouse)\b"), 10).otherwise(0)

    skill_exprs = [F.when(text_blob.rlike(pattern), F.lit(skill)) for skill, pattern in SKILL_PATTERNS.items()]
    extracted_skills = F.array_compact(F.array(*skill_exprs))

    quality_flags = F.array_compact(
        F.array(
            F.when(F.length(F.trim(F.col("description_text"))) < 180, F.lit("short_description")),
            F.when(F.col("title").rlike(PLACEHOLDER_REGEX), F.lit("placeholder_title")),
            F.when(F.col("description_text").rlike(PLACEHOLDER_REGEX), F.lit("placeholder_description")),
            F.when(~F.col("source_url").rlike(r"(?i)^https?://"), F.lit("missing_source_url")),
        )
    )

    normalized_company = F.lower(F.regexp_replace(F.trim(F.col("company")), r"\s+", " "))
    normalized_title = F.lower(F.regexp_replace(F.trim(F.col("title")), r"\s+", " "))
    normalized_location = F.lower(F.regexp_replace(F.trim(F.col("location")), r"\s+", " "))

    silver = (
        bronze.withColumn("description_text", F.regexp_replace(F.col("description_text"), r"\s+", " "))
        .withColumn("quality_score", F.greatest(F.lit(0), score).cast("int"))
        .withColumn("relevance_score", F.least(F.lit(100), relevance).cast("int"))
        .withColumn("quality_flags", quality_flags)
        .withColumn("extracted_skills", extracted_skills)
        .withColumn(
            "dedup_key",
            F.sha2(F.concat_ws("||", normalized_company, normalized_title, normalized_location), 256),
        )
        .withColumn("is_high_quality", F.col("quality_score") >= 65)
        .withColumn("is_data_ai_role", F.col("relevance_score") >= 55)
    )

    # Prefer the newest/highest-quality record for a duplicate job identity.
    from pyspark.sql.window import Window

    dedup_window = Window.partitionBy("dedup_key").orderBy(
        F.col("quality_score").desc(),
        F.col("published_at_ts").desc_nulls_last(),
    )
    return (
        silver.withColumn("dedup_rank", F.row_number().over(dedup_window))
        .filter(F.col("dedup_rank") == 1)
        .drop("dedup_rank")
    )


def build_gold(silver: DataFrame) -> DataFrame:
    return (
        silver.filter(F.col("is_high_quality"))
        .select(
            "job_id",
            "source",
            "source_native_id",
            "source_url",
            "apply_url",
            "company",
            "title",
            "location",
            "salary_min",
            "salary_max",
            "tags",
            "description_text",
            "published_at_ts",
            "ingested_at_ts",
            "quality_score",
            "relevance_score",
            "is_data_ai_role",
            "quality_flags",
            "extracted_skills",
            "dedup_key",
            "pipeline_run_id",
        )
        .withColumnRenamed("published_at_ts", "published_at")
        .withColumnRenamed("ingested_at_ts", "ingested_at")
    )


def write_delta(df: DataFrame, table_name: str) -> None:
    (
        df.write.format("delta")
        .mode("overwrite")
        .option("overwriteSchema", "true")
        .saveAsTable(table_name)
    )


spark.sql(f"CREATE SCHEMA IF NOT EXISTS {TARGET_CATALOG}.{TARGET_SCHEMA}")

source_rows = fetch_sources()
if not source_rows:
    raise RuntimeError("No job records were returned by configured sources")

bronze_df = build_bronze(source_rows)
silver_df = build_silver(bronze_df)
gold_df = build_gold(silver_df)

write_delta(bronze_df, BRONZE_TABLE)
write_delta(silver_df, SILVER_TABLE)
write_delta(gold_df, GOLD_TABLE)

metrics = {
    "pipeline_run_id": PIPELINE_RUN_ID,
    "bronze_rows": bronze_df.count(),
    "silver_rows": silver_df.count(),
    "gold_rows": gold_df.count(),
    "low_quality_rows": silver_df.filter(~F.col("is_high_quality")).count(),
    "data_ai_rows": silver_df.filter(F.col("is_data_ai_role")).count(),
    "gold_table": GOLD_TABLE,
}
print(metrics)

# Required when switching the synced table to TRIGGERED or CONTINUOUS mode.
spark.sql(
    f"ALTER TABLE {GOLD_TABLE} SET TBLPROPERTIES (delta.enableChangeDataFeed = true)"
)
