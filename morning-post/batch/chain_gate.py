#!/usr/bin/env python3
"""Morning Scroll batch chain gate helper — chain_gate.py

Gate wiring for rules-to-gates queue items 99, 104, 105, 106
(2026-10-19). One helper for all four items so every gate in the
chain goes through the same record path:

  chain_gate.py ITEM DATE [--rule-log FILE] [--fetch-state FILE]
                          [--from-record FILE]

It builds that item's checker record from the chain's real state,
writes the record as JSON under batch/logs/, runs the shared gate
routine through
  ~/workspace/gate-builds/daily-jobs/daily_job_runner.py <record> <item>
prints the runner's verdict, and exits with the runner's exit code
(0 pass / 1 stop / 2 no verdict). Callers MUST branch on the exit
code: a stop blocks the work at that point in the chain.

Where each item's record facts come from (real state only — a field
with no real value is left empty/null, never invented):

  Item 99 (batch record): the chain's fixed instruction files in
    this directory plus PUBLISH-RUNBOOK.md; the printed rule log for
    this run (the --rule-log file, or the newest scroll rule log for
    the date in ~/workspace/batch/rule-logs/); the mechanical parts
    the chain programs actually run (build / publish / verify);
    judgment parts false (each chain program states "No AI judgment
    inside" — checked in the files, not assumed).
  Item 104 (fetch): the fetch-state file written by
    build_and_manifest.py at its published-check fetch, at the
    moment of the fetch, before the fetched data is used
    (batch/logs/fetch-state-DATE.json, or --fetch-state FILE).
    The state carries checksum_match as the real comparison of the
    fetched bytes' git blob SHA against the blob SHA in GitHub's
    repository contents listing for the same file (source added
    2026-10-19 — see the wiring log). With no fetch state on record
    the fetch section is empty and the checker stops
    ("fetch record missing").
  Item 105 (publish runbook): the step marks in this run's rule log
    for the run-phase steps (1 build_and_manifest,
    2 publish_bundle_check), read at the point the publish step's
    bundle check has passed.
  Item 106 (sign-off): the sign-off line file
    batch/logs/sign-off-DATE.txt holding three lines —
      cold_read_done: true
      date: YYYY-MM-DD
      edition: YYYY-MM-DD
    Absence of the file is the honest stop state: no recorded
    sign-off, no publish.

--from-record FILE is the proof path: FILE is a full checker record
(like good_record.json / bad_record.json in the gate folder); the
helper takes only that item's section from it and runs it through
the same record-writing + runner path as a real chain call.

No AI judgment inside. Prints a plain log.
"""
import argparse
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

BATCH_DIR = Path(__file__).resolve().parent
ROOT = BATCH_DIR.parent
LOGS_DIR = BATCH_DIR / "logs"
RULE_LOG_LIB = Path.home() / "workspace" / "batch" / "rule-logs"
RUNNER = Path.home() / "workspace" / "gate-builds" / "daily-jobs" / "daily_job_runner.py"
RUNBOOK = ROOT / "PUBLISH-RUNBOOK.md"
ITEMS = (99, 104, 105, 106)


# --- Shared error program (standards wiring step A, 2026-10-21) -------------
# The one shared error program is ~/workspace/batch/shared_error.py.
# An error this program did not foresee goes there, and the standard
# processing — write the error down in full in the dated error record,
# open an ERROR line in the completion pile, hand back STOP — happens
# in that one program, never in code copied here. This block is only
# the call. A gate STOP verdict returned in the normal way is the check
# working as designed: the caller records it in the run's rule log, so
# it does not open an error record here. If the shared error program
# cannot be loaded or cannot record, the report prints a loud line on
# stderr and this program's own output and exit code are unchanged.
def _load_shared_error():
    for parent in Path(__file__).resolve().parents:
        for candidate in (parent / "shared_error.py",
                          parent / "batch" / "shared_error.py"):
            if candidate.is_file():
                try:
                    if str(candidate.parent) not in sys.path:
                        sys.path.insert(0, str(candidate.parent))
                    from shared_error import report_error
                    return report_error
                except Exception:
                    # A shared error program that is present but
                    # fails to load is treated the same as one
                    # that cannot be found: fall back, never
                    # raise at startup.
                    continue
    return None


