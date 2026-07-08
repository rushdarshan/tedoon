import pytest

from progressive_disclosure.form_renderer import (
    field_state_transition,
    FIELD_STATES,
    get_visible_fields,
    get_asking_fields,
    compute_next_batch,
    BATCH_SIZE,
)
from progressive_disclosure.fields import TAB_FIELDS


def test_hidden_not_visible():
    reveal = {"sector": "HIDDEN", "annual_turnover": "ASKING"}
    visible = get_visible_fields(reveal)
    assert "sector" not in visible
    assert "annual_turnover" in visible


def test_asking_fields_filter():
    reveal = {"sector": "HIDDEN", "annual_turnover": "ASKING", "credit_score": "FILLED"}
    asking = get_asking_fields(reveal)
    assert "annual_turnover" in asking
    assert "sector" not in asking
    assert "credit_score" not in asking


def test_field_state_transition_valid():
    state = {"sector": "HIDDEN"}
    field_state_transition(state, "sector", "ASKING")
    assert state["sector"] == "ASKING"


def test_field_state_transition_invalid():
    state = {"sector": "HIDDEN"}
    with pytest.raises(ValueError, match="Invalid field state"):
        field_state_transition(state, "sector", "INVALID")


def test_compute_next_batch_respects_batch_size():
    field_defs = TAB_FIELDS["PD"]
    reveal = {}
    form_state = {}
    batch = compute_next_batch(field_defs, form_state, reveal)
    assert len(batch) <= BATCH_SIZE
    assert len(batch) > 0


def test_compute_next_batch_skips_revealed():
    field_defs = TAB_FIELDS["PD"]
    form_state = {}
    reveal = {"sector": "ASKING"}
    batch = compute_next_batch(field_defs, form_state, reveal)
    assert "sector" not in batch
    assert batch


def test_compute_next_batch_skips_filled_in_form():
    field_defs = TAB_FIELDS["PD"]
    form_state = {"sector": "Manufacturing"}
    reveal = {}
    batch = compute_next_batch(field_defs, form_state, reveal)
    assert "sector" not in batch
