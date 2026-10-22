#!/usr/bin/env python3
"""Morning Scroll batch job: verify.py

Standalone live check: download every file in a publish manifest from
the live GitHub Pages site and compare md5 + size against the manifest.
Also checks the live PDF's page count (PyMuPDF) against the manifest
"pages:" value, and that the number of reader page PNGs in the manifest
equals that page count.

Manifest selection (fix round 2026-10-17, Q1): an explicit DATE or
--manifest wins. With neither, the manifest is picked BY EDITION DATE —
today's date in America/Phoenix — never by file-modification time. A
missing manifest for today is a loud FAIL, not a silent skip. Runs with
no DATE and no --manifest are "clock runs" (the 06:10 systemd timer):
they also write batch/logs/clock-verify-<date>.txt holding the verdict,
so the morning briefing can quote the clock verdict and a FAIL can
never live only in a log file.

Retries (Q2): GitHub Pages can lag 5-15 minutes after an upload, so a
failed attempt is retried on a span of about 15 minutes by default
(waits of 300s then 600s = 3 attempts). Override with --retry-waits
(comma-separated seconds) for tests. On a final FAIL the output states
the next step in plain words.

The full log is always written to
batch/logs/verify-<manifest-date>-<YYYYMMDD-HHMMSS>.log and printed to
stdout. Exit 0 on PASS, 1 on FAIL.

With --mirror and a PASS verdict, also copy the manifest's files from
publish-upload/ into the backup mirror and re-hash the mirror copies.

No AI judgment inside.

Usage:
  venv/bin/python batch/verify.py [DATE] [--manifest PATH] [--mirror]
                                  [--retry-waits 300,600]
"""
import argparse
import hashlib
import re
import shutil
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
BATCH_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = ROOT / "publish-upload"
MIRROR_DIR = Path.home() / "workspace" / "BACKUP-github-websites-only" / "morning-scroll"
SITE_BASE = "https://claypnw.github.io/morning-scroll"
PHOENIX = ZoneInfo("America/Phoenix")
ENTRY_RE = re.compile(r"^([0-9a-f]{32})\s+(\d+)\s+(\S+)$")

LOG_LINES = []
LOG_START = datetime.now()


# --- Shared error program (standards wiring step A, 2026-10-21) -------------
# The one shared error program is ~/workspace/batch/shared_error.py.
# Errors this program reports go there, and the standard processing —
# write the error down in full in the dated error record, open an ERROR
# line in the completion pile, hand back STOP — happens in that one
# program, never in code copied here. This block is only the call:
# locate the program, pass the error in, branch on what comes back.
# If the shared error program cannot be loaded or cannot record, the
# report prints a loud line on stderr and this program's own output,
# dated log, verdict lines, and exit code are unchanged.
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


# --- Start and finish records (standards wiring step B, 2026-10-21) --------
# This program writes a start line when it begins and a finish line
# when it ends well, both through the one shared finish-line writer,
# ~/workspace/work-launcher/write_finish_line.py — the same writer the
# morning jobs write their finish lines through, called the same way.
# A run that fails writes no finish line: its error goes to the one
# shared error program (the block above), and the pile carries the
# ERROR line instead. These calls are records only: they never change
# this program's own output, dated log, verdict lines, or exit code,
# and a failed record write prints a loud line on stderr.
import subprocess as _subprocess
from datetime import datetime as _datetime
from pathlib import Path as _Path
from zoneinfo import ZoneInfo as _ZoneInfo


def _finish_writer_path():
    for parent in _Path(__file__).resolve().parents:
        candidate = parent / "work-launcher" / "write_finish_line.py"
        if candidate.is_file():
            return candidate
    return None


_FINISH_WRITER = _finish_writer_path()


def _write_pile_line(mode, result, rests_on):
    """Write one start or finish line through the shared writer."""
    if _FINISH_WRITER is None:
        print("FINISH-LINE WRITER UNAVAILABLE — record line not written",
              file=sys.stderr)
        return
    try:
        proc = _subprocess.run(
            [sys.executable, str(_FINISH_WRITER), mode,
             _Path(__file__).name,
             _datetime.now(_ZoneInfo("America/Phoenix")).strftime("%Y-%m-%d"),
             result, rests_on],
            check=False, capture_output=True, text=True)
    except Exception as exc:
        print(f"FINISH-LINE WRITER FAILED — record line not written: {exc}",
              file=sys.stderr)
        return
    if proc.returncode != 0:
        detail = (proc.stdout or "").strip() or (proc.stderr or "").strip()
        print(f"FINISH-LINE WRITER STOPPED — record line not written: {detail}",
              file=sys.stderr)


def _write_start_line():
    _write_pile_line("start", "run started", "this run's own output")