_shared_report_error = _load_shared_error()


def _report_to_shared_error(step, error, kind="foreseen"):
    """Send one error to the one shared error program. Never raises."""
    if _shared_report_error is None:
        print(f"SHARED ERROR PROGRAM UNAVAILABLE — error not recorded: {error}",
              file=sys.stderr)
        return None
    try:
        return _shared_report_error(
            program=Path(__file__).name, step=step, error=error, kind=kind,
            error_type="FailedVerdict" if kind == "check_failed" else None)
    except Exception as exc:
        print(f"SHARED ERROR PROGRAM FAILED — error not recorded: {exc}",
              file=sys.stderr)
        return None


def find_rule_log(date_str, given):
    if given:
        return Path(given).expanduser()
    cands = sorted(
        p for p in RULE_LOG_LIB.glob(f"scroll-rule-log-{date_str}-*.txt")
        if "FAILED" not in p.name
    )
    return cands[-1] if cands else None


def build_99(date_str, rule_log):
    instruction_files = [
        BATCH_DIR / "run_chain.sh",
        BATCH_DIR / "build_and_manifest.py",
        BATCH_DIR / "publish.py",
        BATCH_DIR / "verify.py",
        BATCH_DIR / "archive_update.py",
        RUNBOOK,
    ]
    fixed = all(p.is_file() and p.stat().st_size > 0 for p in instruction_files)
    runbook_text = RUNBOOK.read_text(encoding="utf-8") if RUNBOOK.is_file() else ""
    # The batch conversion was talked through before the build: the
    # runbook's BATCH CHAIN note records it as Clay's direction
    # (2026-10-17). Absence of that note would make this false.
    full_talk = "BATCH CHAIN" in runbook_text and "Clay's direction" in runbook_text
    mechanical = []
    if (BATCH_DIR / "build_and_manifest.py").is_file():
        mechanical.append("build")
    if (BATCH_DIR / "publish.py").is_file():
        mechanical.append("publish")
    if (BATCH_DIR / "verify.py").is_file():
        mechanical.append("verify")
    judgment_free = all(
        "No AI judgment" in p.read_text(encoding="utf-8", errors="ignore")
        for p in (BATCH_DIR / "build_and_manifest.py",
                  BATCH_DIR / "publish.py",
                  BATCH_DIR / "verify.py")
        if p.is_file()
    )
    # A change-without-Clay flag file is the chain's only record of an
    # unauthorized instruction change; none on record -> false.
    changed_flag = LOGS_DIR / f"batch-changed-without-clay-{date_str}.txt"
    return {
        "batch_instruction_set": (
            "fixed: run_chain.sh, build_and_manifest.py, publish.py, "
            "verify.py, archive_update.py, PUBLISH-RUNBOOK.md"
            if fixed else ""
        ),
        "batch_instructions_changed_without_clay": changed_flag.is_file(),
        "batch_log_present": bool(rule_log and Path(rule_log).is_file()),
        "full_talk_before_build": full_talk,
        "batch_mechanical_parts": mechanical,
        "batch_includes_judgment_parts": not judgment_free,
    }


def build_104(date_str, fetch_state_path):
    path = fetch_state_path or (LOGS_DIR / f"fetch-state-{date_str}.json")
    if path and Path(path).is_file():
        state = json.loads(Path(path).read_text(encoding="utf-8"))
        if isinstance(state, dict):
            return {"fetch": state}
    return {"fetch": {}}


def build_105(date_str, rule_log):
    steps = []
    if rule_log and Path(rule_log).is_file():
        last = {}
        label = {}
        for line in Path(rule_log).read_text(encoding="utf-8").splitlines():
            m = re.match(r"STEP (\d+) (\S+): DONE ([01])", line)
            if m:
                last[int(m.group(1))] = m.group(3) == "1"
                label[int(m.group(1))] = m.group(2)
        # Run-phase steps only: this gate sits at the end of the run
        # phase, where steps 1-2 are the publish runbook steps that
        # must stand done (steps 3-4 belong to --finish).
        for n in (1, 2):
            name = label.get(n, {1: "build_and_manifest",
                                  2: "publish_bundle_check"}[n])
            steps.append({"name": name, "done": bool(last.get(n, False))})
    return {
        "publish_run": {
            "publish_requested": True,
            "steps": steps,
            "runbook_order": [s["name"] for s in steps],
        }
    }


