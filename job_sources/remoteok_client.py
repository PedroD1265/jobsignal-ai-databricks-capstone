"""Remote OK API client.

Remote OK currently exposes a public JSON feed at https://remoteok.com/api.
The first array element contains API terms; actual job records follow it.
This adapter returns normalized Python dicts and leaves data quality filtering
for the Spark Silver layer.
"""

from __future__ import annotations

import html
import re
from datetime import datetime, timezone
from typing import Any

import requests

REMOTEOK_API_URL = "https://remoteok.com/api"
USER_AGENT = "JobSignalAI-Capstone/1.0 (educational Databricks project)"


class RemoteOKError(RuntimeError):
    """Raised when the Remote OK source cannot be read or parsed."""


def _safe_int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _clean_html(raw: str | None) -> str:
    text = html.unescape(raw or "")
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n", text)
    return text.strip()


def fetch_jobs(timeout: int = 30) -> list[dict[str, Any]]:
    """Fetch and normalize the current Remote OK JSON feed.

    Returns:
        A list of job records. No filtering is applied here because noisy,
        incomplete and duplicate rows are intentionally handled in Spark.
    """
    try:
        response = requests.get(
            REMOTEOK_API_URL,
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
            timeout=timeout,
        )
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise RemoteOKError(f"Remote OK request failed: {exc}") from exc

    if not isinstance(payload, list):
        raise RemoteOKError("Remote OK returned an unexpected non-list payload")

    now = datetime.now(timezone.utc).isoformat()
    jobs: list[dict[str, Any]] = []

    for item in payload:
        if not isinstance(item, dict) or "legal" in item:
            continue

        job_id = str(item.get("id") or "").strip()
        if not job_id:
            continue

        jobs.append(
            {
                "job_id": f"remoteok:{job_id}",
                "source": "remoteok",
                "source_native_id": job_id,
                "source_url": str(item.get("url") or item.get("apply_url") or ""),
                "apply_url": str(item.get("apply_url") or item.get("url") or ""),
                "company": str(item.get("company") or "").strip(),
                "title": str(item.get("position") or "").strip(),
                "location": str(item.get("location") or "Remote").strip(),
                "salary_min": _safe_int(item.get("salary_min")),
                "salary_max": _safe_int(item.get("salary_max")),
                "tags": [str(tag).strip() for tag in (item.get("tags") or []) if str(tag).strip()],
                "description_html": str(item.get("description") or ""),
                "description_text": _clean_html(item.get("description")),
                "published_at": str(item.get("date") or ""),
                "ingested_at": now,
            }
        )

    return jobs
