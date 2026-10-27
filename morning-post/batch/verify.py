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
import base64
import hashlib
import http.client
import json
import os
import re
import shutil
import ssl
import sys
import time
import urllib.parse
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


def voice_and_rolloff_lines(manifest_date):
    """The voice lines verify reads into the morning record: the notes
    the build wrote for this date (batch/voice-notes-DATE.txt — a
    recording that failed, landed on retry, or stalled), the loud line
    for a recording still missing at verify time (its date stands in
    the standing queue, batch/voice-queue.json), and the roll-off
    names for this publish (batch/rolloff-DATE.txt). Plain lines for
    the verify log — the log is what the morning reporting quotes, so
    this is where Clay is told, the same morning, never silently."""
    lines = []
    batch_dir = Path(__file__).resolve().parent
    notes_path = batch_dir / f"voice-notes-{manifest_date}.txt"
    if notes_path.is_file():
        for raw in notes_path.read_text(encoding="utf-8").splitlines():
            if raw.strip():
                lines.append(raw.strip())
    # Facts this run's notes already announced, by (date, state): the
    # queue lines below speak for standing states the notes did NOT
    # cover, so a fact is never stated twice in one finish record —
    # a stall or a landing the build's notes announced today is not
    # announced again here; on a later day, when the notes are
    # silent, the standing state is named from the queue.
    noted = set()
    for line in lines:
        m = re.search(r"(\d{4}-\d{2}-\d{2})", line)
        if not m:
            continue
        if "STALLED" in line:
            noted.add((m.group(1), "stalled"))
        if "landed on retry" in line:
            noted.add((m.group(1), "landed"))
    queue_path = batch_dir / "voice-queue.json"
    try:
        queue = json.loads(queue_path.read_text(encoding="utf-8"))
    except Exception:
        queue = []
    if isinstance(queue, list):
        for entry in queue:
            if not isinstance(entry, dict) or not entry.get("date"):
                continue
            edate = entry["date"]
            if entry.get("status") == "stalled":
                if (edate, "stalled") in noted:
                    continue
                lines.append(
                    f"VOICE: the recording for {edate} is STALLED — "
                    f"{entry.get('stall_reason', 'it cannot be rebuilt')}. "
                    f"It stands in the queue (batch/voice-queue.json) "
                    f"for Clay's word; it is not retried and not dropped.")
            elif entry.get("landed_run") == manifest_date:
                if (edate, "landed") in noted:
                    continue
                lines.append(
                    f"VOICE: the recording for {edate} landed on retry "
                    f"and stands on this publish's bundle; its queue "
                    f"entry clears below if this verify passes.")
            elif edate == manifest_date:
                lines.append(
                    f"VOICE: the recording for {manifest_date} is still "
                    f"MISSING — the edition published without its reading. "
                    f"Background retry is queued (batch/voice-queue.json) "
                    f"and the work continues until it lands or Clay says stop.")
            else:
                lines.append(
                    f"VOICE: the recording for {edate} is still missing — "
                    f"background retry continues (batch/voice-queue.json).")
    rolloff_path = batch_dir / f"rolloff-{manifest_date}.txt"
    if rolloff_path.is_file():
        for raw in rolloff_path.read_text(encoding="utf-8").splitlines():
            name = raw.strip()
            if name:
                lines.append(
                    f"ROLLOFF: {name} is named for removal in this "
                    f"publish (recordings are kept 45 days, rolling); "
                    f"each removal is confirmed on the live site below, "
                    f"and only a confirmed removal leaves the mirror.")
    return lines


