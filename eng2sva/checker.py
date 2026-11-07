import json
import os
import shutil
import subprocess
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Any, Tuple

from .emitter import TranslationItem, emit_monitor_verilog

@dataclass
class CheckResult:
    id: str
    text: str
    sva: Optional[str]
    status: str  # "PASS (proved)", "PASS (bounded)", "FAIL", "VACUOUS", "UNTRANSLATABLE", "ERROR"
    vcd_path: Optional[str] = None
    elapsed_seconds: float = 0.0
    notes: Optional[str] = None


def get_module_ports(top: str, rtl_file: str) -> Dict[str, Dict[str, Any]]:
    """Inspects RTL ports using Yosys JSON output."""
    cmd = [
        "yosys", "-q", "-p",
        f"read_verilog -sv {rtl_file}; hierarchy -top {top}; proc; write_json -"
    ]
    out = subprocess.check_output(cmd, text=True)
    data = json.loads(out)
    return data["modules"][top]["ports"]


def generate_formal_wrapper(
    top: str,
    rtl_file: str,
    clk_name: str,
    rst_name: str,
    monitor_code: str,
    wrapper_name: str = "formal_wrapper",
) -> str:
    """Generates a formal verification wrapper with free inputs and a 3-cycle reset."""
    ports = get_module_ports(top, rtl_file)

    lines: List[str] = [
        f"// Formal verification wrapper for {top}",
        f"module {wrapper_name} (",
        f"    input wire {clk_name}",
        ");",
        "",
        "    // Initial reset generator (held high for first 3 cycles)",
        "    reg [2:0] reset_cnt = 3'd0;",
        f"    reg {rst_name} = 1'b1;",
        f"    always @(posedge {clk_name}) begin",
        "        if (reset_cnt < 3'd3) begin",
        "            reset_cnt <= reset_cnt + 3'd1;",
        f"            {rst_name} <= 1'b1;",
        "        end else begin",
        f"            {rst_name} <= 1'b0;",
        "        end",
        "    end",
        "",
        "    // DUT port connections and signals",
    ]

    dut_connections: List[str] = []

    for pname, pinfo in ports.items():
        width = len(pinfo["bits"])
        bus_str = f"[{width-1}:0] " if width > 1 else ""
        if pname in (clk_name, rst_name):
            dut_connections.append(f".{pname}({pname})")
        else:
            lines.append(f"    wire {bus_str}{pname};")
            dut_connections.append(f".{pname}({pname})")

    lines.append("")
    lines.append(f"    // Instantiate DUT ({top})")
    lines.append(f"    {top} dut (")
    lines.append("        " + ",\n        ".join(dut_connections))
    lines.append("    );")
    lines.append("")
    lines.append("    // Monitor assertions / cover")
    for mline in monitor_code.splitlines():
        lines.append("    " + mline)
    lines.append("")
    lines.append("endmodule")

    return "\n".join(lines)


def run_sby_task(
    work_dir: str,
    task_name: str,
    mode: str,
    wrapper_file: str,
    rtl_files: List[str],
    top_module: str,
    depth: int = 20,
    timeout_sec: int = 120,
) -> Tuple[int, str, Optional[str]]:
    """Runs an SBY task in the specified directory. Returns (returncode, log, vcd_path)."""
    task_dir = os.path.join(work_dir, task_name)
    sby_file = os.path.join(work_dir, f"{task_name}.sby")

    # Clean existing task directory
    if os.path.exists(task_dir):
        shutil.rmtree(task_dir)

    all_read_cmds = [f"read_verilog -formal -sv {os.path.abspath(f)}" for f in rtl_files]
    all_read_cmds.append(f"read_verilog -formal -sv {os.path.abspath(wrapper_file)}")
    read_script = "\n".join(all_read_cmds)

    sby_content = f"""[options]
mode {mode}
depth {depth}

[engines]
smtbmc yices

[script]
{read_script}
prep -top {top_module}

"""
    with open(sby_file, "w") as f:
        f.write(sby_content)

    t0 = time.time()
    try:
        proc = subprocess.run(
            ["sby", "-f", f"{task_name}.sby"],
            cwd=work_dir,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
        )
        retcode = proc.returncode
        log = proc.stdout + "\n" + proc.stderr
    except subprocess.TimeoutExpired:
        retcode = -1
        log = f"Timed out after {timeout_sec} seconds"

    vcd_path = None
    # Look for trace VCD
    possible_vcds = [
        os.path.join(task_dir, "engine_0", "trace.vcd"),
        os.path.join(task_dir, "engine_0", "trace0.vcd"),
        os.path.join(task_dir, "engine_0", "trace_induct.vcd"),
    ]
    for p in possible_vcds:
        if os.path.exists(p):
            vcd_path = p
            break

    return retcode, log, vcd_path


