from job_sources.remoteok_client import (
    RETRYABLE_STATUS_CODES,
    _build_session,
    _clean_html,
)


def test_clean_html_removes_markup_and_decodes_entities():
    value = _clean_html("<p>Python &amp; SQL</p><br><b>Remote</b>")
    assert "<" not in value
    assert "Python & SQL" in value
    assert "Remote" in value


def test_remoteok_session_has_retry_backoff_and_rate_limit_handling():
    session = _build_session()
    retry = session.get_adapter("https://").max_retries

    assert retry.total == 3
    assert retry.backoff_factor > 0
    assert 429 in retry.status_forcelist
    assert set(RETRYABLE_STATUS_CODES).issubset(set(retry.status_forcelist))
    assert "GET" in retry.allowed_methods
