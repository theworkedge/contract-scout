"""Tests for SAM.gov URL construction in contract_scout.py."""

import pytest

from contract_scout import (
    NAICS_CODES,
    POST_TYPES,
    RESULT_LIMIT,
    SAM_SEARCH_URL,
    build_sam_url,
)

_FROM = "03/09/2026"
_TO = "03/11/2026"
_KEY = "SAM=1b873a38-593e-4acb-b287-96875e1da53d"


def _url():
    return build_sam_url(_KEY, _FROM, _TO)


# ---------------------------------------------------------------------------
# Base structure
# ---------------------------------------------------------------------------


def test_url_starts_with_base():
    assert _url().startswith(SAM_SEARCH_URL + "?")


def test_url_contains_all_required_params():
    url = _url()
    for param in ("api_key=", "postedFrom=", "postedTo=", "ncode=", "ptype=", "limit="):
        assert param in url, f"Missing param prefix: {param}"


# ---------------------------------------------------------------------------
# No percent-encoding of special characters that SAM.gov requires unencoded
# ---------------------------------------------------------------------------


def test_api_key_equals_not_encoded():
    """= signs in the API key must not become %3D."""
    url = _url()
    assert "%3D" not in url, "= in api_key was percent-encoded (%3D)"
    assert f"api_key={_KEY}" in url


def test_date_slashes_not_encoded():
    """Date slashes must not become %2F."""
    url = _url()
    assert "%2F" not in url, "/ in date was percent-encoded (%2F)"
    assert f"postedFrom={_FROM}" in url
    assert f"postedTo={_TO}" in url


def test_naics_commas_not_encoded():
    """NAICS code commas must not become %2C."""
    url = _url()
    assert "%2C" not in url, ", was percent-encoded (%2C)"
    assert f"ncode={NAICS_CODES}" in url


def test_ptype_commas_not_encoded():
    """ptype commas must not become %2C."""
    url = _url()
    assert f"ptype={POST_TYPES}" in url


def test_limit_value():
    assert f"limit={RESULT_LIMIT}" in _url()


# ---------------------------------------------------------------------------
# Different API key formats
# ---------------------------------------------------------------------------


def test_plain_api_key_no_equals():
    """Plain UUID key (no = sign) should still work without encoding artifacts."""
    url = build_sam_url("abc123", _FROM, _TO)
    assert "api_key=abc123" in url
    assert "%3D" not in url


def test_no_double_question_mark():
    url = _url()
    assert url.count("?") == 1
