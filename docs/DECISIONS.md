# Architectural and Verification Decisions

1. **Dual Representation (Concurrent SVA and Synthesizable Monitors)**:
   - *Issue*: Native Yosys does not support IEEE 1800 concurrent assertion syntax (`property`, `|->`, `|=>`, `##[1:N]`, `disable iff`).
   - *Decision*: We emit full SystemVerilog concurrent assertions into `props.sv` for standard commercial tool compatibility (e.g. Questa, VCS, Xcelium, JasperGold). Simultaneously, we lower each assertion to an equivalent synthesizable monitor module with immediate clocked `assert` and `cover` statements for verification using Yosys and SymbiYosys (`sby`).

2. **Antecedent Coverage and Vacuity Detection**:
   - For every conditional assertion (`If X then ...`), we synthesize an associated `cover` statement for the antecedent condition `X`.
   - Before evaluating property assertions, a cover pass checks whether the antecedent was reachable within the BMC depth. If the antecedent is never triggered, the property is marked as `VACUOUS`.

3. **Per-Property Verification with SBY**:
   - Rather than running all properties simultaneously where one failure might obscure counterexamples or make cover analysis ambiguous, each property has an isolated formal target.
   - For each target, BMC is executed to depth 20 (with a 120-second timeout).
   - If BMC passes, a `mode prove` (k-induction) pass is executed:
     - If k-induction succeeds, the property status is reported as `PASS (proved)`.
     - If k-induction does not conclude within depth 20 but bounded BMC holds, the status is reported as `PASS (bounded)`.
   - If an assertion fails, the status is `FAIL` and the path to the counterexample VCD trace is captured.

4. **Reset Sequence in Wrapper**:
   - The formal wrapper drives clock and asserts synchronous active-high reset for the initial 3 cycles, then deasserts it, matching the Step 5 requirement. All external design inputs remain free symbolic inputs.
