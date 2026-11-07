import difflib
import re
from typing import Dict, List, Tuple, Optional

class TranslationError(Exception):
    """Base exception for translation errors."""
    pass

class UntranslatableError(TranslationError):
    """Raised when an English sentence matches no template."""
    def __init__(self, text: str):
        super().__init__(f"UNTRANSLATABLE: '{text}' does not match any recognized SVA template pattern.")
        self.text = text

class UnknownPhraseError(TranslationError):
    """Raised when an English phrase cannot be resolved in the signal dictionary."""
    def __init__(self, phrase: str, text: str, closest: List[str]):
        super().__init__(
            f"UNKNOWN PHRASE: '{phrase}' in requirement '{text}'. Closest candidates: {closest}"
        )
        self.phrase = phrase
        self.text = text
        self.closest = closest


# Relational and logical operators mapped from English phrases to Verilog operators.
# Ordered by length descending so longer phrases match first.
OPERATORS: List[Tuple[str, str]] = [
    ("is greater than or equal to", ">="),
    ("greater than or equal to", ">="),
    ("is less than or equal to", "<="),
    ("less than or equal to", "<="),
    ("is not equal to", "!="),
    ("not equal to", "!="),
    ("is equal to", "=="),
    ("is greater than", ">"),
    ("greater than", ">"),
    ("is less than", "<"),
    ("less than", "<"),
    ("equals", "=="),
    ("equal to", "=="),
    ("and", "&&"),
    ("or", "||"),
    ("not", "!"),
    ("==", "=="),
    ("!=", "!="),
    (">=", ">="),
    ("<=", "<="),
    (">", ">"),
    ("<", "<"),
    ("(", "("),
    (")", ")"),
]


def build_signal_dictionary(design_yaml: Dict) -> Dict[str, str]:
    """Combines signals, constants, and events into a normalized dictionary (lowercase keys)."""
    dictionary: Dict[str, str] = {}

    # 1. Signals
    for k, v in design_yaml.get("signals", {}).items():
        dictionary[k.lower().strip()] = str(v).strip()

    # 2. Constants
    for k, v in design_yaml.get("constants", {}).items():
        dictionary[k.lower().strip()] = str(v).strip()

    # 3. Events
    for k, v in design_yaml.get("events", {}).items():
        dictionary[k.lower().strip()] = str(v).strip()

    # 4. Standard reset signal name if specified
    if "reset" in design_yaml and isinstance(design_yaml["reset"], dict):
        rst_name = design_yaml["reset"].get("name", "rst")
        dictionary["reset"] = rst_name
        dictionary["rst"] = rst_name

    return dictionary


def resolve_condition(
    condition_text: str,
    dictionary: Dict[str, str],
    full_text: str
) -> str:
    """
    Resolves an English condition into an RTL expression.
    Uses longest match first (case-insensitive) against dictionary and operators.
    Raises UnknownPhraseError if a phrase cannot be resolved, giving difflib candidates.
    """
    text = condition_text.strip()
    if not text:
        return ""

    # Sort dictionary keys by length descending (longest match first)
    dict_keys_sorted = sorted(dictionary.keys(), key=lambda k: len(k), reverse=True)

    tokens: List[str] = []
    i = 0
    n = len(text)

    while i < n:
        # Skip whitespace
        if text[i].isspace():
            i += 1
            continue

        matched = False
        remaining = text[i:]
        remaining_lower = remaining.lower()

        # 1. Check dictionary phrases first (longest match first)
        for key in dict_keys_sorted:
            # Match either at word boundary or exact start
            if remaining_lower.startswith(key):
                end_pos = len(key)
                # Ensure word boundary if key ends with an alphanumeric character
                if end_pos < len(remaining) and (key[-1].isalnum() and remaining[end_pos].isalnum()):
                    continue
                tokens.append(dictionary[key])
                i += end_pos
                matched = True
                break
        if matched:
            continue

        # 2. Check operators (longest match first)
        for op_phrase, op_symbol in OPERATORS:
            if remaining_lower.startswith(op_phrase):
                end_pos = len(op_phrase)
                # Word boundary check for alphabetic operators
                if op_phrase[-1].isalpha() and end_pos < len(remaining) and remaining[end_pos].isalnum():
                    continue
                tokens.append(op_symbol)
                i += end_pos
                matched = True
                break
        if matched:
            continue

        # 3. Check Verilog literal (e.g. 4'd15, 8'hff, 1'b0)
        vlog_lit = re.match(r"^(\d+'[bhdBHD][0-9a-fA-F_]+)", remaining)
        if vlog_lit:
            lit = vlog_lit.group(1)
            tokens.append(lit)
            i += len(lit)
            continue

        # 4. Check decimal integer literal (e.g. 15, 0, 4)
        num_lit = re.match(r"^(\d+)", remaining)
        if num_lit:
            lit = num_lit.group(1)
            tokens.append(lit)
            i += len(lit)
            continue

        # 5. Check identifier-like token (possible unknown phrase or word)
        id_match = re.match(r"^([a-zA-Z_][a-zA-Z0-9_]*)", remaining)
        if id_match:
            unknown_token = id_match.group(1)
            # Find closest dictionary candidates
            closest = difflib.get_close_matches(
                unknown_token.lower(),
                list(dictionary.keys()),
                n=5,
                cutoff=0.3
            )
            # Also check difflib with the remaining sentence fragment
            if not closest:
                fragment = remaining.split()[0]
                closest = difflib.get_close_matches(fragment.lower(), list(dictionary.keys()), n=5, cutoff=0.2)
            raise UnknownPhraseError(unknown_token, full_text, closest)

        # 6. Unmatched punctuation or character
        char = remaining[0]
        closest = difflib.get_close_matches(char, list(dictionary.keys()), n=3, cutoff=0.1)
        raise UnknownPhraseError(char, full_text, closest)

    # Format tokens into valid expression
    # Join tokens with space, but keep unary operators tight
    expr = " ".join(tokens)
    # Tidy up common patterns: '! ' -> '!'
    expr = re.sub(r'!\s+', '!', expr)
    return expr
