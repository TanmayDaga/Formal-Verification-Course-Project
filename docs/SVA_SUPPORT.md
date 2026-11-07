# SVA Support in OSS CAD Suite / Yosys

## Investigation Summary
We probed the installed Yosys version (`Yosys 0.70+344`) and toolchain in OSS CAD Suite to determine support for concurrent SystemVerilog Assertions (SVA).

### Probed Features
1. **Concurrent Assertion Directives (`assert property`, `cover property`)**:
   - `assert property (@(posedge clk) ...)`: **Unsupported natively**.
   - Yosys Verilog/SystemVerilog frontend (`read_verilog -formal -sv`) produces: `syntax error, unexpected '@'`.
2. **Implication Operators (`|->`, `|=>`)**:
   - Module-level or concurrent implication operators: **Unsupported natively**.
   - Frontend produces: `syntax error, unexpected '>'`.
3. **Sequence Delay and Range (`##N`, `##[1:N]`)**:
   - Sequence timing operators: **Unsupported natively**.
4. **Disable Condition (`disable iff (...)`)**:
   - Concurrent assertion disable clause: **Unsupported natively**.
5. **Slang / External SVA Plugin**:
   - Yosys `plugin -l`: No external plugins loaded (`oss-cad-suite` does not bundle an external SVA compiler plugin).
6. **Clocked Immediate Assertions (`assert(...)`, `cover(...)`)**:
   - Supported inside clocked `always @(posedge clk)` blocks under `-formal`.
7. **Formal System Functions (`$past`, `$stable`, `$rose`, `$fell`)**:
   - Supported inside clocked procedural blocks under `-formal`.

## Architecture Strategy: Dual-Backend Output
To satisfy both industry-standard SVA portability and open-source formal execution with Yosys/sby:
1. **Standard Concurrent SVA Emitter**:
   Generates standard IEEE 1800 SystemVerilog concurrent assertions (`property p_<id>; @(posedge clk) disable iff (rst) ...; endproperty; assert property (p_<id>); cover property (...)`) into `props.sv`.
2. **Synthesizable Monitor Lowering**:
   Lowers all 12 requirement templates into synthesizable formal monitors with identical semantics:
   - Registers and valid flags for 1-cycle delays (`|=>`, `$past`, `$stable`)
   - Bounded cycle counters / shift timers for bounded response (`##[1:N]`)
   - Synchronous resets and guards
   - Procedural assertions and covers compatible with `yosys -formal` and `sby`.
