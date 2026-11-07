import pytest
import yaml
from eng2sva.templates import TEMPLATES
from eng2sva.parser import (
    build_signal_dictionary,
    resolve_condition,
    UnknownPhraseError,
    UntranslatableError,
)
from eng2sva.emitter import translate_requirement, emit_concurrent_sva

# Dummy test dictionary
SAMPLE_DESIGN = {
    "top": "test_unit",
    "clock": "clk",
    "reset": {"name": "rst", "polarity": "active_high"},
    "signals": {
        "grant 0": "gnt0",
        "grant 1": "gnt1",
        "request 0": "req0",
        "request 1": "req1",
        "fifo full": "full",
        "fifo empty": "empty",
        "fifo count": "cnt",
        "state": "state",
        "count": "count",
        "load": "load",
        "out": "out",
        "q": "q",
    },
    "constants": {
        "RED": "2'd0",
        "GREEN": "2'd1",
        "YELLOW": "2'd2",
        "zero": "3'd0",
        "max": "4'd15",
        "0": "0",
        "15": "15",
    },
    "events": {
        "write": "wr_en",
    }
}

DICT = build_signal_dictionary(SAMPLE_DESIGN)

# --- Category 1: Template 1 - Always hold (4 tests) ---
def test_template_always_1():
    item = translate_requirement({"id": "T01", "text": "always count is greater than or equal to 0"}, DICT, TEMPLATES)
    assert item.status == "TRANSLATED"
    assert item.sva == "count >= 0"

def test_template_always_2():
    item = translate_requirement({"id": "T02", "text": "count is greater than or equal to 0 must always hold"}, DICT, TEMPLATES)
    assert item.status == "TRANSLATED"
    assert item.sva == "count >= 0"

def test_template_always_3():
    item = translate_requirement({"id": "T03", "text": "always out equals 0"}, DICT, TEMPLATES)
    assert item.status == "TRANSLATED"
    assert item.sva == "out == 0"

def test_template_always_4():
    item = translate_requirement({"id": "T04", "text": "always q not equal to 15"}, DICT, TEMPLATES)
    assert item.status == "TRANSLATED"
    assert item.sva == "q != 15"

# --- Category 2: Template 2 - Never happen / Never be true (4 tests) ---
def test_template_never_1():
    item = translate_requirement({"id": "T05", "text": "never grant 0 and grant 1"}, DICT, TEMPLATES)
    assert item.status == "TRANSLATED"
    assert item.sva == "!(gnt0 && gnt1)"

def test_template_never_2():
    item = translate_requirement({"id": "T06", "text": "grant 0 and grant 1 must never happen"}, DICT, TEMPLATES)
    assert item.status == "TRANSLATED"
    assert item.sva == "!(gnt0 && gnt1)"

def test_template_never_3():
    item = translate_requirement({"id": "T07", "text": "fifo full and fifo empty must never be true"}, DICT, TEMPLATES)
    assert item.status == "TRANSLATED"
    assert item.sva == "!(full && empty)"

def test_template_never_4():
    item = translate_requirement({"id": "T08", "text": "out must never happen"}, DICT, TEMPLATES)
    assert item.status == "TRANSLATED"
    assert item.sva == "!(out)"

# --- Category 3: Template 3 - Implication (|->) (4 tests) ---
def test_template_implication_1():
    item = translate_requirement({"id": "T09", "text": "If request 0 then grant 0"}, DICT, TEMPLATES)
    assert item.status == "TRANSLATED"
    assert item.sva == "(req0) |-> (gnt0)"

def test_template_implication_2():
    item = translate_requirement({"id": "T10", "text": "If out then request 0 is greater than 0"}, DICT, TEMPLATES)
    assert item.status == "TRANSLATED"
    assert item.sva == "(out) |-> (req0 > 0)"

def test_template_implication_3():
    item = translate_requirement({"id": "T11", "text": "If fifo full then not fifo empty"}, DICT, TEMPLATES)
    assert item.status == "TRANSLATED"
    assert item.sva == "(full) |-> (!empty)"

def test_template_implication_4():
    item = translate_requirement({"id": "T12", "text": "If not load then count equals 0"}, DICT, TEMPLATES)
    assert item.status == "TRANSLATED"
    assert item.sva == "(!load) |-> (count == 0)"

# --- Category 4: Template 4 - Next cycle (|=>) (4 tests) ---
def test_template_next_cycle_1():
    item = translate_requirement({"id": "T13", "text": "If request 0 then grant 0 in the next cycle"}, DICT, TEMPLATES)
    assert item.status == "TRANSLATED"
    assert item.sva == "(req0) |=> (gnt0)"

def test_template_next_cycle_2():
    item = translate_requirement({"id": "T14", "text": "If load then q equals 0 in the next cycle"}, DICT, TEMPLATES)
    assert item.status == "TRANSLATED"
    assert item.sva == "(load) |=> (q == 0)"

def test_template_next_cycle_3():
    item = translate_requirement({"id": "T15", "text": "If count equals 15 then count equals 15 in the next cycle"}, DICT, TEMPLATES)
    assert item.status == "TRANSLATED"
    assert item.sva == "(count == 15) |=> (count == 15)"

