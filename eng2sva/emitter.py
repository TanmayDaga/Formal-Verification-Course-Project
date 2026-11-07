import os
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Any

from .templates import TEMPLATES, Template
from .parser import (
    resolve_condition,
    build_signal_dictionary,
    UntranslatableError,
    UnknownPhraseError,
    TranslationError,
)

@dataclass
class TranslationItem:
    id: str
    text: str
    status: str  # "TRANSLATED", "UNTRANSLATABLE", "ERROR"
    template_name: Optional[str] = None
    kind: Optional[str] = None
    sva: Optional[str] = None
    antecedent: Optional[str] = None
    resolved_slots: Optional[Dict[str, str]] = None
    error_message: Optional[str] = None
    closest_candidates: Optional[List[str]] = None


def translate_requirement(
    req: Dict[str, Any],
    design_dict: Dict[str, str],
    templates: List[Template] = TEMPLATES,
) -> TranslationItem:
    """Translates a single English requirement into SVA and monitor IR."""
    req_id = str(req.get("id", "UNKNOWN"))
    text = str(req.get("text", "")).strip()

    # 1. Match against template regexes
    matched_template: Optional[Template] = None
    matched_slots: Optional[Dict[str, str]] = None

    for t in templates:
        slots = t.match(text)
        if slots is not None:
            matched_template = t
            matched_slots = slots
            break

    if not matched_template or matched_slots is None:
        return TranslationItem(
            id=req_id,
            text=text,
            status="UNTRANSLATABLE",
            error_message=f"No matching template pattern for '{text}'",
        )

    # 2. Resolve slots through the signal dictionary and operator grammar
    resolved_slots: Dict[str, str] = {}
    try:
        for slot_name, slot_val in matched_slots.items():
            if slot_name == "N" and slot_val.isdigit():
                resolved_slots[slot_name] = slot_val
            else:
                resolved_slots[slot_name] = resolve_condition(slot_val, design_dict, text)

        sva_body = matched_template.format_sva(resolved_slots)
        antecedent_expr = matched_template.format_antecedent(resolved_slots)

        return TranslationItem(
            id=req_id,
            text=text,
            status="TRANSLATED",
            template_name=matched_template.name,
            kind=matched_template.kind,
            sva=sva_body,
            antecedent=antecedent_expr,
            resolved_slots=resolved_slots,
        )

    except UnknownPhraseError as e:
        return TranslationItem(
            id=req_id,
            text=text,
            status="ERROR",
            error_message=str(e),
            closest_candidates=e.closest,
        )
    except TranslationError as e:
        return TranslationItem(
            id=req_id,
            text=text,
            status="ERROR",
            error_message=str(e),
        )


def emit_concurrent_sva(
    items: List[TranslationItem],
    design_config: Dict[str, Any],
) -> str:
    """
    Emits IEEE 1800 SystemVerilog concurrent assertion file (props.sv).
    Includes one named property p_<id> per requirement with disable iff rst,
    plus cover property for each antecedent.
    """
    clk = design_config.get("clock", "clk")
    rst_info = design_config.get("reset", {})
    if isinstance(rst_info, dict):
        rst_name = rst_info.get("name", "rst")
        polarity = rst_info.get("polarity", "active_high")
        rst_expr = rst_name if polarity in ("active_high", "high", "1") else f"!{rst_name}"
    else:
        rst_expr = str(rst_info)

    lines: List[str] = [
        "// ============================================================================",
        "// Auto-generated SystemVerilog Assertions (eng2sva)",
        "// ============================================================================",
        "`default_nettype none",
        "",
    ]

    for item in items:
        if item.status != "TRANSLATED" or not item.sva:
            lines.append(f"// Requirement {item.id}: [{item.status}] \"{item.text}\"")
            if item.error_message:
                lines.append(f"// Error: {item.error_message}")
            lines.append("")
            continue

        lines.append(f"// Requirement {item.id}: \"{item.text}\"")
        lines.append(f"property p_{item.id};")
        lines.append(f"    @(posedge {clk}) disable iff ({rst_expr})")
        lines.append(f"        {item.sva};")
        lines.append("endproperty")
        lines.append(f"assert property (p_{item.id});")
        if item.antecedent:
            lines.append(f"cover property (@(posedge {clk}) disable iff ({rst_expr}) {item.antecedent});")
        lines.append("")

    return "\n".join(lines)


