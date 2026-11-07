import re
from typing import Optional, Dict, Any, List, Union

class Template:
    """Represents a requirement translation template mapping English regex to SVA and monitor IR."""
    def __init__(
        self,
        name: str,
        patterns: Union[str, List[str]],
        sva_template: str,
        antecedent_template: Optional[str] = None,
        kind: Optional[str] = None,
    ):
        self.name = name
        if isinstance(patterns, str):
            patterns = [patterns]
        self.patterns = [re.compile(p, re.IGNORECASE) for p in patterns]
        self.sva_template = sva_template
        self.antecedent_template = antecedent_template
        self.kind = kind or name

    def match(self, text: str) -> Optional[Dict[str, str]]:
        clean_text = text.strip().rstrip(".").strip()
        for p in self.patterns:
            m = p.match(clean_text)
            if m:
                return {k: v.strip() for k, v in m.groupdict().items() if v is not None}
        return None

    def format_sva(self, resolved_slots: Dict[str, str]) -> str:
        return self.sva_template.format(**resolved_slots)

    def format_antecedent(self, resolved_slots: Dict[str, str]) -> Optional[str]:
        if not self.antecedent_template:
            return None
        return self.antecedent_template.format(**resolved_slots)


# 12+ Templates Table. Each addition takes ~5 lines.
TEMPLATES = [
    # 4. If X then Y in the next cycle (|=>)
    Template(
        name="next_cycle",
        patterns=r"^if\s+(?P<X>.+?)\s+then\s+(?P<Y>.+?)\s+in\s+the\s+next\s+cycle$",
        sva_template="({X}) |=> ({Y})",
        antecedent_template="{X}",
        kind="next_cycle",
    ),
    # 5. If X then Y within N cycles (|-> ##[1:N] Y)
    Template(
        name="within_n_cycles",
        patterns=r"^if\s+(?P<X>.+?)\s+then\s+(?P<Y>.+?)\s+within\s+(?P<N>\d+)\s+cycles?$",
        sva_template="({X}) |-> ##[1:{N}] ({Y})",
        antecedent_template="{X}",
        kind="within_n_cycles",
    ),
    # 3. If X then Y (|->)
    Template(
        name="implication",
        patterns=r"^if\s+(?P<X>.+?)\s+then\s+(?P<Y>.+)$",
        sva_template="({X}) |-> ({Y})",
        antecedent_template="{X}",
        kind="implication",
    ),
    # 1. X must always hold / always X
    Template(
        name="always_hold",
        patterns=[
            r"^always\s+(?P<X>.+)$",
            r"^(?P<X>.+?)\s+must\s+always\s+hold$",
        ],
        sva_template="{X}",
        antecedent_template="{X}",
        kind="always_hold",
    ),
    # 2. X must never happen / X must never be true
    Template(
        name="never_happen",
        patterns=[
            r"^(?P<X>.+?)\s+must\s+never\s+(?:happen|be\s+true)$",
            r"^never\s+(?P<X>.+)$",
        ],
        sva_template="!({X})",
        antecedent_template="{X}",
        kind="never_happen",
    ),
    # 6. Y must only change when X
    Template(
        name="only_change_when",
        patterns=r"^(?P<Y>.+?)\s+must\s+only\s+change\s+when\s+(?P<X>.+)$",
        sva_template="(!$stable({Y})) |-> ({X})",
        antecedent_template="!$stable({Y})",
        kind="only_change_when",
    ),
    # 7. X must remain stable while Y ($stable)
    Template(
        name="stable_while",
        patterns=r"^(?P<X>.+?)\s+must\s+remain\s+stable\s+while\s+(?P<Y>.+)$",
        sva_template="({Y}) |-> $stable({X})",
        antecedent_template="{Y}",
        kind="stable_while",
    ),
    # 8. X must be Z after reset
    Template(
        name="after_reset",
        patterns=r"^(?P<X>.+?)\s+must\s+be\s+(?P<Z>.+?)\s+after\s+reset$",
        sva_template="($past(rst) && !rst) |-> (({X}) == ({Z}))",
        antecedent_template="$past(rst) && !rst",
        kind="after_reset",
    ),
    # 9. X and Y are mutually exclusive
    Template(
        name="mutually_exclusive",
        patterns=r"^(?P<X>.+?)\s+and\s+(?P<Y>.+?)\s+are\s+mutually\s+exclusive$",
        sva_template="!(({X}) && ({Y}))",
        antecedent_template="({X}) || ({Y})",
        kind="mutually_exclusive",
    ),
    # 10. X must never be followed by Y in the next cycle
    Template(
        name="never_followed_by",
        patterns=r"^(?P<X>.+?)\s+must\s+never\s+be\s+followed\s+by\s+(?P<Y>.+?)\s+in\s+the\s+next\s+cycle$",
        sva_template="({X}) |=> !({Y})",
        antecedent_template="{X}",
        kind="never_followed_by",
    ),
    # 11a. X must never exceed N
    Template(
        name="never_exceed",
        patterns=r"^(?P<X>.+?)\s+must\s+never\s+exceed\s+(?P<N>.+)$",
        sva_template="({X}) <= ({N})",
        antecedent_template="({X}) == ({N})",
        kind="never_exceed",
    ),
    # 11b. X must never be less than N
    Template(
        name="never_less_than",
        patterns=r"^(?P<X>.+?)\s+must\s+never\s+be\s+less\s+than\s+(?P<N>.+)$",
        sva_template="({X}) >= ({N})",
        antecedent_template="({X}) == ({N})",
        kind="never_less_than",
    ),
    # 12. X must stay at Z when Y
    Template(
        name="stay_at_when",
        patterns=r"^(?P<X>.+?)\s+must\s+stay\s+at\s+(?P<Z>.+?)\s+when\s+(?P<Y>.+)$",
        sva_template="({Y}) |-> (({X}) == ({Z}))",
        antecedent_template="{Y}",
        kind="stay_at_when",
    ),
]