def test_template_next_cycle_4():
    item = translate_requirement({"id": "T16", "text": "If write then fifo count is greater than 0 in the next cycle"}, DICT, TEMPLATES)
    assert item.status == "TRANSLATED"
    assert item.sva == "(wr_en) |=> (cnt > 0)"

# --- Category 5: Template 5 - Within N cycles (4 tests) ---
def test_template_within_n_1():
    item = translate_requirement({"id": "T17", "text": "If state equals GREEN then state equals YELLOW within 4 cycles"}, DICT, TEMPLATES)
    assert item.status == "TRANSLATED"
    assert item.sva == "(state == 2'd1) |-> ##[1:4] (state == 2'd2)"

def test_template_within_n_2():
    item = translate_requirement({"id": "T18", "text": "If request 0 then grant 0 within 2 cycles"}, DICT, TEMPLATES)
    assert item.status == "TRANSLATED"
    assert item.sva == "(req0) |-> ##[1:2] (gnt0)"

def test_template_within_n_3():
    item = translate_requirement({"id": "T19", "text": "If write then fifo full within 8 cycles"}, DICT, TEMPLATES)
    assert item.status == "TRANSLATED"
    assert item.sva == "(wr_en) |-> ##[1:8] (full)"

def test_template_within_n_4():
    item = translate_requirement({"id": "T20", "text": "If load then out within 1 cycle"}, DICT, TEMPLATES)
    assert item.status == "TRANSLATED"
    assert item.sva == "(load) |-> ##[1:1] (out)"

# --- Category 6: Template 6 - Only change when (3 tests) ---
def test_template_only_change_1():
    item = translate_requirement({"id": "T21", "text": "count must only change when load"}, DICT, TEMPLATES)
    assert item.status == "TRANSLATED"
    assert item.sva == "(!$stable(count)) |-> (load)"

def test_template_only_change_2():
    item = translate_requirement({"id": "T22", "text": "q must only change when load or request 0"}, DICT, TEMPLATES)
    assert item.status == "TRANSLATED"
    assert item.sva == "(!$stable(q)) |-> (load || req0)"

def test_template_only_change_3():
    item = translate_requirement({"id": "T23", "text": "fifo count must only change when write"}, DICT, TEMPLATES)
    assert item.status == "TRANSLATED"
    assert item.sva == "(!$stable(cnt)) |-> (wr_en)"

# --- Category 7: Template 7 - Stable while (3 tests) ---
def test_template_stable_while_1():
    item = translate_requirement({"id": "T24", "text": "count must remain stable while not load"}, DICT, TEMPLATES)
    assert item.status == "TRANSLATED"
    assert item.sva == "(!load) |-> $stable(count)"

def test_template_stable_while_2():
    item = translate_requirement({"id": "T25", "text": "q must remain stable while not load and not request 0"}, DICT, TEMPLATES)
    assert item.status == "TRANSLATED"
    assert item.sva == "(!load && !req0) |-> $stable(q)"

def test_template_stable_while_3():
    item = translate_requirement({"id": "T26", "text": "out must remain stable while fifo empty"}, DICT, TEMPLATES)
    assert item.status == "TRANSLATED"
    assert item.sva == "(empty) |-> $stable(out)"

# --- Category 8: Template 8 - After reset (3 tests) ---
def test_template_after_reset_1():
    item = translate_requirement({"id": "T27", "text": "count must be 0 after reset"}, DICT, TEMPLATES)
    assert item.status == "TRANSLATED"
    assert item.sva == "($past(rst) && !rst) |-> ((count) == (0))"

def test_template_after_reset_2():
    item = translate_requirement({"id": "T28", "text": "state must be RED after reset"}, DICT, TEMPLATES)
    assert item.status == "TRANSLATED"
    assert item.sva == "($past(rst) && !rst) |-> ((state) == (2'd0))"

def test_template_after_reset_3():
    item = translate_requirement({"id": "T29", "text": "grant 0 must be 0 after reset"}, DICT, TEMPLATES)
    assert item.status == "TRANSLATED"
    assert item.sva == "($past(rst) && !rst) |-> ((gnt0) == (0))"

# --- Category 9: Template 9 - Mutually exclusive (3 tests) ---
def test_template_mutually_exclusive_1():
    item = translate_requirement({"id": "T30", "text": "grant 0 and grant 1 are mutually exclusive"}, DICT, TEMPLATES)
    assert item.status == "TRANSLATED"
    assert item.sva == "!((gnt0) && (gnt1))"

def test_template_mutually_exclusive_2():
    item = translate_requirement({"id": "T31", "text": "fifo full and fifo empty are mutually exclusive"}, DICT, TEMPLATES)
    assert item.status == "TRANSLATED"
    assert item.sva == "!((full) && (empty))"

def test_template_mutually_exclusive_3():
    item = translate_requirement({"id": "T32", "text": "out and count equals 0 are mutually exclusive"}, DICT, TEMPLATES)
    assert item.status == "TRANSLATED"
    assert item.sva == "!((out) && (count == 0))"