def _fetch_once(url, timeout, range_from=None, read_limit=None):
    """One GET, driven through the connection engine (http.client)
    directly, along the machine's proxy road when a proxy is set.

    Returns a dict: status (the site's answer number), data (the
    bytes read — partial when the read was cut short), expected
    (the whole file's size when the answer names it, else None),
    cut (True when the read ended before the whole piece arrived).
    Raises when no answer arrives at all.

    Why the engine directly (2026-10-26 record): the urllib layer
    over this same engine was cut on every fetch from the live site
    that morning, while the engine driven directly, the requests
    library, and curl each brought the same files down whole."""
    parts = urllib.parse.urlsplit(url)
    host = parts.hostname
    port = parts.port or 443
    path = parts.path or "/"
    if parts.query:
        path += "?" + parts.query
    headers = {}
    if range_from is not None:
        headers["Range"] = f"bytes={range_from}-"
    proxy = os.environ.get("https_proxy") or os.environ.get("HTTPS_PROXY")
    ctx = ssl.create_default_context()
    if proxy:
        pp = urllib.parse.urlsplit(proxy if "//" in proxy
                                   else "//" + proxy)
        conn = http.client.HTTPSConnection(pp.hostname,
                                           pp.port or 3128,
                                           timeout=timeout,
                                           context=ctx)
        tunnel_headers = {}
        if pp.username:
            raw = (f"{urllib.parse.unquote(pp.username)}:"
                   f"{urllib.parse.unquote(pp.password or '')}")
            tunnel_headers["Proxy-Authorization"] = (
                "Basic " + base64.b64encode(raw.encode()).decode())
        conn.set_tunnel(host, port, headers=tunnel_headers)
    else:
        conn = http.client.HTTPSConnection(host, port,
                                           timeout=timeout,
                                           context=ctx)
    try:
        conn.request("GET", path, headers=headers)
        resp = conn.getresponse()
        status = resp.status
        expected = None
        if status == 200:
            length = resp.getheader("Content-Length")
            if length is not None and length.isdigit():
                expected = int(length)
        elif status == 206:
            range_header = resp.getheader("Content-Range") or ""
            if "/" in range_header:
                tail = range_header.rsplit("/", 1)[1]
                if tail.isdigit():
                    expected = int(tail)
        cut = False
        if read_limit is not None:
            data = resp.read(read_limit) or b""
        else:
            try:
                data = resp.read() or b""
            except http.client.IncompleteRead as exc:
                data = exc.partial or b""
                cut = True
            if status == 200 and expected is not None \
                    and len(data) < expected:
                cut = True
            if status == 206 and expected is not None \
                    and range_from is not None \
                    and len(data) < expected - range_from:
                cut = True
        return {"status": status, "data": data,
                "expected": expected, "cut": cut}
    finally:
        conn.close()


def site_file_stands(name):
    """Probe the live site for one file: True when it answers,
    False when it answers 404, None when the probe itself could not
    tell. One short try — this is a presence check, not a download.
    Rides the same engine road as download() (2026-10-26)."""
    url = f"{SITE_BASE}/{name}?v=verify{int(time.time())}"
    try:
        answer = _fetch_once(url, timeout=30, read_limit=1)
    except Exception:
        return None
    if answer["status"] == 404:
        return False
    if answer["status"] == 200:
        return True
    return None


def apply_mirror_rolloff(manifest_date):
    """Mirror this publish's roll-off removals — but only the
    confirmed ones. Each named recording is probed on the live site:
    gone means the delete landed, so the mirror copy goes too;
    still standing means the delete did NOT land — the mirror copy
    is KEPT, so the next run's roll-off (which is computed from the
    mirror) names it again, and the line below names the failure in
    this finish record. An unreadable site also keeps the copy.
    Returns the lines for the verify log."""
    lines = []
    rolloff_path = Path(__file__).resolve().parent / f"rolloff-{manifest_date}.txt"
    if not rolloff_path.is_file():
        return lines
    for raw in rolloff_path.read_text(encoding="utf-8").splitlines():
        name = raw.strip()
        if not name:
            continue
        stands = site_file_stands(name)
        dest = MIRROR_DIR / name
        if stands is False:
            if dest.is_file():
                dest.unlink()
            lines.append(f"MIRROR ROLLOFF: {name} is confirmed gone from the "
                         f"site; its mirror copy is removed (45-day roll)")
        elif stands is True:
            lines.append(f"ROLLOFF NOT CONFIRMED: {name} still stands on the "
                         f"site past 45 days — the delete did not land. Its "
                         f"mirror copy is kept, so the next publish names "
                         f"it again.")
        else:
            lines.append(f"ROLLOFF NOT CHECKED: {name} — the site could not "
                         f"be read for the confirmation; its mirror copy "
                         f"is kept and it will be named again next run.")
    return lines