def build_106(date_str):
    signoff = {"cold_read_done": False, "date": "", "edition": ""}
    path = LOGS_DIR / f"sign-off-{date_str}.txt"
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            if ":" not in line:
                continue
            key, _, value = line.partition(":")
            key, value = key.strip().lower(), value.strip()
            if key == "cold_read_done":
                signoff["cold_read_done"] = value.lower() in ("true", "yes", "1", "done")
            elif key == "date":
                signoff["date"] = value
            elif key == "edition":
                signoff["edition"] = value
    return {
        "sign_off": signoff,
        "publish_run": {"publish_requested": True},
    }


def section_from_record(item, source):
    """Proof path: take only this item's section from a full record."""
    if item == 99:
        keys = ("batch_instruction_set", "batch_instructions_changed_without_clay",
                "batch_log_present", "full_talk_before_build",
                "batch_mechanical_parts", "batch_includes_judgment_parts")
        return {k: source.get(k) for k in keys}
    if item == 104:
        return {"fetch": source.get("fetch") or {}}
    if item == 105:
        return {"publish_run": source.get("publish_run") or {}}
    if item == 106:
        return {
            "sign_off": source.get("sign_off") or {},
            "publish_run": source.get("publish_run") or {},
        }
    return {}


def main():
    parser = argparse.ArgumentParser(
        description="Build one Morning Scroll gate record from the chain's real state and run the daily-jobs checker on it.")
    parser.add_argument("item", type=int, choices=ITEMS, help="Gate item number")
    parser.add_argument("date", help="Edition date, YYYY-MM-DD")
    parser.add_argument("--rule-log", default=None,
                        help="This run's rule log file (items 99 and 105)")
    parser.add_argument("--fetch-state", default=None,
                        help="Fetch-state JSON written at the fetch (item 104)")
    parser.add_argument("--from-record", default=None,
                        help="Proof path: full checker record JSON to take this item's section from")
    args = parser.parse_args()

    date_str = args.date
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        print(f"ERROR: bad date {date_str!r} (want YYYY-MM-DD)")
        return 2

    rule_log = find_rule_log(date_str, args.rule_log)
    if args.from_record:
        source = json.loads(Path(args.from_record).read_text(encoding="utf-8"))
        section = section_from_record(args.item, source)
        origin = f"section of {args.from_record}"
    elif args.item == 99:
        section = build_99(date_str, rule_log)
        origin = "chain real state (instruction files + rule log)"
    elif args.item == 104:
        section = build_104(date_str, Path(args.fetch_state) if args.fetch_state else None)
        origin = "fetch state written at the published-check fetch"
    elif args.item == 105:
        section = build_105(date_str, rule_log)
        origin = "chain real state (this run's rule log, run-phase steps)"
    else:
        section = build_106(date_str)
        origin = f"sign-off line file {LOGS_DIR / f'sign-off-{date_str}.txt'}"

    record = {"record_name": f"scroll-chain-gate-{args.item}-{date_str}"}
    record.update(section)

    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%H%M%S")
    record_path = LOGS_DIR / f"gate-record-{args.item}-{date_str}-{stamp}.json"
    n = 1
    while record_path.exists():
        n += 1
        record_path = LOGS_DIR / f"gate-record-{args.item}-{date_str}-{stamp}-{n}.json"
    record_path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(f"gate item {args.item} for {date_str}: record from {origin}")
    print(f"gate record: {record_path}")
    print(f"gate record contents: {json.dumps(record)}")

    result = subprocess.run(
        [sys.executable, str(RUNNER), str(record_path), str(args.item)],
        capture_output=True, text=True)
    sys.stdout.write(result.stdout)
    sys.stderr.write(result.stderr)
    print(f"gate item {args.item} exit: {result.returncode}")
    return result.returncode


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except BaseException as exc:
        # Catch-all: an error this program did not foresee goes to the
        # one shared error program, then the program stops as it would
        # have — the traceback still prints.
        _report_to_shared_error("main", exc, kind="unforeseen")
        raise