# --- Category 10: Template 10 - Never followed by in next cycle (3 tests) ---
def test_template_never_followed_by_1():
    item = translate_requirement({"id": "T33", "text": "state equals GREEN must never be followed by state equals RED in the next cycle"}, DICT, TEMPLATES)
    assert item.status == "TRANSLATED"
    assert item.sva == "(state == 2'd1) |=> !(state == 2'd0)"

def test_template_never_followed_by_2():
    item = translate_requirement({"id": "T34", "text": "grant 0 must never be followed by grant 1 in the next cycle"}, DICT, TEMPLATES)
    assert item.status == "TRANSLATED"
    assert item.sva == "(gnt0) |=> !(gnt1)"

def test_template_never_followed_by_3():
    item = translate_requirement({"id": "T35", "text": "fifo full must never be followed by fifo empty in the next cycle"}, DICT, TEMPLATES)
    assert item.status == "TRANSLATED"
    assert item.sva == "(full) |=> !(empty)"

# --- Category 11: Template 11 - Never exceed / Never less than (3 tests) ---
def test_template_never_exceed_1():
    item = translate_requirement({"id": "T36", "text": "count must never exceed 15"}, DICT, TEMPLATES)
    assert item.status == "TRANSLATED"
    assert item.sva == "(count) <= (15)"

def test_template_never_exceed_2():
    item = translate_requirement({"id": "T37", "text": "fifo count must never exceed 4"}, DICT, TEMPLATES)
    assert item.status == "TRANSLATED"
    assert item.sva == "(cnt) <= (4)"

def test_template_never_less_than_1():
    item = translate_requirement({"id": "T38", "text": "count must never be less than 0"}, DICT, TEMPLATES)
    assert item.status == "TRANSLATED"
    assert item.sva == "(count) >= (0)"

# --- Category 12: Template 12 - Stay at when (3 tests) ---
def test_template_stay_at_when_1():
    item = translate_requirement({"id": "T39", "text": "fifo count must stay at 4 when fifo full"}, DICT, TEMPLATES)
    assert item.status == "TRANSLATED"
    assert item.sva == "(full) |-> ((cnt) == (4))"

def test_template_stay_at_when_2():
    item = translate_requirement({"id": "T40", "text": "count must stay at 15 when count equals 15 and not load"}, DICT, TEMPLATES)
    assert item.status == "TRANSLATED"
    assert item.sva == "(count == 15 && !load) |-> ((count) == (15))"

def test_template_stay_at_when_3():
    item = translate_requirement({"id": "T41", "text": "state must stay at RED when not request 0"}, DICT, TEMPLATES)
    assert item.status == "TRANSLATED"
    assert item.sva == "(!req0) |-> ((state) == (2'd0))"

# --- Category 13: Error Paths & Untranslatable (6 tests) ---
def test_untranslatable_sentence_1():
    item = translate_requirement({"id": "E01", "text": "The counter should feel responsive and fast."}, DICT, TEMPLATES)
    assert item.status == "UNTRANSLATABLE"
    assert "No matching template" in item.error_message

def test_untranslatable_sentence_2():
    item = translate_requirement({"id": "E02", "text": "The lights must look pleasant to motorists."}, DICT, TEMPLATES)
    assert item.status == "UNTRANSLATABLE"

def test_unknown_signal_phrase_with_suggestions():
    item = translate_requirement({"id": "E03", "text": "fifo_cnt must never exceed 4"}, DICT, TEMPLATES)
    assert item.status == "ERROR"
    assert "UNKNOWN PHRASE: 'fifo_cnt'" in item.error_message
    assert item.closest_candidates is not None
    assert "fifo count" in item.closest_candidates

def test_unknown_signal_phrase_raises_direct():
    with pytest.raises(UnknownPhraseError) as exc_info:
        resolve_condition("nonexistent_sig equals 0", DICT, "test")
    assert "nonexistent_sig" in str(exc_info.value)
    assert exc_info.value.closest is not None

def test_emit_concurrent_sva_output():
    items = [
        translate_requirement({"id": "A01", "text": "grant 0 and grant 1 are mutually exclusive"}, DICT, TEMPLATES),
        translate_requirement({"id": "A02", "text": "count must be 0 after reset"}, DICT, TEMPLATES),
    ]
    sva_code = emit_concurrent_sva(items, SAMPLE_DESIGN)
    assert "property p_A01;" in sva_code
    assert "assert property (p_A01);" in sva_code
    assert "disable iff (rst)" in sva_code
    assert "cover property (@(posedge clk) disable iff (rst) (gnt0) || (gnt1));" in sva_code

def test_emit_concurrent_sva_untranslatable_commented():
    items = [
        translate_requirement({"id": "U01", "text": "Design should be super quick."}, DICT, TEMPLATES),
    ]
    sva_code = emit_concurrent_sva(items, SAMPLE_DESIGN)
    assert "// Requirement U01: [UNTRANSLATABLE]" in sva_code