def _write_finish_line(result, rests_on):
    _write_pile_line("finish", result, rests_on)


def log(message=""):
    print(message, flush=True)
    LOG_LINES.append(message)


def write_log(manifest_date):
    logs_dir = BATCH_DIR / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    stamp = LOG_START.strftime("%Y%m%d-%H%M%S")
    path = logs_dir / f"verify-{manifest_date}-{stamp}.log"
    path.write_text("\n".join(LOG_LINES) + "\n", encoding="utf-8")
    print(f"log written: {path}")
    return path


def write_clock_verdict(manifest_date, verdict, log_path):
    """Clock runs only: a small dated file the morning briefing quotes."""
    logs_dir = BATCH_DIR / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    path = logs_dir / f"clock-verify-{manifest_date}.txt"
    stamp = datetime.now(PHOENIX).isoformat(timespec="seconds")
    path.write_text(
        f"date: {manifest_date}\n"
        f"run: {stamp} (America/Phoenix)\n"
        f"VERDICT: {verdict}\n"
        f"log: {log_path}\n",
        encoding="utf-8",
    )
    print(f"clock verdict written: {path}")
    return path


def parse_manifest(path):
    meta = {}
    entries = []
    for line in path.read_text(encoding="utf-8").splitlines():
        m = ENTRY_RE.match(line.strip())
        if m:
            entries.append((m.group(3), m.group(1), int(m.group(2))))
        elif ":" in line and not line.startswith("#"):
            key, _, value = line.partition(":")
            meta[key.strip()] = value.strip()
    return meta, entries


def pick_manifest(args):
    """Returns (path, clock_mode). Selection is by edition date only."""
    if args.manifest:
        return Path(args.manifest).expanduser(), False
    if args.date:
        return BATCH_DIR / f"manifest-{args.date}.txt", False
    today = datetime.now(PHOENIX).strftime("%Y-%m-%d")
    return BATCH_DIR / f"manifest-{today}.txt", True


def download(url, name):
    """One file, with one retry after a short wait (review fix Q5).

    A single transient timeout through the egress proxy must not fail a
    whole attempt — observed 2026-10-17: index.html timed out once at
    60s while the other 7 files passed seconds later. So: 90s timeout,
    and on any download error wait 15 seconds and try the file once more
    before calling it a failure.
    """
    last_exc = None
    for try_no in (1, 2):
        try:
            with urllib.request.urlopen(url, timeout=90) as resp:
                return resp.read()
        except Exception as exc:
            last_exc = exc
            if try_no == 1:
                log(f"download of {name} failed ({exc}); waiting 15 seconds and retrying the file once")
                time.sleep(15)
    raise last_exc


def run_attempt(attempt_no, entries, want_pages, pdf_name):
    """Returns (ok, download_errors, mismatches, count_mismatches).

    The kinds stay separate so the final wording can tell apart: a check
    that could not download (network), a live file that truly differs
    (md5/size), and a page-count disagreement. A page-count disagreement
    is NOT a site mismatch: when the PDF's md5 matches the manifest, the
    file is byte-identical to the build, so a wrong count can only be a
    wrong number in the manifest itself.
    """
    log(f"--- attempt {attempt_no} ---")
    ts = int(time.time())
    ok = True
    download_errors = 0
    mismatches = 0
    count_mismatches = 0
    pdf_bytes = None
    for name, want_md5, want_size in entries:
        url = f"{SITE_BASE}/{name}?v=verify{ts}"
        try:
            data = download(url, name)
        except Exception as exc:
            log(f"FAIL {name} download error: {exc}")
            ok = False
            download_errors += 1
            continue
        got_md5 = hashlib.md5(data).hexdigest()
        if got_md5 == want_md5 and len(data) == want_size:
            # Print BOTH md5s on a PASS: the morning briefing quotes the
            # checksum pair verbatim from this log, so the live md5 must
            # be in the log, not just inferred from the word PASS.
            log(f"PASS {name} live md5 {got_md5} == manifest md5 {want_md5}")
        else:
            log(f"FAIL {name} expected md5 {want_md5} got {got_md5} "
                f"(expected size {want_size} got {len(data)})")
            ok = False
            mismatches += 1
        if name == pdf_name:
            pdf_bytes = data
    if pdf_bytes is None:
        log("FAIL pdf-page-count (PDF did not download)")
        ok = False
        download_errors += 1
    else:
        try:
            import fitz
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            got_pages = doc.page_count
            doc.close()
        except Exception as exc:
            log(f"FAIL pdf-page-count (could not open downloaded PDF: {exc})")
            ok = False
            mismatches += 1
        else:
            if got_pages == want_pages:
                log(f"PASS pdf-page-count ({got_pages} pages)")
            else:
                log(f"FAIL pdf-page-count expected {want_pages} got {got_pages}")
                ok = False
                count_mismatches += 1
    log(f"attempt {attempt_no}: {'PASS' if ok else 'FAIL'}")
    return ok, download_errors, mismatches, count_mismatches