def queue_clear_lines(manifest_date, verified):
    """The voice queue's clearing step, run at the end of verify.
    A queue entry whose recording landed on this publish's bundle
    (landed_run == the manifest date) is cleared ONLY when this
    verify passed — the recording has then been confirmed on the
    live site like every other bundle file. On a failed verify the
    entries stand, and the next run's drain lands the recordings
    again. Returns the lines for the verify log."""
    lines = []
    queue_path = Path(__file__).resolve().parent / "voice-queue.json"
    try:
        queue = json.loads(queue_path.read_text(encoding="utf-8"))
    except Exception:
        queue = []
    if not isinstance(queue, list):
        return lines
    landed = [e for e in queue if isinstance(e, dict)
              and e.get("landed_run") == manifest_date]
    if not landed:
        return lines
    if verified:
        kept = [e for e in queue if e not in landed]
        queue_path.write_text(json.dumps(kept, indent=2) + "\n", encoding="utf-8")
        for entry in landed:
            lines.append(f"VOICE QUEUE: the recording for {entry['date']} is "
                         f"confirmed on the live site; its queue entry "
                         f"is cleared.")
    else:
        for entry in landed:
            lines.append(f"VOICE QUEUE: the recording for {entry['date']} "
                         f"landed on this bundle, but the publish is NOT "
                         f"verified — its queue entry stands, and the "
                         f"next run lands it again.")
    return lines


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
    """One file, fetched down a ladder of different ways (the
    step-down rule, 2026-10-26: a retry never repeats the same ask
    when anything can be changed):

    Rung 1: the connection engine asks for the whole file at once.
    Rung 2: the file is picked up in pieces — each piece asks only
            for the bytes still missing — until the file is whole.
    Rung 3: the old road (urllib) asks for the whole file; a
            different layer, kept last.

    The 2026-10-26 record behind the ladder: urllib's top layer was
    cut on every fetch from the live site that morning, while the
    engine underneath it, driven directly, brought the same files
    down whole. An error answer from the site (the file is not
    there) is not a cut and is not laddered; it is raised at once.
    The rounds around this function (verify attempts with their
    waits) are unchanged.
    """
    errors = []
    have = b""
    expected = None
    # Rung 1: the whole file, via the engine.
    try:
        answer = _fetch_once(url, timeout=90)
        if answer["status"] >= 400:
            raise RuntimeError(f"HTTP {answer['status']}")
        if answer["status"] != 200:
            raise RuntimeError(f"unexpected HTTP {answer['status']}")
        have = answer["data"]
        expected = answer["expected"]
        if not answer["cut"] and (expected is None
                                  or len(have) == expected):
            return have
        errors.append(f"rung 1 cut at {len(have)} bytes")
    except Exception as exc:
        if isinstance(exc, RuntimeError) \
                and str(exc).startswith("HTTP"):
            raise
        errors.append(f"rung 1 failed: {exc}")
    # Rung 2: pick the file up in pieces.
    try:
        stalls = 0
        pieces = 0
        while pieces < 12:
            if expected is not None and len(have) >= expected:
                return have[:expected]
            pieces += 1
            answer = _fetch_once(url, timeout=90,
                                 range_from=len(have))
            if answer["status"] == 416 and have:
                # The ask starts past the end: the file is whole.
                return have
            if answer["status"] >= 400:
                raise RuntimeError(f"HTTP {answer['status']}")
            if answer["status"] == 200:
                # The Range ask was ignored and the file came from
                # the top; keep whichever copy stands longer.
                if not answer["cut"] and (
                        answer["expected"] is None
                        or len(answer["data"]) == answer["expected"]):
                    return answer["data"]
                if len(answer["data"]) > len(have):
                    have = answer["data"]
                    expected = answer["expected"]
                    stalls = 0
                else:
                    stalls += 1
            elif answer["status"] == 206:
                if answer["expected"] is not None:
                    expected = answer["expected"]
                if answer["data"]:
                    have += answer["data"]
                    stalls = 0
                else:
                    stalls += 1
            else:
                raise RuntimeError(
                    f"unexpected HTTP {answer['status']}")
            if expected is not None and len(have) >= expected:
                return have[:expected]
            if stalls >= 2:
                break
        errors.append(
            f"rung 2 stopped at {len(have)} of "
            f"{expected if expected is not None else '?'} bytes")
    except Exception as exc:
        if isinstance(exc, RuntimeError) \
                and str(exc).startswith("HTTP"):
            raise
        errors.append(f"rung 2 failed: {exc}")
    # Rung 3: the old road, the whole file at once.
    try:
        with urllib.request.urlopen(url, timeout=90) as resp:
            return resp.read()
    except Exception as exc:
        errors.append(f"rung 3 failed: {exc}")
    raise RuntimeError(f"download of {name} failed on every rung — "
                       + "; ".join(errors))


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

    # Reader page count cross-check (Q6): the manifest's reader page
    # PNG entries must equal the edition's page count, same number the
    # PDF check uses. Reader pages only: the bundle also carries the
    # edition web page's pictures under images/ (the web-page road,
    # 2026-10-26), and a picture that happens to be a PNG is not a
    # reader page.
    png_entries = [name for name, _, _ in entries
                   if re.match(r"^scroll-\d{4}-\d{2}-\d{2}-page-\d+-r1-.+\.png$",
                               name)]
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
    for line in voice_and_rolloff_lines(manifest_date):
        log(line)
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
            # A manifest name may carry a folder (the edition's
            # recording stands under audio/): make the folder in the
            # mirror before the copy, or the copy itself fails.
            dest.parent.mkdir(parents=True, exist_ok=True)
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
        for line in apply_mirror_rolloff(manifest_date):
            log(line)
        if not mirror_ok:
            mirror_failed = True
            exit_code = 1
    elif args.mirror:
        log("MIRROR: SKIPPED (verdict was FAIL)")

    # The voice queue clears here, and only here: an entry whose
    # recording landed on this bundle is cleared when this verify
    # has confirmed the bundle on the live site, and stands
    # otherwise (see queue_clear_lines).
    for line in queue_clear_lines(manifest_date, verdict_ok):
        log(line)

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
