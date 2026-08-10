"""Stateless FastMCP server for the JobSignal AI capstone."""

from fastapi import FastAPI
from fastmcp import FastMCP

import job_broker

mcp_server = FastMCP(name="mcp-jobsignal-ai")


@mcp_server.tool()
def search_matching_jobs(query: str, profile_id: int = 1, top_k: int = 5) -> list[dict]:
    """Search trusted Data/AI jobs using semantic similarity and profile skills.

    Args:
        query: Natural-language job preference or constraint.
        profile_id: Lakebase candidate profile to score against.
        top_k: Number of ranked jobs to return, from 1 to 10.

    Returns:
        Ranked job dictionaries including match score, source URL, matched skills,
        missing skills, quality score and a concise description preview.
    """
    return job_broker.search_jobs(query, profile_id=profile_id, top_k=top_k)


@mcp_server.tool()
def get_job_details(job_id: str) -> dict:
    """Return the authoritative synced job record for a job ID.

    Args:
        job_id: Stable source-prefixed identifier such as remoteok:12345.

    Returns:
        Full job metadata and source/apply URLs from the Lakebase serving table.
    """
    return job_broker.get_job_details(job_id)


@mcp_server.tool()
def save_job(job_id: str, profile_id: int = 1, notes: str = "") -> dict:
    """Persist a job to the user's saved list in Lakebase.

    Use only when the user explicitly asks to save/bookmark a job.
    This does not submit an external job application.
    """
    return job_broker.save_job(profile_id, job_id, notes)


@mcp_server.tool()
def move_application(
    job_id: str,
    stage: str,
    profile_id: int = 1,
    follow_up_at: str | None = None,
) -> dict:
    """Create or move an application tracker entry to a pipeline stage.

    Args:
        job_id: Stable job identifier.
        stage: saved, applied, interviewing, rejected, offer, or withdrawn.
        profile_id: Candidate profile.
        follow_up_at: Optional ISO timestamp for a follow-up reminder.

    Returns:
        The persisted Lakebase application record.

    This updates the local tracker only; it never claims to apply externally.
    """
    return job_broker.move_application(profile_id, job_id, stage, follow_up_at)


@mcp_server.tool()
def add_interview_note(job_id: str, note: str, profile_id: int = 1) -> dict:
    """Persist an interview or recruiter note for a tracked application."""
    return job_broker.add_interview_note(profile_id, job_id, note)


@mcp_server.tool()
def get_stale_applications(profile_id: int = 1, days: int = 7) -> list[dict]:
    """Find active applications that have not been updated recently.

    Args:
        profile_id: Candidate profile.
        days: Minimum age in days since the last update.
    """
    return job_broker.get_stale_applications(profile_id, days)


# Databricks' current MCP template recommends stateless HTTP so requests do not
# depend on sticky sessions when Apps scale horizontally.
mcp_app = mcp_server.http_app(stateless_http=True)

api_app = FastAPI(
    title="JobSignal AI MCP",
    description="MCP tools for trusted job retrieval and application actions",
    version="1.0.0",
    lifespan=mcp_app.lifespan,
)


@api_app.get("/", include_in_schema=False)
async def root():
    return {"status": "healthy", "service": "mcp-jobsignal-ai", "mcp": "/mcp"}


combined_app = FastAPI(
    title="JobSignal AI MCP Server",
    routes=[*mcp_app.routes, *api_app.routes],
    lifespan=mcp_app.lifespan,
)
