"""JobSignal AI Databricks App.

A trust-aware Data & AI job hunting copilot frontend backed by Lakebase.
The analytical job feed comes from a Spark Gold Delta table synced into
Lakebase; application state remains transactional in Lakebase.
"""

from __future__ import annotations

import logging
import os

from flask import Flask, jsonify, render_template, request

import lakebase
from embeddings import MODEL_NAME, embed_pending_jobs, embed_query
from matching import dedupe_and_rank

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("jobsignal-ai")

app = Flask(__name__)


def _json_safe(value):
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def _serialize_row(row: dict) -> dict:
    return {key: _json_safe(value) for key, value in row.items()}


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/healthz")
def healthz():
    return jsonify(
        {
            "status": "ok",
            "service": "jobsignal-ai",
            "embedding_model": MODEL_NAME,
            "job_postings_table": os.getenv(
                "JOB_POSTINGS_TABLE", "jobsignal_capstone.gold_jobs_synced"
            ),
        }
    )


@app.errorhandler(Exception)
def handle_exception(err):
    logger.exception("Unhandled exception")
    status_code = getattr(err, "code", 500)
    if not isinstance(status_code, int):
        status_code = 500
    return jsonify({"error": str(err)}), status_code


@app.get("/api/stats")
def api_stats():
    profile_id = max(1, int(request.args.get("profile_id", 1)))
    return jsonify(_serialize_row(lakebase.stats(profile_id)))


@app.get("/api/profile")
def api_get_profile():
    profile_id = max(1, int(request.args.get("profile_id", 1)))
    profile = lakebase.get_profile(profile_id)
    return jsonify(_serialize_row(profile) if profile else {})


@app.post("/api/profile")
def api_save_profile():
    body = request.get_json(silent=True) or {}
    profile_id = body.get("profile_id")
    if profile_id is not None:
        profile_id = int(profile_id)
    profile = lakebase.upsert_profile(body, profile_id=profile_id)
    return jsonify(_serialize_row(profile)), 201


@app.post("/api/profile/demo")
def api_demo_profile():
    return jsonify(_serialize_row(lakebase.seed_demo_profile())), 201


@app.post("/api/admin/embed-jobs")
def api_embed_jobs():
    body = request.get_json(silent=True) or {}
    try:
        limit = max(1, min(int(body.get("limit", 500)), 2000))
    except (TypeError, ValueError):
        return jsonify({"error": "limit must be an integer"}), 400
    return jsonify(embed_pending_jobs(limit=limit))


@app.post("/api/jobs/search")
def api_search_jobs():
    body = request.get_json(silent=True) or {}
    query = str(body.get("query") or "").strip()
    if not query:
        return jsonify({"error": "query is required"}), 400

    try:
        top_k = max(1, min(int(body.get("top_k", 8)), 20))
        profile_id = max(1, int(body.get("profile_id", 1)))
    except (TypeError, ValueError):
        return jsonify({"error": "top_k and profile_id must be integers"}), 400

    profile = lakebase.get_profile(profile_id)
    query_vector = embed_query(query)
    rows = lakebase.vector_search(query_vector, top_k=top_k)
    results = dedupe_and_rank(rows, profile, top_k)
    return jsonify(
        {
            "query": query,
            "profile_id": profile_id,
            "model": MODEL_NAME,
            "results": [_serialize_row(row) for row in results],
        }
    )


@app.get("/api/jobs/<path:job_id>")
def api_job_detail(job_id: str):
    job = lakebase.get_job(job_id)
    if not job:
        return jsonify({"error": "job not found"}), 404
    return jsonify(_serialize_row(job))


@app.post("/api/jobs/<path:job_id>/save")
def api_save_job(job_id: str):
    body = request.get_json(silent=True) or {}
    profile_id = max(1, int(body.get("profile_id", 1)))
    result = lakebase.save_job(profile_id, job_id, body.get("notes"))
    return jsonify(result), 201


@app.get("/api/applications")
def api_applications():
    profile_id = max(1, int(request.args.get("profile_id", 1)))
    return jsonify([_serialize_row(row) for row in lakebase.list_applications(profile_id)])


@app.post("/api/applications/<path:job_id>/stage")
def api_application_stage(job_id: str):
    body = request.get_json(silent=True) or {}
    profile_id = max(1, int(body.get("profile_id", 1)))
    stage = str(body.get("stage") or "").strip().lower()
    if not stage:
        return jsonify({"error": "stage is required"}), 400
    result = lakebase.set_application_stage(
        profile_id,
        job_id,
        stage,
        follow_up_at=body.get("follow_up_at"),
    )
    return jsonify(_serialize_row(result)), 201


@app.post("/api/applications/<path:job_id>/notes")
def api_application_note(job_id: str):
    body = request.get_json(silent=True) or {}
    profile_id = max(1, int(body.get("profile_id", 1)))
    note = str(body.get("note") or "").strip()
    if not note:
        return jsonify({"error": "note is required"}), 400
    result = lakebase.add_interview_note(profile_id, job_id, note)
    return jsonify(_serialize_row(result)), 201


@app.get("/api/applications/stale")
def api_stale_applications():
    profile_id = max(1, int(request.args.get("profile_id", 1)))
    days = max(1, min(int(request.args.get("days", 7)), 90))
    rows = lakebase.stale_applications(profile_id, days)
    return jsonify([_serialize_row(row) for row in rows])


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    app.run(host="0.0.0.0", port=port)
