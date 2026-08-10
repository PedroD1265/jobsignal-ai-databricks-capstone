"""Explainable hybrid job matching: semantic similarity + skills + data quality."""

from __future__ import annotations


def _norm(value: str) -> str:
    return " ".join((value or "").lower().strip().split())


def score_job(job: dict, profile: dict | None) -> dict:
    similarity = max(0.0, min(float(job.get("similarity") or 0.0), 1.0))
    quality = max(0.0, min(float(job.get("quality_score") or 0.0) / 100.0, 1.0))

    profile_skills = [_norm(x) for x in ((profile or {}).get("skills") or []) if _norm(x)]
    job_skills_raw = job.get("extracted_skills") or []
    if isinstance(job_skills_raw, str):
        job_skills_raw = [job_skills_raw]
    job_skills = [_norm(x) for x in job_skills_raw if _norm(x)]

    profile_set = set(profile_skills)
    job_set = set(job_skills)
    matched = sorted(profile_set & job_set)
    missing = sorted(job_set - profile_set)
    skill_overlap = (len(matched) / len(job_set)) if job_set else 0.5

    if profile_skills:
        match_score = 0.65 * similarity + 0.25 * skill_overlap + 0.10 * quality
    else:
        match_score = 0.85 * similarity + 0.15 * quality

    return {
        **job,
        "similarity": round(similarity, 4),
        "skill_overlap": round(skill_overlap, 4),
        "match_score": round(match_score * 100, 1),
        "matched_skills": matched,
        "missing_skills": missing,
        "match_explanation": {
            "semantic_weight": 65 if profile_skills else 85,
            "skills_weight": 25 if profile_skills else 0,
            "quality_weight": 10 if profile_skills else 15,
        },
    }


def dedupe_and_rank(rows: list[dict], profile: dict | None, top_k: int) -> list[dict]:
    best: dict[str, dict] = {}
    for row in rows:
        job_id = row["job_id"]
        similarity = float(row.get("similarity") or 0.0)
        if job_id not in best or similarity > float(best[job_id].get("similarity") or 0.0):
            best[job_id] = row
    scored = [score_job(job, profile) for job in best.values()]
    scored.sort(key=lambda x: (x["match_score"], x.get("quality_score") or 0), reverse=True)
    return scored[:top_k]