def check_property(
    item: TranslationItem,
    design_config: Dict[str, Any],
    rtl_files: List[str],
    work_dir: str,
    depth: int = 20,
    timeout_sec: int = 120,
) -> CheckResult:
    """Checks a single property on the given design variant."""
    t_start = time.time()

    if item.status == "UNTRANSLATABLE":
        return CheckResult(
            id=item.id,
            text=item.text,
            sva=None,
            status="UNTRANSLATABLE",
            notes=item.error_message,
        )

    if item.status == "ERROR":
        return CheckResult(
            id=item.id,
            text=item.text,
            sva=None,
            status="ERROR",
            notes=item.error_message,
        )

    top = design_config["top"]
    clk = design_config.get("clock", "clk")
    rst_info = design_config.get("reset", {})
    rst_name = rst_info.get("name", "rst") if isinstance(rst_info, dict) else "rst"
    effective_depth = design_config.get("depth", depth)

    os.makedirs(work_dir, exist_ok=True)

    # 1. Check antecedent reachability (vacuity check) if property has an antecedent
    if item.antecedent and item.kind in ("implication", "next_cycle", "within_n_cycles", "stay_at_when"):
        cover_monitor = emit_monitor_verilog(item, design_config, check_assert=False, check_cover=True)
        cover_wrapper = generate_formal_wrapper(top, rtl_files[0], clk, rst_name, cover_monitor, "wrapper_cover")
        wrapper_path = os.path.join(work_dir, f"wrapper_cover_{item.id}.v")
        with open(wrapper_path, "w") as f:
            f.write(cover_wrapper)

        cov_ret, cov_log, _ = run_sby_task(
            work_dir=work_dir,
            task_name=f"cov_{item.id}",
            mode="cover",
            wrapper_file=wrapper_path,
            rtl_files=rtl_files,
            top_module="wrapper_cover",
            depth=effective_depth,
            timeout_sec=timeout_sec,
        )
        if cov_ret != 0:
            # Antecedent cover was never hit within bounded depth
            elapsed = time.time() - t_start
            return CheckResult(
                id=item.id,
                text=item.text,
                sva=item.sva,
                status="VACUOUS",
                elapsed_seconds=elapsed,
                notes="Antecedent cover condition was not reached within depth limit",
            )

    # 2. Check assertion via BMC
    assert_monitor = emit_monitor_verilog(item, design_config, check_assert=True, check_cover=False)
    assert_wrapper = generate_formal_wrapper(top, rtl_files[0], clk, rst_name, assert_monitor, "wrapper_bmc")
    wrapper_path = os.path.join(work_dir, f"wrapper_bmc_{item.id}.v")
    with open(wrapper_path, "w") as f:
        f.write(assert_wrapper)

    bmc_ret, bmc_log, vcd = run_sby_task(
        work_dir=work_dir,
        task_name=f"bmc_{item.id}",
        mode="bmc",
        wrapper_file=wrapper_path,
        rtl_files=rtl_files,
        top_module="wrapper_bmc",
        depth=effective_depth,
        timeout_sec=timeout_sec,
    )

    if bmc_ret != 0:
        elapsed = time.time() - t_start
        if bmc_ret == 2:
            return CheckResult(
                id=item.id,
                text=item.text,
                sva=item.sva,
                status="FAIL",
                vcd_path=vcd,
                elapsed_seconds=elapsed,
                notes="Assertion violated during BMC",
            )
        elif bmc_ret == -1:
            return CheckResult(
                id=item.id,
                text=item.text,
                sva=item.sva,
                status="TIMEOUT",
                elapsed_seconds=elapsed,
                notes=f"BMC timed out after {timeout_sec}s",
            )
        else:
            return CheckResult(
                id=item.id,
                text=item.text,
                sva=item.sva,
                status="ERROR",
                elapsed_seconds=elapsed,
                notes=f"SBY BMC returned error code {bmc_ret}",
            )

    # 3. BMC passed -> try prove (k-induction)
    prove_ret, prove_log, _ = run_sby_task(
        work_dir=work_dir,
        task_name=f"prove_{item.id}",
        mode="prove",
        wrapper_file=wrapper_path,
        rtl_files=rtl_files,
        top_module="wrapper_bmc",
        depth=effective_depth,
        timeout_sec=timeout_sec,
    )

    elapsed = time.time() - t_start
    if prove_ret == 0:
        status_str = "PASS (proved)"
    else:
        status_str = "PASS (bounded)"

    return CheckResult(
        id=item.id,
        text=item.text,
        sva=item.sva,
        status=status_str,
        elapsed_seconds=elapsed,
    )
