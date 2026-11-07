import argparse
import glob
import os
import sys
import yaml

from .emitter import translate_requirement, emit_concurrent_sva
from .parser import build_signal_dictionary
from .templates import TEMPLATES
from .checker import check_property
from .report import generate_design_reports

def cmd_translate(args):
    """Translates spec into SVA file (props.sv)."""
    with open(args.design) as f:
        design_cfg = yaml.safe_load(f)

    with open(args.spec) as f:
        spec_cfg = yaml.safe_load(f)

    design_dict = build_signal_dictionary(design_cfg)
    requirements = spec_cfg.get("requirements", [])
    if isinstance(spec_cfg, list):
        requirements = spec_cfg

    translated_items = []
    print(f"Translating {len(requirements)} requirements from {args.spec}...")
    for req in requirements:
        item = translate_requirement(req, design_dict, TEMPLATES)
        translated_items.append(item)
        if item.status == "TRANSLATED":
            print(f"  [{item.id}] TRANSLATED: {item.sva}")
        elif item.status == "UNTRANSLATABLE":
            print(f"  [{item.id}] UNTRANSLATABLE: {item.text}")
        else:
            print(f"  [{item.id}] ERROR: {item.error_message}")

    props_sv = emit_concurrent_sva(translated_items, design_cfg)

    out_path = args.out
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with open(out_path, "w") as f:
        f.write(props_sv)
    print(f"Wrote SVA properties to {out_path}\n")


def cmd_check(args):
    """Runs formal verification on correct and buggy design variants, producing results."""
    with open(args.design) as f:
        design_cfg = yaml.safe_load(f)

    with open(args.spec) as f:
        spec_cfg = yaml.safe_load(f)

    design_dict = build_signal_dictionary(design_cfg)
    requirements = spec_cfg.get("requirements", [])
    if isinstance(spec_cfg, list):
        requirements = spec_cfg

    items = [translate_requirement(req, design_dict, TEMPLATES) for req in requirements]

    out_dir = args.out or f"build/{design_cfg['top']}"
    os.makedirs(out_dir, exist_ok=True)

    # Emit props.sv
    props_sv = emit_concurrent_sva(items, design_cfg)
    with open(os.path.join(out_dir, "props.sv"), "w") as f:
        f.write(props_sv)

    correct_files = design_cfg.get("files", [])
    buggy_files = design_cfg.get("buggy_files", [])

    print(f"\n=======================================================")
    print(f"Checking Design: {design_cfg['top']}")
    print(f"=======================================================")

    correct_results = []
    print("\n--- Running Correct RTL Variant ---")
    corr_work = os.path.join(out_dir, "formal_correct")
    for item in items:
        res = check_property(item, design_cfg, correct_files, corr_work, depth=args.depth, timeout_sec=args.timeout)
        correct_results.append(res)
        print(f"  Property {res.id:8s}: {res.status:16s} ({res.elapsed_seconds:.2f}s)")

    buggy_results = []
    if buggy_files:
        print("\n--- Running Buggy RTL Variant ---")
        bug_work = os.path.join(out_dir, "formal_buggy")
        for item in items:
            res = check_property(item, design_cfg, buggy_files, bug_work, depth=args.depth, timeout_sec=args.timeout)
            buggy_results.append(res)
            print(f"  Property {res.id:8s}: {res.status:16s} ({res.elapsed_seconds:.2f}s)")

    rep = generate_design_reports(design_cfg["top"], correct_results, buggy_results, out_dir)
    print(f"\nReport written to {os.path.join(out_dir, 'report.md')}")
    print(f"JSON results written to {os.path.join(out_dir, 'results.json')}")
    if rep["bug_caught"]:
        print(f"Bug Caught by: {', '.join(rep['killing_properties'])}")
    else:
        print(f"WARNING: Specification Gap! Bug was not caught by any property.")
    return rep


def cmd_demo(args):
    """Runs demo across all designs and prints a consolidated summary kill table."""
    design_files = sorted(glob.glob("designs/*.yaml"))
    all_reports = []

    print("================================================================================")
    print("                    ENG2SVA FORMAL VERIFICATION DEMO                            ")
    print("================================================================================")

    for df in design_files:
        name = os.path.splitext(os.path.basename(df))[0]
        spec_file = f"specs/{name}.yaml"
        if not os.path.exists(spec_file):
            continue
        dummy_args = argparse.Namespace(
            design=df,
            spec=spec_file,
            out=f"build/{name}",
            depth=args.depth,
            timeout=args.timeout,
        )
        rep = cmd_check(dummy_args)
        all_reports.append(rep)

    # Consolidated Kill Table
    print("\n")
    print("================================================================================")
    print("                           CONSOLIDATED KILL TABLE                              ")
    print("================================================================================")
    print(f"{'Design':<15} | {'Bug Detected?':<15} | {'Killing Properties':<25} | {'Status'}")
    print("-" * 80)
    for rep in all_reports:
        des = rep["design"]
        caught = "YES" if rep["bug_caught"] else "NO"
        killers = ", ".join(rep["killing_properties"]) if rep["bug_caught"] else "NONE"
        status = "PASSED" if rep["bug_caught"] else "SPEC GAP"
        print(f"{des:<15} | {caught:<15} | {killers:<25} | {status}")
    print("================================================================================")


def main():
    parser = argparse.ArgumentParser(description="eng2sva: Controlled-English to SVA Translator & Checker")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # translate
    p_trans = subparsers.add_parser("translate", help="Translate English specs to SVA")
    p_trans.add_argument("--design", required=True, help="Path to design YAML")
    p_trans.add_argument("--spec", required=True, help="Path to spec YAML")
    p_trans.add_argument("--out", required=True, help="Path to output SVA file (props.sv)")

    # check
    p_check = subparsers.add_parser("check", help="Run formal verification with SBY")
    p_check.add_argument("--design", required=True, help="Path to design YAML")
    p_check.add_argument("--spec", required=True, help="Path to spec YAML")
    p_check.add_argument("--out", default=None, help="Output directory (default: build/<top>)")
    p_check.add_argument("--depth", type=int, default=20, help="BMC depth (default: 20)")
    p_check.add_argument("--timeout", type=int, default=120, help="Timeout in seconds (default: 120)")

    # demo
    p_demo = subparsers.add_parser("demo", help="Run full demo across all designs")
    p_demo.add_argument("--depth", type=int, default=20, help="BMC depth (default: 20)")
    p_demo.add_argument("--timeout", type=int, default=120, help="Timeout in seconds (default: 120)")

    args = parser.parse_args()
    if args.command == "translate":
        cmd_translate(args)
    elif args.command == "check":
        cmd_check(args)
    elif args.command == "demo":
        cmd_demo(args)

if __name__ == "__main__":
    main()
