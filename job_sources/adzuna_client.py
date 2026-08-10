"""Optional Adzuna source adapter.

The capstone works without Adzuna. If ADZUNA_APP_ID and ADZUNA_APP_KEY are
configured as Databricks secrets/environment variables, this adapter can be
added as a second source for multi-source ingestion.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

import requests

API_ROOT = "https://api.adzuna.com/v1/api/jobs"


class AdzunaError(RuntimeError):
    pass


def _safe_int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def is_configured() -> bool:
    return bool(os.getenv("ADZUNA_APP_ID") and os.getenv("ADZUNA_APP_KEY"))


def fetch_jobs(
    country: str = "us",
    query: str = "data engineer",
    where: str = "",
    page: int = 1,
    results_per_page: int = 50,
    timeout: int = 30,
) -> list[dict[str, Any]]:
    app_id = os.getenv("ADZUNA_APP_ID")
    app_key = os.getenv("ADZUNA_APP_KEY")
    if not app_id or not app_key:
        raise AdzunaError("ADZUNA_APP_ID and ADZUNA_APP_KEY are not configured")

    url = f"{API_ROOT}/{country}/search/{page}"
    params = {
        "app_id": app_id,
        "app_key": app_key,
        "results_per_page": min(max(results_per_page, 1), 50),
        "what": query,
        "content-type": "application/json",
    }
    if where:
        params["where"] = where

    try:
        response = requests.get(url, params=params, timeout=timeout)
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise AdzunaError(f"Adzuna request failed: {exc}") from exc

    now = datetime.now(timezone.utc).isoformat()
    rows: list[dict[str, Any]] = []
    for item in payload.get("results", []):
        native_id = str(item.get("id") or "").strip()
        if not native_id:
            continue
        location = ((item.get("location") or {}).get("display_name") or "").strip()
        company = ((item.get("company") or {}).get("display_name") or "").strip()
        description = str(item.get("description") or "").strip()
        rows.append(
            {
                "job_id": f"adzuna:{native_id}",
                "source": "adzuna",
                "source_native_id": native_id,
                "source_url": str(item.get("redirect_url") or ""),
                "apply_url": str(item.get("redirect_url") or ""),
                "company": company,
                "title": str(item.get("title") or "").strip(),
                "location": location,
                "salary_min": _safe_int(item.get("salary_min")),
                "salary_max": _safe_int(item.get("salary_max")),
                "tags": [],
                "description_html": description,
                "description_text": description,
                "published_at": str(item.get("created") or ""),
                "ingested_at": now,
            }
        )
    return rows
