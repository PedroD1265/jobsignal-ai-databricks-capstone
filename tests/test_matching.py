from matching import dedupe_and_rank, score_job


def test_score_job_rewards_skill_overlap():
    profile = {"skills": ["Python", "SQL", "Spark"]}
    strong = score_job(
        {"job_id": "1", "similarity": 0.8, "quality_score": 90, "extracted_skills": ["python", "sql", "spark"]},
        profile,
    )
    weak = score_job(
        {"job_id": "2", "similarity": 0.8, "quality_score": 90, "extracted_skills": ["terraform", "kubernetes"]},
        profile,
    )
    assert strong["match_score"] > weak["match_score"]
    assert strong["matched_skills"] == ["python", "spark", "sql"]


def test_dedupe_uses_best_chunk_then_ranks():
    rows = [
        {"job_id": "a", "similarity": 0.50, "quality_score": 90, "extracted_skills": ["python"]},
        {"job_id": "a", "similarity": 0.82, "quality_score": 90, "extracted_skills": ["python"]},
        {"job_id": "b", "similarity": 0.70, "quality_score": 80, "extracted_skills": ["terraform"]},
    ]
    ranked = dedupe_and_rank(rows, {"skills": ["python"]}, top_k=5)
    assert len(ranked) == 2
    assert ranked[0]["job_id"] == "a"
    assert ranked[0]["similarity"] == 0.82
