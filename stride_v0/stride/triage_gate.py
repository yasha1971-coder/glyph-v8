#!/usr/bin/env python3
"""triage_gate.py — CIV triage gate: read state files, print one-line verdict.

Verdict priority (highest first):
  STOPPED_BY_USER   — STOP_BY_USER.flag exists
  LOCK_BY_GOV       — LOCK_BY_GOV flag exists
  MASKED_SERVICE    — FORCE_LOCK or LOCK_BY_ANTIDRIFT flag exists
  NO_MICRO_EVENT    — latest_trinity_micro_event.json missing or empty
  MOVING            — all checks passed

Usage:
    python3 triage_gate.py
    python3 triage_gate.py --civ-dir CIV --flags-dir . --micro latest_trinity_micro_event.json
    python3 triage_gate.py --json
"""

import argparse
import json
import os
import sys
from collections import OrderedDict


FLAG_FILES = OrderedDict([
    ("STOP_BY_USER",     "STOP_BY_USER.flag"),
    ("FORCE_LOCK",       "FORCE_LOCK"),
    ("FORCE_ITERATE",    "FORCE_ITERATE"),
    ("LOCK_BY_ANTIDRIFT","LOCK_BY_ANTIDRIFT"),
    ("LOCK_BY_GOV",      "LOCK_BY_GOV"),
])


def read_json(path):
    if not os.path.isfile(path):
        return None
    try:
        with open(path, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def read_jsonl_tail(path, n=50):
    if not os.path.isfile(path):
        return []
    lines = []
    try:
        with open(path, 'r') as f:
            for line in f:
                line = line.strip()
                if line:
                    lines.append(line)
        tail = lines[-n:]
        parsed = []
        for l in tail:
            try:
                parsed.append(json.loads(l))
            except json.JSONDecodeError:
                pass
        return parsed
    except OSError:
        return []


def check_flag(flags_dir, filename):
    return os.path.isfile(os.path.join(flags_dir, filename))


def triage(civ_dir, flags_dir, micro_path):
    facts = OrderedDict()

    civ_state = read_json(os.path.join(civ_dir, "civ_state.json"))
    facts["civ_state_exists"] = civ_state is not None
    facts["civ_state"] = civ_state if civ_state else {}

    chronicle = read_jsonl_tail(os.path.join(civ_dir, "chronicle.jsonl"), 50)
    facts["chronicle_lines"] = len(chronicle)
    facts["chronicle_last"] = chronicle[-1] if chronicle else {}

    micro = read_json(micro_path)
    facts["micro_event_exists"] = micro is not None
    facts["micro_event"] = micro if micro else {}

    flags_present = OrderedDict()
    for name, fname in FLAG_FILES.items():
        flags_present[name] = check_flag(flags_dir, fname)
    facts["flags"] = flags_present

    if flags_present["STOP_BY_USER"]:
        verdict = "STOPPED_BY_USER"
    elif flags_present["LOCK_BY_GOV"]:
        verdict = "LOCK_BY_GOV"
    elif flags_present["FORCE_LOCK"] or flags_present["LOCK_BY_ANTIDRIFT"]:
        verdict = "MASKED_SERVICE"
    elif not facts["micro_event_exists"]:
        verdict = "NO_MICRO_EVENT"
    else:
        verdict = "MOVING"

    pass_table = OrderedDict([
        ("STOP_BY_USER.flag absent",    not flags_present["STOP_BY_USER"]),
        ("LOCK_BY_GOV absent",          not flags_present["LOCK_BY_GOV"]),
        ("FORCE_LOCK absent",           not flags_present["FORCE_LOCK"]),
        ("LOCK_BY_ANTIDRIFT absent",    not flags_present["LOCK_BY_ANTIDRIFT"]),
        ("micro_event exists",          facts["micro_event_exists"]),
        ("civ_state exists",            facts["civ_state_exists"]),
        ("chronicle has entries",       facts["chronicle_lines"] > 0),
    ])

    return verdict, facts, pass_table


def main():
    ap = argparse.ArgumentParser(description="CIV triage gate — one-line verdict")
    ap.add_argument("--civ-dir", default="CIV",
                    help="Directory with civ_state.json and chronicle.jsonl (default: CIV)")
    ap.add_argument("--flags-dir", default=".",
                    help="Directory where flag files live (default: .)")
    ap.add_argument("--micro", default="latest_trinity_micro_event.json",
                    help="Path to micro-event JSON (default: latest_trinity_micro_event.json)")
    ap.add_argument("--json", action="store_true",
                    help="Output full JSON report instead of one-line verdict")
    args = ap.parse_args()

    verdict, facts, pass_table = triage(args.civ_dir, args.flags_dir, args.micro)

    if args.json:
        report = OrderedDict([
            ("verdict", verdict),
            ("pass_table", pass_table),
            ("facts", facts),
        ])
        print(json.dumps(report, indent=2, ensure_ascii=False, default=str))
    else:
        print(verdict)
        print()
        all_pass = all(pass_table.values())
        print(f"{'Check':<30} {'Status':>8}")
        print("-" * 40)
        for check, ok in pass_table.items():
            mark = "PASS" if ok else "FAIL"
            print(f"{check:<30} {mark:>8}")
        print("-" * 40)
        print(f"{'GATE':.<30} {'PASS' if all_pass else 'FAIL':>8}")


if __name__ == "__main__":
    main()
