from job_sources.remoteok_client import _clean_html


def test_clean_html_removes_markup_and_decodes_entities():
    value = _clean_html("<p>Python &amp; SQL</p><br><b>Remote</b>")
    assert "<" not in value
    assert "Python & SQL" in value
    assert "Remote" in value
