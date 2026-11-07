# eng2sva: Controlled-English to SystemVerilog Assertions & Formal Verification

`eng2sva` is an automated verification toolchain that translates controlled-English specification requirements into IEEE 1800 SystemVerilog Assertions (SVA) and verifies them against RTL designs using open-source formal tools (Yosys and SymbiYosys `sby`).

---

## 1. Architecture

```
                  +-----------------------------------+
                  | English Specification (YAML)      |
                  | e.g. "If req0 then gnt0 in next"  |
                  +-----------------+-----------------+
                                    |
                                    v
+------------------+      +-------------------+
| Signal / Symbol  | ===> | Resolver & Matcher|
| Dictionary (YAML)|      | (Longest Match)   |
+------------------+      +---------+---------+
                                    |
                                    v
                      +---------------------------+
                      | Intermediate Property IR  |
                      +-------------+-------------+
                                    |
        +---------------------------+---------------------------+
        |                                                       |
        v                                                       v
+-------------------------------+               +-------------------------------+
| SVA Concurrent Property       |               | Synthesizable Formal Monitor  |
| Emitter (`props.sv`)          |               | Generator (Immediate Assert)  |
+-------------------------------+               +---------------+---------------+
| IEEE 1800 syntax:             |                               |
| - `assert property`           |                               v
| - `cover property`            |               +-------------------------------+
| - `|->`, `|=>`, `##[1:N]`     |               | Formal Verification Harness   |
| - `disable iff (rst)`         |               | (Yosys + SBY + Yices)         |
+-------------------------------+               +---------------+---------------+
                                                                |
                                                                v
                                                +-------------------------------+
                                                | Results & Kill Table Reporter |
                                                | (`results.json`, `report.md`) |
                                                +-------------------------------+
```

---

## 2. Quick Start

### Prerequisites
- Python 3 with `pyyaml` and `pytest`
- OSS CAD Suite (`yosys`, `sby`, `verilator`, `yices`)

### Commands
```bash
# Verify environment dependencies
make setup

# Lint all RTL designs and buggy variants
make lint

# Run unit tests (47 tests for all 12 templates and error paths)
make test

# Translate a spec to IEEE 1800 SVA
python3 -m eng2sva translate --design designs/fifo.yaml --spec specs/fifo.yaml --out build/fifo/props.sv

# Check formal properties on correct and buggy RTL variants
python3 -m eng2sva check --design designs/arbiter.yaml --spec specs/arbiter.yaml

# Run the complete testbench demo across all 6 designs
make demo
```

---

## 3. How to Add a Template (~5 Lines)

Templates map regex patterns to SVA expressions and monitor generators in `eng2sva/templates.py`. Each template inherits from `Template`.

To add a new template:
```python
Template(
    name="my_new_template",
    patterns=r"^(?P<X>.+?)\s+must\s+trigger\s+(?P<Y>.+)$",
    sva_template="({X}) |-> ({Y})",
    antecedent_template="{X}",
    kind="implication",
)
```

Add this object to the `TEMPLATES` list in `eng2sva/templates.py`. The regex group names (`X`, `Y`, `N`, `Z`) are automatically extracted and passed to the dictionary resolver.

---

## 4. How to Add a Design

1. **Write Clean Verilog-2001 RTL**: Place synthesizable RTL in `designs/rtl/<name>.v`.
2. **Write Injected Bug RTL**: Place the buggy variant in `designs/rtl_bug/<name>.v` and document the bug in `designs/BUGS.md`.
3. **Write Design Dictionary (`designs/<name>.yaml`)**:
   ```yaml
   top: my_module
   files:
     - designs/rtl/my_module.v
   buggy_files:
     - designs/rtl_bug/my_module.v
   clock: clk
   reset:
     name: rst
     polarity: active_high
   signals:
     "the my output": out
     "the request": req
   constants:
     "0": "1'b0"
     "1": "1'b1"
   ```
4. **Write Specifications (`specs/<name>.yaml`)**:
   ```yaml
   requirements:
     - id: M01
       text: out must be 0 after reset
     - id: M02
       text: If req then out in the next cycle
   ```
5. **Run Formal Verification**:
   ```bash
   python3 -m eng2sva check --design designs/my_module.yaml --spec specs/my_module.yaml
   ```

---

## 5. Honest Limitations

1. **Proof Depth**:
   - `PASS (proved)` means the rule holds forever for all possible cycles.
   - `PASS (bounded)` means the rule holds for the first 20 cycles. The tool cannot guarantee what happens after cycle 20 without extra hints.

2. **Unconstrained Inputs**:
   - Inputs are completely random and can change value every clock cycle. If a property assumes an input stays stable or follows a specific sequence, it might fail unless you explicitly state that rule.

3. **Strict English Phrasing**:
   - The tool only recognizes specific sentence patterns. Vague, poetic, or informal English (such as *"the counter should be fast"*) will not be translated and will be marked as `UNTRANSLATABLE`.

4. **Yosys SVA Compatibility**:
   - Open-source Yosys cannot directly read complex concurrent SVA syntax (like `assert property (@...)`). Because of this, `eng2sva` turns rules into small, standard Verilog monitor circuits that Yosys and SBY can check directly. A standard SVA file (`props.sv`) is also generated for commercial tools.

5. **What "PASS" Really Means**:
   - A `PASS` only means the rules you actually wrote were not broken.
   - It does **not** mean the design is 100% bug-free: if you forgot to write a rule for an important behavior, a bug can still slip through undetected.
