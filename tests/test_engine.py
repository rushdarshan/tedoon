import json
import pytest

from progressive_disclosure.engine import (
    _parse_response,
    _fallback_response,
    get_missing_fields,
)
from progressive_disclosure.fields import TAB_FIELDS


def test_parse_response_filters_hallucinated_keys():
    field_defs = TAB_FIELDS["PD"]
    response = json.dumps({
        "filled_fields": {"sector": "Manufacturing", "fake_key": "evil", "annual_turnover": 5000000},
        "missing_fields": ["credit_score", "ghost_field"],
        "next_question": "What is your credit score?",
        "summary": "MSME in manufacturing with ₹50L turnover.",
    })
    result = _parse_response(response, field_defs)
    assert "fake_key" not in result["filled_fields"]
    assert "ghost_field" not in result["missing_fields"]
    assert result["filled_fields"]["sector"] == "Manufacturing"
    assert result["filled_fields"]["annual_turnover"] == 5000000
    assert "credit_score" in result["missing_fields"]


def test_parse_response_casts_types():
    field_defs = TAB_FIELDS["PD"]
    response = json.dumps({
        "filled_fields": {"annual_turnover": "5000000", "years_in_operation": "8", "sector": "Manufacturing"},
        "missing_fields": [],
        "next_question": "",
        "summary": "Summary.",
    })
    result = _parse_response(response, field_defs)
    assert isinstance(result["filled_fields"]["annual_turnover"], float)
    assert isinstance(result["filled_fields"]["years_in_operation"], int)


def test_parse_response_handles_type_mismatch():
    field_defs = TAB_FIELDS["PD"]
    response = json.dumps({
        "filled_fields": {"annual_turnover": "not-a-number", "sector": "Textiles"},
        "missing_fields": [],
        "next_question": "",
        "summary": "",
    })
    result = _parse_response(response, field_defs)
    assert result["filled_fields"]["annual_turnover"] == ""
    assert result["filled_fields"]["sector"] == "Textiles"


def test_fallback_response_returns_first_required():
    field_defs = TAB_FIELDS["PD"]
    result = _fallback_response(field_defs)
    assert result["filled_fields"] == {}
    assert "sector" in result["missing_fields"]
    assert "credit_score" in result["missing_fields"]
    assert "Business Sector" in result["next_question"]


def test_get_missing_fields_skips_filled():
    form_state = {"sector": "Manufacturing", "annual_turnover": 5000000}
    field_reveal = {"sector": "FILLED", "annual_turnover": "FILLED"}
    missing = get_missing_fields(form_state, field_reveal, "PD")
    assert "sector" not in missing
    assert "annual_turnover" not in missing
    assert "credit_score" in missing


def test_get_missing_fields_includes_unrevealed_required():
    form_state = {}
    field_reveal = {}
    missing = get_missing_fields(form_state, field_reveal, "PD")
    for f in TAB_FIELDS["PD"]:
        if f["required"]:
            assert f["key"] in missing
