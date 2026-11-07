"""eng2sva: Controlled-English to SystemVerilog Assertions translator and formal checker."""
from .templates import TEMPLATES, Template
from .parser import build_signal_dictionary, resolve_condition, UnknownPhraseError, UntranslatableError
from .emitter import translate_requirement, emit_concurrent_sva, emit_monitor_verilog
from .checker import check_property, CheckResult
from .report import generate_design_reports

__all__ = [
    "TEMPLATES",
    "Template",
    "build_signal_dictionary",
    "resolve_condition",
    "UnknownPhraseError",
    "UntranslatableError",
    "translate_requirement",
    "emit_concurrent_sva",
    "emit_monitor_verilog",
    "check_property",
    "CheckResult",
    "generate_design_reports",
]
