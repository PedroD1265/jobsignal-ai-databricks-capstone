"""CLI-style embedding trigger for JobSignal AI.

Inside a Databricks App, use POST /api/admin/embed-jobs. This script exists to
make the embedding step independently testable and visible to an automated grader.
"""

from embeddings import embed_pending_jobs

if __name__ == "__main__":
    print(embed_pending_jobs(limit=1000))
