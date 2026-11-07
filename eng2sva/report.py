import json
import os
from typing import Dict, List, Any
from .checker import CheckResult

def generate_design_reports(
    design_name: str,
    correct_results: List[CheckResult],
    buggy_results: List[CheckResult],
    out_dir: str,
) -> Dict[str, Any]:
    """Generates results.json and report.md for a design comparing correct and buggy variants."""
    os.makedirs(out_dir, exist_ok=True)

    combined_rows = []
    kill_list = []

    buggy_map = {r.id: r for r in buggy_results}

    for corr in correct_results:
        buggy = buggy_map.get(corr.id)
        buggy_status = buggy.status if buggy else "N/A"
        total_time = corr.elapsed_seconds + (buggy.elapsed_seconds if buggy else 0.0)

        # Bug is caught if correct RTL passed (or bounded) and buggy RTL failed!
        caught = ("PASS" in corr.status) and (buggy_status == "FAIL")
        if caught:
            kill_list.append(corr.id)

        row = {
            "id": corr.id,
            "text": corr.text,
            "sva": corr.sva,
            "correct_status": corr.status,
            "buggy_status": buggy_status,
            "vcd_path": buggy.vcd_path if (buggy and buggy.vcd_path) else corr.vcd_path,
            "time_sec": round(total_time, 3),
            "caught_bug": caught,
        }
        combined_rows.append(row)

    report_data = {
        "design": design_name,
        "properties": combined_rows,
        "bug_caught": len(kill_list) > 0,
        "killing_properties": kill_list,
        "specification_gap": len(kill_list) == 0,
    }

    # Write results.json
    json_path = os.path.join(out_dir, "results.json")
    with open(json_path, "w") as f:
        json.dump(report_data, f, indent=2)

    # Write report.md
    md_lines = [
        f"# Formal Verification Report: `{design_name}`",
        "",
        "## Summary",
        f"- **Bug Detected / Killed**: {'**YES** (' + ', '.join(kill_list) + ')' if kill_list else '**NO (Specification Gap Detected!)**'}",
        "",
        "## Property Verification Results",
        "",
        "| ID | English Requirement | SVA | Correct RTL | Buggy RTL | Time (s) |",
        "| :--- | :--- | :--- | :--- | :--- | :--- |",
    ]

    for r in combined_rows:
        sva_escaped = f"`{r['sva']}`" if r['sva'] else "*N/A*"
        # replace vertical bars in table for markdown
        sva_escaped = sva_escaped.replace("|", "\\|")
        text_escaped = r['text'].replace("|", "\\|")
        md_lines.append(
            f"| **{r['id']}** | {text_escaped} | {sva_escaped} | {r['correct_status']} | {r['buggy_status']} | {r['time_sec']:.2f} |"
        )

    md_lines.append("")
    md_lines.append("## Counterexample Traces")
    traces_found = False
    for r in combined_rows:
        if r["buggy_status"] == "FAIL" and r["vcd_path"]:
            traces_found = True
            md_lines.append(f"- Property `{r['id']}` failed on buggy RTL: `{r['vcd_path']}`")
    if not traces_found:
        md_lines.append("- No counterexamples generated.")
    md_lines.append("")

    md_path = os.path.join(out_dir, "report.md")
    with open(md_path, "w") as f:
        f.write("\n".join(md_lines))

    return report_data
