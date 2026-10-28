#!/usr/bin/env python3
"""Morning Scroll batch job: publish.py

Bundle check + gate print for one edition.

The upload itself uses the admin's saved GitHub browser session per the
runbook (Step 6) — a plain program has no GitHub credential on this VM
and gh is not logged in. This program mechanizes everything except the
browser click: it checks publish-upload/ against batch/manifest-DATE.txt
(nothing more, nothing less than the manifest list) and, on success,
prints the exact browser-upload instruction block.

No AI judgment inside. Prints a plain log.

Usage:
  venv/bin/python batch/publish.py DATE
"""
import argparse
import calendar
import hashlib
import re
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BATCH_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = ROOT / "publish-upload"
UPDATED_FILES = ["index.html", "scroll-search-index.json"]
ENTRY_RE = re.compile(r"^([0-9a-f]{32})\s+(\d+)\s+(\S+)$")


# --- Shared error program (standards wiring step A, 2026-10-21) -------------
# The one shared error program is ~/workspace/batch/shared_error.py.
# Errors this program reports go there, and the standard processing —
# write the error down in full in the dated error record, open an ERROR
# line in the completion pile, hand back STOP — happens in that one
# program, never in code copied here. This block is only the call:
# locate the program, pass the error in, branch on what comes back.
# If the shared error program cannot be loaded or cannot record, the
# report prints a loud line on stderr and this program's own output and
# exit behavior are unchanged.
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


# The step this program is on, named for the shared error record.
# main() sets it at each phase boundary; fail() reports it.
_STEP = "start"


def fail(message, kind="foreseen"):
    """One failure path: print the ERROR line, hand the error to the one
    shared error program, and exit on the STOP it hands back (its exit
    code: 1, or 2 when the ERROR line could not be confirmed)."""
    print(f"ERROR: {message}")
    result = _report_to_shared_error(_STEP, message, kind=kind)
    sys.exit(result["exit_code"] if result else 1)


def md5_of(path):
    h = hashlib.md5()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    parser = argparse.ArgumentParser(description="Check the publish bundle against its manifest and print the upload gate.")
    parser.add_argument("date", help="Edition date, YYYY-MM-DD")
    args = parser.parse_args()
    global _STEP
    _STEP = "read arguments"
    date_str = args.date
    try:
        day = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        fail(f"bad date {date_str!r} (want YYYY-MM-DD)")

    _STEP = "read manifest"
    manifest_path = BATCH_DIR / f"manifest-{date_str}.txt"
    if not manifest_path.is_file():
        fail(f"missing manifest {manifest_path} (run build_and_manifest.py first)")
    print(f"input: manifest {manifest_path}")
    print(f"input: upload dir {UPLOAD_DIR}")

    entries = []
    for line in manifest_path.read_text(encoding="utf-8").splitlines():
        m = ENTRY_RE.match(line.strip())
        if m:
            entries.append((m.group(3), m.group(1), int(m.group(2))))
    if not entries:
        fail(f"no file entries found in {manifest_path}")

    _STEP = "bundle check"
    failures = 0
    for name, want_md5, want_size in entries:
        path = UPLOAD_DIR / name
        if not path.is_file():
            print(f"FAIL {name} missing from {UPLOAD_DIR}")
            failures += 1
            continue
        got_size = path.stat().st_size
        got_md5 = md5_of(path)
        if got_size == want_size and got_md5 == want_md5:
            print(f"OK {name} ({got_size} bytes, md5 {got_md5})")
        else:
            print(f"FAIL {name} expected md5 {want_md5} size {want_size}, got md5 {got_md5} size {got_size}")
            failures += 1
    # Extra files (Q7): anything in publish-upload/ that is NOT in the
    # manifest must be named out loud — an extra file riding along in the
    # upload would land on the site unrecorded. Stale dated files from
    # earlier editions are cleared by build_and_manifest.py at build
    # time, so an extra here is a real problem, not housekeeping.
    manifest_names = {name for name, _, _ in entries}
    extras = sorted(p.name for p in UPLOAD_DIR.iterdir() if p.is_file() and p.name not in manifest_names)
    for name in extras:
        print(f"EXTRA {name} is in {UPLOAD_DIR} but NOT in the manifest — it must not be uploaded")
    if extras:
        print(f"bundle check FAILED: {len(extras)} extra file(s) in publish-upload are not in the manifest; "
              f"move or delete them, then re-run")
        _report_to_shared_error(
            "bundle check",
            f"bundle check FAILED: {len(extras)} extra file(s) in publish-upload "
            f"are not in the manifest",
            kind="check_failed")
        return 1
    if failures:
        print(f"bundle check FAILED: {failures} of {len(entries)} files do not match the manifest")
        _report_to_shared_error(
            "bundle check",
            f"bundle check FAILED: {failures} of {len(entries)} files do not match the manifest",
            kind="check_failed")
        return 1
    print(f"bundle check passed: all {len(entries)} manifest files match, no extra files in publish-upload")

    vol = f"{day.year % 100:02d}{day.month:02d}"
    no = f"{day.day:02d}"
    commit_message = (f"Publish {calendar.month_abbr[day.month]} {day.day}, {day.year} "
                      f"edition (Vol. {vol}, No. {no})")
    new_names = [name for name, _, _ in entries if name not in UPDATED_FILES]

    # Roll-off moves (Clay's design, 2026-10-27): recordings past the
    # 45-day keep, named by the build in batch/rolloff-DATE.txt, are
    # never deleted into nothing — they move to the archive repository
    # (scroll-archive-1), which holds them from then on, and a tap on
    # an old paper plays them from the archive. The move command
    # prints with the upload list so the send step runs it together:
    # archive_move.py proves each archive copy stands (read back, same
    # size) before the file leaves the main repository, and a file
    # whose move fails is set aside — nothing is taken down unproven.
    rolloff_names = []
    rolloff_path = BATCH_DIR / f"rolloff-{date_str}.txt"
    if rolloff_path.is_file():
        rolloff_names = [ln.strip() for ln in
                         rolloff_path.read_text(encoding="utf-8").splitlines() if ln.strip()]

    print("")
    print("=== BROWSER UPLOAD INSTRUCTIONS (runbook Step 6) ===")
    print("Upload via the browser task (the admin's saved GitHub session) to https://github.com/claypnw/morning-scroll")
    print("")
    print("Updated files (2) — upload with 'Add file' > 'Upload files' (overwrites same-named files):")
    for name in UPDATED_FILES:
        print(f"  {UPLOAD_DIR / name}")
    print("")
    print(f"New files ({len(new_names)}) — upload with 'Add file' > 'Upload files':")
    for name in new_names:
        print(f"  {UPLOAD_DIR / name}")
    print("")
    if rolloff_names:
        print(f"Roll-off moves ({len(rolloff_names)}) — recordings past the 45-day keep "
              f"move to the archive repository in this same publish; run the move "
              f"program once for the whole list:")
        for name in rolloff_names:
            print(f"  moves: {name}")
        print(f"  archive_move.py --list {rolloff_path} --archive-repo scroll-archive-1 "
              f"--main-repo morning-scroll --mirror "
              f"{Path.home() / 'workspace' / 'BACKUP-github-websites-only' / 'morning-scroll'}")
        print("")
    print("Commit directly to main.")
    print(f"Commit message: {commit_message}")
    print("=====================================================")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except BaseException as exc:
        # Catch-all: an error this program did not foresee goes to the
        # one shared error program, then the program stops as it would
        # have — the traceback still prints.
        _report_to_shared_error(_STEP, exc, kind="unforeseen")
        raise