def main():
    _write_start_line()
    parser = argparse.ArgumentParser(description="Verify the live Morning Scroll site against a publish manifest.")
    parser.add_argument("date", nargs="?", default=None, help="Edition date, YYYY-MM-DD (optional)")
    parser.add_argument("--manifest", default=None, help="Manifest path (overrides DATE / today's-manifest selection)")
    parser.add_argument("--mirror", action="store_true",
                        help="On PASS, copy the manifest files into the backup mirror and re-hash them")
    parser.add_argument("--retry-waits", default="300,600",
                        help="Comma-separated seconds to wait before each retry "
                             "(default 300,600: attempts span about 15 minutes, "
                             "matching the runbook's GitHub Pages lag window)")
    args = parser.parse_args()
    try:
        retry_waits = [int(x) for x in args.retry_waits.split(",") if x.strip() != ""]
    except ValueError:
        print(f"ERROR: bad --retry-waits {args.retry_waits!r} (want comma-separated seconds)")
        return 1

    clock_mode = not args.date and not args.manifest
    fallback_date = args.date or datetime.now(PHOENIX).strftime("%Y-%m-%d")
    manifest_path, _ = pick_manifest(args)
    if manifest_path is None or not manifest_path.is_file():
        log(f"ERROR: manifest not found ({manifest_path})")
        log("VERDICT: FAIL")
        if clock_mode:
            log_path = write_log(fallback_date)
            write_clock_verdict(fallback_date, "FAIL", log_path)
        else:
            write_log(fallback_date)
        _report_to_shared_error(
            "read manifest", f"manifest not found ({manifest_path})",
            kind="foreseen")
        return 1
    meta, entries = parse_manifest(manifest_path)
    manifest_date = meta.get("date", fallback_date)
    if not entries:
        log(f"ERROR: no file entries in {manifest_path}")
        log("VERDICT: FAIL")
        log_path = write_log(manifest_date)
        if clock_mode:
            write_clock_verdict(manifest_date, "FAIL", log_path)
        _report_to_shared_error(
            "read manifest", f"no file entries in {manifest_path}",
            kind="foreseen")
        return 1
    try:
        want_pages = int(meta.get("pages", "0"))
    except ValueError:
        want_pages = 0
    pdf_names = [name for name, _, _ in entries if name.endswith(".pdf")]
    pdf_name = pdf_names[0] if pdf_names else None

    log(f"verify: manifest {manifest_path}")
    log(f"verify: date {manifest_date}, {len(entries)} files, expected pages {want_pages}")
    log(f"verify: site {SITE_BASE}")
    log(f"verify: mode {'clock (today by edition date)' if clock_mode else 'explicit'}")

    # Reader page count cross-check (Q6): manifest PNG entries must equal
    # the edition's page count, same number the PDF check uses.
    png_entries = [name for name, _, _ in entries if name.endswith(".png")]
    counts_ok = len(png_entries) == want_pages and want_pages > 0
    if counts_ok:
        log(f"PASS reader-page-count ({len(png_entries)} page PNGs in manifest == {want_pages} pages)")
    else:
        log(f"FAIL reader-page-count ({len(png_entries)} page PNGs in manifest != {want_pages} pages)")

    verdict_ok, last_dl_errors, last_mismatches, last_count = run_attempt(1, entries, want_pages, pdf_name)
    verdict_ok = counts_ok and verdict_ok
    attempt_no = 1
    if not counts_ok:
        log("not retrying: the reader-page-count failure is inside the manifest itself — "
            "waiting for Pages cannot change it")
    local_only = counts_ok and last_mismatches == 0 and last_dl_errors == 0 and last_count > 0
    if local_only:
        log("not retrying: the only failure is the manifest's stated page count — "
            "waiting for Pages cannot change it")
    for wait in retry_waits:
        if verdict_ok or not counts_ok or local_only:
            break
        attempt_no += 1
        log(f"attempt {attempt_no - 1} failed; GitHub Pages can lag 5-15 minutes after an upload — "
            f"waiting {wait} seconds and retrying the whole check")
        time.sleep(wait)
        verdict_ok, last_dl_errors, last_mismatches, last_count = run_attempt(attempt_no, entries, want_pages, pdf_name)
        verdict_ok = counts_ok and verdict_ok

    log(f"VERDICT: {'PASS' if verdict_ok else 'FAIL'}")
    if not verdict_ok:
        if last_mismatches > 0:
            log("NEXT STEP: the live site does not match the manifest above. "
                "Wait for GitHub Pages to finish (it can lag 5-15 minutes), then re-run: "
                f"run_chain.sh --finish {manifest_date}. "
                "If it still fails, check in the repo that the upload landed on branch main, "
                "and re-upload ONLY the files marked FAIL above — never the whole bundle blindly.")
        elif not counts_ok or last_count > 0:
            # The manifest's page numbers disagree with the manifest's own
            # PNG list and/or with the built PDF's real page count, while
            # every live file's md5 matched. No upload or re-run of
            # --finish can fix that; the manifest must be rebuilt.
            log("NEXT STEP: the MANIFEST itself is inconsistent — its stated page count "
                "does not match its own reader-page PNG list and/or the PDF's real page "
                "count (see the page-count lines above), while the live files themselves "
                "matched their checksums. Rebuild the manifest by re-running "
                f"the build step (run_chain.sh {manifest_date} up to the GATE, checking the "
                "build log), then re-run "
                f"run_chain.sh --finish {manifest_date}. Re-uploading files cannot fix this.")
        else:
            # Every failure was a download that never arrived — that is a
            # CHECK failure (network/proxy), not proof the site is wrong.
            log("NEXT STEP: this check could not download the live files "
                "(network or proxy timeouts — see the FAIL lines above). That is a failure "
                "of the CHECK, not proof that the site is wrong: no live file was shown to "
                f"differ from the manifest. Re-run when the network settles: "
                f"run_chain.sh --finish {manifest_date}.")
    exit_code = 0 if verdict_ok else 1
    mirror_failed = False

    if args.mirror and verdict_ok:
        MIRROR_DIR.mkdir(parents=True, exist_ok=True)
        mirror_ok = True
        copied = 0
        for name, want_md5, want_size in entries:
            src = UPLOAD_DIR / name
            dest = MIRROR_DIR / name
            if not src.is_file():
                log(f"MIRROR FAIL {name} missing from {UPLOAD_DIR}")
                mirror_ok = False
                continue
            # Hash the SOURCE before anything is copied (review fix Q3):
            # a source that does not match the manifest must never
            # overwrite the good mirror copy.
            h = hashlib.md5()
            with open(src, "rb") as fh:
                for chunk in iter(lambda: fh.read(1024 * 1024), b""):
                    h.update(chunk)
            if h.hexdigest() != want_md5 or src.stat().st_size != want_size:
                log(f"MIRROR FAIL {name} source in publish-upload does not match the manifest "
                    f"(md5 {h.hexdigest()} size {src.stat().st_size} != md5 {want_md5} size {want_size}); "
                    f"mirror copy left untouched")
                mirror_ok = False
                continue
            shutil.copyfile(src, dest)
            copied += 1
            h2 = hashlib.md5()
            with open(dest, "rb") as fh:
                for chunk in iter(lambda: fh.read(1024 * 1024), b""):
                    h2.update(chunk)
            if h2.hexdigest() != want_md5 or dest.stat().st_size != want_size:
                log(f"MIRROR FAIL {name} mirror copy md5 {h2.hexdigest()} size {dest.stat().st_size} "
                    f"!= manifest md5 {want_md5} size {want_size}")
                mirror_ok = False
        log(f"MIRROR: {'PASS' if mirror_ok else 'FAIL'} ({copied} files copied to {MIRROR_DIR})")
        if not mirror_ok:
            mirror_failed = True
            exit_code = 1
    elif args.mirror:
        log("MIRROR: SKIPPED (verdict was FAIL)")

    if exit_code != 0:
        # A failed verdict opens an error record in the one shared
        # error program. The dated log and the verdict lines above are
        # unchanged — they are the evidence reports quote.
        if not verdict_ok:
            _report_to_shared_error(
                "verify live site",
                f"VERDICT: FAIL for {manifest_date} — download errors "
                f"{last_dl_errors}, file mismatches {last_mismatches}, "
                f"page-count mismatches {last_count}, reader-page-count "
                f"ok: {counts_ok} (see the verify log)",
                kind="check_failed")
        elif mirror_failed:
            _report_to_shared_error(
                "mirror refresh",
                f"MIRROR: FAIL for {manifest_date} — one or more mirror "
                f"copies did not match the manifest (see the verify log)",
                kind="check_failed")

    log_path = write_log(manifest_date)
    if clock_mode:
        write_clock_verdict(manifest_date, "PASS" if exit_code == 0 else "FAIL", log_path)
    if exit_code == 0:
        _write_finish_line("VERDICT: PASS", str(log_path))
    return exit_code


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
