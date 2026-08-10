"""Remote OK API client.

Remote OK exposes a public JSON feed at https://remoteok.com/api.
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
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

REMOTEOK_API_URL = "https://remoteok.com/api"
USER_AGENT = "JobSignalAI-Capstone/1.0 (educational Databricks project)"
RETRYABLE_STATUS_CODES = (429, 500, 502, 503, 504)


class RemoteOKError(RuntimeError):
    """Raised when the Remote OK source cannot be read or parsed."""


def _build_session() -> requests.Session:
    """Create a resilient HTTP session for transient API failures.

    Retries GET requests on rate limiting and common 5xx responses, uses
    exponential backoff, and honors Retry-After when the API supplies it.
    """
    retry = Retry(
        total=3,
        connect=3,
        read=3,
        status=3,
        backoff_factor=0.75,
        status_forcelist=RETRYABLE_STATUS_CODES,
        allowed_methods=frozenset({"GET"}),
        respect_retry_after_header=True,
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session = requests.Session()
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update(
        {
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
        }
    )
    return session


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

    The request retries transient 429/5xx responses with exponential backoff.
    No business filtering is applied here because noisy, incomplete and
    duplicate rows are intentionally handled in the Spark Silver layer.
    """
    try:
        with _build_session() as session:
            response = session.get(REMOTEOK_API_URL, timeout=timeout)
            response.raise_for_status()
            payload = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise RemoteOKError(f"Remote OK request failed after retries: {exc}") from exc

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

        tags = item.get("tags")
        if not isinstance(tags, list):
            tags = []

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
                "tags": [str(tag).strip() for tag in tags if str(tag).strip()],
                "description_html": str(item.get("description") or ""),
                "description_text": _clean_html(item.get("description")),
                "published_at": str(item.get("date") or ""),
                "ingested_at": now,
            }
        )

    return jobs