def emit_monitor_verilog(
    item: TranslationItem,
    design_config: Dict[str, Any],
    check_assert: bool = True,
    check_cover: bool = False,
) -> str:
    """
    Emits synthesizable Verilog monitor code for Yosys/sby verification.
    `check_assert`: if True, emits immediate assert(...) for the property.
    `check_cover`: if True, emits immediate cover(...) for antecedent reachability.
    """
    clk = design_config.get("clock", "clk")
    rst_info = design_config.get("reset", {})
    if isinstance(rst_info, dict):
        rst_name = rst_info.get("name", "rst")
        polarity = rst_info.get("polarity", "active_high")
        rst_expr = rst_name if polarity in ("active_high", "high", "1") else f"!{rst_name}"
    else:
        rst_expr = str(rst_info)

    slots = item.resolved_slots or {}
    kind = item.kind
    lines: List[str] = []

    lines.append(f"// --- Monitor for {item.id} ({kind}) ---")
    lines.append(f"// Requirement: {item.text}")

    reg_prefix = f"m_{item.id}"

    if kind == "always_hold":
        x = slots["X"]
        lines.append("always @(posedge " + clk + ") begin")
        lines.append(f"    if (!({rst_expr})) begin")
        if check_cover:
            lines.append(f"        cover({x});")
        if check_assert:
            lines.append(f"        assert({x});")
        lines.append("    end")
        lines.append("end")

    elif kind == "never_happen":
        x = slots["X"]
        lines.append("always @(posedge " + clk + ") begin")
        lines.append(f"    if (!({rst_expr})) begin")
        if check_cover:
            lines.append(f"        cover({x});")
        if check_assert:
            lines.append(f"        assert(!({x}));")
        lines.append("    end")
        lines.append("end")

    elif kind == "implication":
        x = slots["X"]
        y = slots["Y"]
        lines.append("always @(posedge " + clk + ") begin")
        lines.append(f"    if (!({rst_expr})) begin")
        if check_cover:
            lines.append(f"        if ({x}) cover(1'b1);")
        if check_assert:
            lines.append(f"        if ({x}) assert({y});")
        lines.append("    end")
        lines.append("end")

    elif kind == "next_cycle":
        x = slots["X"]
        y = slots["Y"]
        d1 = f"{reg_prefix}_d1"
        lines.append(f"reg {d1} = 1'b0;")
        # Check if Y is of the form "LHS == RHS" where RHS is not a constant literal
        eq_match = re.match(r"^(.+?)\s*==\s*(.+)$", y.strip())
        if eq_match:
            lhs = eq_match.group(1).strip()
            rhs = eq_match.group(2).strip()
            # If rhs is an input signal/identifier rather than a literal (like 8'd0 or 15)
            if not re.match(r"^(\d+'[bhdBHD][0-9a-fA-F_]+|\d+)$", rhs):
                past_rhs = f"{reg_prefix}_past_rhs"
                lines.append(f"reg [31:0] {past_rhs};")
                lines.append("always @(posedge " + clk + ") begin")
                lines.append(f"    if ({rst_expr}) begin")
                lines.append(f"        {d1} <= 1'b0;")
                lines.append("    end else begin")
                lines.append(f"        {d1} <= ({x});")
                lines.append(f"        {past_rhs} <= ({rhs});")
                if check_cover:
                    lines.append(f"        if ({x}) cover(1'b1);")
                if check_assert:
                    lines.append(f"        if ({d1}) assert({lhs} == {past_rhs});")
                lines.append("    end")
                lines.append("end")
            else:
                lines.append("always @(posedge " + clk + ") begin")
                lines.append(f"    if ({rst_expr}) begin")
                lines.append(f"        {d1} <= 1'b0;")
                lines.append("    end else begin")
                lines.append(f"        {d1} <= ({x});")
                if check_cover:
                    lines.append(f"        if ({x}) cover(1'b1);")
                if check_assert:
                    lines.append(f"        if ({d1}) assert({y});")
                lines.append("    end")
                lines.append("end")
        else:
            lines.append("always @(posedge " + clk + ") begin")
            lines.append(f"    if ({rst_expr}) begin")
            lines.append(f"        {d1} <= 1'b0;")
            lines.append("    end else begin")
            lines.append(f"        {d1} <= ({x});")
            if check_cover:
                lines.append(f"        if ({x}) cover(1'b1);")
            if check_assert:
                lines.append(f"        if ({d1}) assert({y});")
            lines.append("    end")
            lines.append("end")

    elif kind == "within_n_cycles":
        x = slots["X"]
        y = slots["Y"]
        n = int(slots.get("N", "1"))
        timer = f"{reg_prefix}_cnt"
        lines.append(f"reg [7:0] {timer} = 8'd0;")
        lines.append("always @(posedge " + clk + ") begin")
        lines.append(f"    if ({rst_expr}) begin")
        lines.append(f"        {timer} <= 8'd0;")
        lines.append("    end else begin")
        if check_cover:
            lines.append(f"        if ({x}) cover(1'b1);")
        lines.append(f"        if ({timer} > 8'd0) begin")
        lines.append(f"            if ({y}) begin")
        lines.append(f"                {timer} <= ({x} && !({y})) ? 8'd{n} : 8'd0;")
        lines.append(f"            end else if ({timer} == 8'd1) begin")
        if check_assert:
            lines.append("                assert(1'b0); // Deadline reached without Y")
        lines.append(f"                {timer} <= ({x}) ? 8'd{n} : 8'd0;")
        lines.append("            end else begin")
        lines.append(f"                {timer} <= {timer} - 8'd1;")
        lines.append("            end")
        lines.append(f"        end else if ({x} && !({y})) begin")
        lines.append(f"            {timer} <= 8'd{n};")
        lines.append("        end")
        lines.append("    end")
        lines.append("end")

    elif kind == "only_change_when":
        x = slots["X"]
        y = slots["Y"]
        past_y = f"{reg_prefix}_past_y"
        past_x = f"{reg_prefix}_past_x"
        valid = f"{reg_prefix}_valid"
        lines.append(f"reg [31:0] {past_y};")
        lines.append(f"reg {past_x};")
        lines.append(f"reg {valid} = 1'b0;")
        lines.append("always @(posedge " + clk + ") begin")
        lines.append(f"    if ({rst_expr}) begin")
        lines.append(f"        {valid} <= 1'b0;")
        lines.append("    end else begin")
        lines.append(f"        if ({valid} && ({y} != {past_y})) begin")
        if check_cover:
            lines.append("            cover(1'b1);")
        if check_assert:
            lines.append(f"            assert({past_x});")
        lines.append("        end")
        lines.append(f"        {past_y} <= {y};")
        lines.append(f"        {past_x} <= ({x});")
        lines.append(f"        {valid} <= 1'b1;")
        lines.append("    end")
        lines.append("end")

    elif kind == "stable_while":
        x = slots["X"]
        y = slots["Y"]
        past_x = f"{reg_prefix}_past_x"
        past_y = f"{reg_prefix}_past_y"
        valid = f"{reg_prefix}_valid"
        lines.append(f"reg [31:0] {past_x};")
        lines.append(f"reg {past_y};")
        lines.append(f"reg {valid} = 1'b0;")
        lines.append("always @(posedge " + clk + ") begin")
        lines.append(f"    if ({rst_expr}) begin")
        lines.append(f"        {valid} <= 1'b0;")
        lines.append("    end else begin")
        lines.append(f"        if ({valid} && ({past_y})) begin")
        if check_cover:
            lines.append("            cover(1'b1);")
        if check_assert:
            lines.append(f"            assert({x} == {past_x});")
        lines.append("        end")
        lines.append(f"        {past_x} <= {x};")
        lines.append(f"        {past_y} <= ({y});")
        lines.append(f"        {valid} <= 1'b1;")
        lines.append("    end")
        lines.append("end")

    elif kind == "after_reset":
        x = slots["X"]
        z = slots["Z"]
        past_rst = f"{reg_prefix}_past_rst"
        lines.append(f"reg {past_rst} = 1'b1;")
        lines.append("always @(posedge " + clk + ") begin")
        lines.append(f"    if ({past_rst} && !({rst_expr})) begin")
        if check_cover:
            lines.append("        cover(1'b1);")
        if check_assert:
            lines.append(f"        assert(({x}) == ({z}));")
        lines.append("    end")
        lines.append(f"    {past_rst} <= ({rst_expr});")
        lines.append("end")

    elif kind == "mutually_exclusive":
        x = slots["X"]
        y = slots["Y"]
        lines.append("always @(posedge " + clk + ") begin")
        lines.append(f"    if (!({rst_expr})) begin")
        if check_cover:
            lines.append(f"        if (({x}) || ({y})) cover(1'b1);")
        if check_assert:
            lines.append(f"        assert(!(({x}) && ({y})));")
        lines.append("    end")
        lines.append("end")

    elif kind == "never_followed_by":
        x = slots["X"]
        y = slots["Y"]
        d1 = f"{reg_prefix}_d1"
        lines.append(f"reg {d1} = 1'b0;")
        lines.append("always @(posedge " + clk + ") begin")
        lines.append(f"    if ({rst_expr}) begin")
        lines.append(f"        {d1} <= 1'b0;")
        lines.append("    end else begin")
        lines.append(f"        {d1} <= ({x});")
        if check_cover:
            lines.append(f"        if ({x}) cover(1'b1);")
        if check_assert:
            lines.append(f"        if ({d1}) assert(!({y}));")
        lines.append("    end")
        lines.append("end")

    elif kind == "never_exceed":
        x = slots["X"]
        n = slots["N"]
        lines.append("always @(posedge " + clk + ") begin")
        lines.append(f"    if (!({rst_expr})) begin")
        if check_cover:
            lines.append(f"        if (({x}) == ({n})) cover(1'b1);")
        if check_assert:
            lines.append(f"        assert(({x}) <= ({n}));")
        lines.append("    end")
        lines.append("end")

    elif kind == "never_less_than":
        x = slots["X"]
        n = slots["N"]
        lines.append("always @(posedge " + clk + ") begin")
        lines.append(f"    if (!({rst_expr})) begin")
        if check_cover:
            lines.append(f"        if (({x}) == ({n})) cover(1'b1);")
        if check_assert:
            lines.append(f"        assert(({x}) >= ({n}));")
        lines.append("    end")
        lines.append("end")

    elif kind == "stay_at_when":
        x = slots["X"]
        z = slots["Z"]
        y = slots["Y"]
        lines.append("always @(posedge " + clk + ") begin")
        lines.append(f"    if (!({rst_expr})) begin")
        if check_cover:
            lines.append(f"        if ({y}) cover(1'b1);")
        if check_assert:
            lines.append(f"        if ({y}) assert(({x}) == ({z}));")
        lines.append("    end")
        lines.append("end")

    return "\n".join(lines)
