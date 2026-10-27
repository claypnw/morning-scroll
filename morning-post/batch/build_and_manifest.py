#!/usr/bin/env python3
"""Morning Scroll batch job: build_and_manifest.py

Mechanizes PUBLISH-RUNBOOK Steps 1 + 2 and writes the publish manifest.

Full mode:
  1. Run prep_publish.py DATE with the venv python (Step 1).
  2. PDF source check + hashed PNG copies into publish-upload/ (Step 2).
  3. Run archive_update.py DATE (Steps 2b + 3 + 4).
  4. Write batch/manifest-DATE.txt over the publish-upload copies.

--manifest-only mode: skip prep_publish.py and archive_update.py; still
do the PDF check, the upload PDF/PNG copies, and the manifest.

PDF rule: the upload PDF is ALWAYS copied from the goal-files build
output (the source of truth). If the staging PDF's md5 differs from the
build output, print a loud COPY MISMATCH line and copy the build output
over the staging PDF and the pdf-host copy too.

The voice block (before the archive step) drains the standing retry
queue (batch/voice-queue.json), records this edition's reading, works
out where the Read button goes (batch/button-mode-DATE.json, read by
archive_update.py), and writes the 45-day roll-off list
(batch/rolloff-DATE.txt). A recording failure never stops the chain —
see the voice block's own comment.

No AI judgment inside. Prints a plain log.

Usage:
  venv/bin/python batch/build_and_manifest.py DATE [--manifest-only]
"""
import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BATCH_DIR = Path(__file__).resolve().parent
VENV_PY = ROOT / "venv" / "bin" / "python"
UPLOAD_DIR = ROOT / "publish-upload"
GOAL_FILES = Path.home() / "workspace" / "goals" / "morning-agenda-briefing" / "files"
MIRROR_DIR = Path.home() / "workspace" / "BACKUP-github-websites-only" / "morning-scroll"
VOICE_QUEUE_PATH = BATCH_DIR / "voice-queue.json"
RETENTION_DAYS = 45


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


# The published check's two live reads climb a step-down ladder
# (2026-10-26, second form after the fresh-eyes review). The first
# form repeated the same whole read at longer limits; the review
# sent it back, on the morning's own evidence: on 2026-10-26 whole
# urllib reads from these addresses were CUT partway at random
# points, every time — a longer limit does nothing for a cut. So
# each try now takes a different road:
#   try 1 — the whole read exactly as before (the standing call);
#   try 2 — the file read in parts of at most PART_BYTES, keeping
#     the bytes that arrived and asking only for the missing tail
#     (a Range request per part). Each part is checked against the
#     range the server says it sent: a part that does not start
#     where it was asked to, or a file whose stated size changes
#     mid-read, ends the try — pieces of two versions are never
#     joined. A "no such range" answer (416) ends the read only
#     when its stated total equals the bytes in hand.
#   try 3 — the same address fetched by curl, the road that came
#     down whole in the 2026-10-26 diagnosis.
# The limits (60, then 120, then 180 seconds) bound each socket
# operation, not the whole read; the whole read is bounded by
# READ_DEADLINE_SECONDS across all three tries together, checked
# between requests and between chunks, so a slow-drip answer cannot
# hold a read past it. The worst case for one read is therefore
# the deadline itself (600 seconds), and the published check makes
# two reads — a bound the chain's own time budget stands against
# (the chain runs from the 03:30 briefing step; the edition must
# be live by about 06:15). Answers no later try can fix — an HTTP
# 4xx other than 408 (time-out) and 429 (busy) — are raised at once
# and named, never retried down the ladder. Each failed try is
# printed with its error; after the third, the last error is
# raised, so the caller's standing failure path runs unchanged.
READ_DEADLINE_SECONDS = 600
PART_BYTES = 256 * 1024
_TRY_TIMEOUTS = (60, 120, 180)
_TRY_WAITS = (10, 20)


def _retryable_http(code):
    return code in (408, 429) or 500 <= code <= 599


def _open_url(url, headers, timeout, extra_headers=None):
    merged = dict(headers or {})
    merged.update(extra_headers or {})
    request = urllib.request.Request(url, headers=merged)
    return urllib.request.urlopen(request, timeout=timeout)


def _read_body(resp, deadline_end):
    """Read a response body in chunks, enforcing the read deadline
    between chunks; a stated length the body does not reach raises,
    so a short read is a failed try, never a short result. The body
    is pulled with read1 where the response offers it: a plain
    read(n) waits until it holds n bytes, so a slow-drip answer
    (a byte at a time, never idle long enough to trip the socket
    limit) would hold the read past the deadline without ever
    returning to the check between chunks; read1 returns with
    whatever one pull brought, and the deadline check runs."""
    pull = getattr(resp, "read1", None) or resp.read
    chunks = []
    got = 0
    while True:
        chunk = pull(256 * 1024)
        if not chunk:
            break
        chunks.append(chunk)
        got += len(chunk)
        if time.monotonic() > deadline_end:
            raise TimeoutError("the read deadline ran out mid-read")
    data = b"".join(chunks)
    stated = resp.headers.get("Content-Length") if resp.headers else None
    if stated is not None:
        try:
            stated_n = int(stated)
        except (TypeError, ValueError):
            stated_n = None
        if stated_n is not None and got != stated_n:
            raise OSError(f"short read: got {got} of {stated_n} bytes")
    return data


def _read_whole_road(url, headers, timeout, deadline_end):
    with _open_url(url, headers, timeout) as resp:
        return _read_body(resp, deadline_end)


def _parse_content_range(value):
    """'bytes 100-199/500' -> (100, 199, 500); a total of '*' -> None
    total; 'bytes */500' (the 416 form) -> (None, None, 500)."""
    if not value:
        return None, None, None
    try:
        unit, rest = value.split(None, 1)
        range_part, _, total_part = rest.partition("/")
        total = None if total_part in ("", "*") else int(total_part)
        if range_part == "*":
            return None, None, total
        start_s, _, end_s = range_part.partition("-")
        return int(start_s), int(end_s), total
    except (ValueError, AttributeError):
        return None, None, None


def _read_parts_road(url, headers, timeout, deadline_end):
    got = bytearray()
    total = None
    stalls = 0
    while total is None or len(got) < total:
        if time.monotonic() > deadline_end:
            raise TimeoutError("the read deadline ran out during the parts read")
        start = len(got)
        range_header = {"Range": f"bytes={start}-{start + PART_BYTES - 1}"}
        try:
            resp = _open_url(url, headers, timeout, range_header)
        except urllib.error.HTTPError as err:
            if err.code == 416:
                _, _, stated_total = _parse_content_range(
                    err.headers.get("Content-Range") if err.headers else None)
                if stated_total is not None and stated_total == len(got) \
                        and len(got) > 0:
                    return bytes(got)
                if total is not None and total == len(got) and len(got) > 0:
                    return bytes(got)
                raise OSError(
                    f"range refused (416) with {len(got)} bytes in hand "
                    f"and no proof they reach the end of the file")
            raise
        with resp:
            if resp.status == 200:
                # The Range ask was ignored: the answer is the whole
                # file from the start. It replaces the kept bytes —
                # pieces are never joined across answers.
                body = _read_body(resp, deadline_end)
                if total is not None and len(body) != total:
                    raise OSError(
                        "the whole answer does not match the size "
                        "learned earlier in this read")
                return body
            if resp.status != 206:
                raise OSError(
                    f"unexpected answer {resp.status} to a part request")
            p_start, p_end, p_total = _parse_content_range(
                resp.headers.get("Content-Range") if resp.headers else None)
            if p_start != start:
                raise OSError(
                    f"a part began at byte {p_start}; byte {start} was asked for")
            if p_total is not None:
                if total is not None and p_total != total:
                    raise OSError("the file changed size during the read")
                total = p_total
            part = _read_body(resp, deadline_end)
            span = (p_end - p_start + 1) if p_end is not None else len(part)
            if len(part) > span:
                raise OSError("a part carried more bytes than its stated range")
            got.extend(part)
            if len(part) == 0:
                stalls += 1
                if stalls >= 3:
                    raise OSError("the parts read stopped advancing")
            else:
                stalls = 0
            if total is not None and len(got) > total:
                raise OSError("the read ran past the file's stated size")
            if total is None and len(part) < PART_BYTES:
                # No total was ever stated and the server sent less
                # than a full part: that was the end of the file.
                return bytes(got)
    return bytes(got)


def _read_curl_road(url, headers, timeout, deadline_end):
    remaining = int(deadline_end - time.monotonic())
    if remaining <= 0:
        raise TimeoutError("the read deadline ran out before the curl try")
    cmd = ["/usr/bin/curl", "-fsS", "--max-time", str(min(timeout, remaining))]
    for key, value in (headers or {}).items():
        cmd += ["-H", f"{key}: {value}"]
    cmd.append(url)
    proc = subprocess.run(cmd, capture_output=True)
    if proc.returncode != 0:
        raise OSError(
            f"the curl road failed (exit {proc.returncode}): "
            f"{proc.stderr.decode('utf-8', 'replace').strip()}")
    return proc.stdout


def _fetch_ladder(what, url, headers=None):
    """Run one live read down the step-down ladder described above
    and return its bytes. After the third failed try the last error
    is raised, so the caller's standing failure path runs."""
    deadline_end = time.monotonic() + READ_DEADLINE_SECONDS
    roads = (("the whole read", _read_whole_road),
             ("the read in parts", _read_parts_road),
             ("the curl road", _read_curl_road))
    last_exc = None
    for try_no, (road_name, road) in enumerate(roads, start=1):
        if try_no > 1:
            wait = _TRY_WAITS[try_no - 2]
            print(f"{what}: try {try_no - 1} failed ({last_exc}); "
                  f"waiting {wait} seconds before try {try_no} "
                  f"({road_name})", flush=True)
            time.sleep(wait)
        try:
            return road(url, headers, _TRY_TIMEOUTS[try_no - 1], deadline_end)
        except urllib.error.HTTPError as exc:
            if not _retryable_http(exc.code):
                print(f"{what}: answer {exc.code} cannot be fixed by "
                      f"another try; not retrying", flush=True)
                raise
            last_exc = exc
        except Exception as exc:
            last_exc = exc
        if time.monotonic() > deadline_end:
            raise TimeoutError(
                f"{what}: the {READ_DEADLINE_SECONDS}-second limit "
                f"for one read ran out (last error: {last_exc})")
    raise last_exc


def md5_of(path):
    h = hashlib.md5()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def sha1_8_of(path):
    h = hashlib.sha1()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()[:8]


def vol_no(day):
    return f"{day.year % 100:02d}{day.month:02d}", f"{day.day:02d}"


# Margin sample points (fractions of page width/height) for the parchment
# spot-check. On the real parchment build all six read tan (e.g.
# (143,112,68)); on the stripped 2026-10-17 build the paper background was
# gone and such points read white (255,255,255).
#
# Points must sit INSIDE the parchment sheet's deckled silhouette: the
# burnt-edge wave recedes up to 55px at 150dpi from any edge (build_paper's
# _deckled_alpha max_depth), i.e. 4.3% of width / 3.3% of height. The
# original points (0.03 / 0.97 fractions = 38–50px) sat inside that wave
# zone: on the 2026-10-18 seed both bottom corners fell fully outside the
# sheet (alpha 0) and the bottom-mid sat on the wave's slope (alpha 100),
# so a good parchment build scored 4/6 and the check false-failed. These points are inset 89px horizontally and 82–99px
# vertically — beyond the wave's reach on any seed — and read parchment on
# all nine editions 2026-10-10..18 (verified 2026-10-18).
PARCHMENT_POINTS = [(0.07, 0.05), (0.5, 0.05), (0.93, 0.05),
                    (0.07, 0.94), (0.5, 0.94), (0.93, 0.94)]


def is_parchment(r, g, b):
    return r < 248 and g < 248 and b < 248 and (r - b) >= 15


def parchment_problems(pdf_path):
    """Render spot-check alone: page 1 margins parchment, not white.
    Returns a list of problems (empty = pass). Needs no edition meta,
    so it can gate prep_publish.py, which stages from the build output.
    """
    try:
        import fitz
    except ImportError:
        return ["PyMuPDF (fitz) not available for the parchment spot-check"]
    try:
        doc = fitz.open(pdf_path)
    except Exception as exc:
        return [f"build output {pdf_path} does not open as a PDF: {exc}"]
    if doc.page_count < 1:
        doc.close()
        return [f"build output {pdf_path} has no pages"]
    pix = doc[0].get_pixmap(dpi=72)
    samples = []
    for fx, fy in PARCHMENT_POINTS:
        x = min(max(int(pix.width * fx), 0), pix.width - 1)
        y = min(max(int(pix.height * fy), 0), pix.height - 1)
        samples.append(pix.pixel(x, y))
    doc.close()
    tan = sum(1 for (r, g, b) in samples if is_parchment(r, g, b))
    if tan < 5:
        return [f"page 1 margins look white, not parchment ({tan}/6 parchment samples: {samples})"]
    return []


def check_build_pdf(pdf_path, meta):
    """Sanity-check the BUILD OUTPUT before it may heal staging (Q4).

    The build output is the source of truth for the upload PDF, so it is
    checked itself: page count vs edition meta, page dimensions vs the
    meta's rendered size (meta pixels are 3x PDF points), and a render
    spot-check that page 1's margins are parchment-colored, not white.
    Any failure is a loud chain FAIL — nothing is copied.
    """
    try:
        import fitz
    except ImportError:
        fail("BUILD SANITY FAIL: PyMuPDF (fitz) not available to check the build output")
    pages_meta = meta.get("pages", [])
    if not pages_meta:
        fail("BUILD SANITY FAIL: edition-meta.json lists no pages", kind="check_failed")
    try:
        doc = fitz.open(pdf_path)
    except Exception as exc:
        fail(f"BUILD SANITY FAIL: build output {pdf_path} does not open as a PDF: {exc}")
    problems = []
    if doc.page_count != len(pages_meta):
        problems.append(f"page count {doc.page_count} != edition meta {len(pages_meta)}")
    for i, page in enumerate(doc):
        want_w = pages_meta[i]["width"] / 3.0 if i < len(pages_meta) else None
        want_h = pages_meta[i]["height"] / 3.0 if i < len(pages_meta) else None
        if want_w is not None and (abs(page.rect.width - want_w) > 1.5 or abs(page.rect.height - want_h) > 1.5):
            problems.append(
                f"page {i + 1} size {page.rect.width}x{page.rect.height}pt != meta {want_w}x{want_h}pt")
    parch = parchment_problems(pdf_path)
    problems.extend(parch)
    if not parch:
        print("build sanity: page 1 parchment spot-check PASS")
    doc.close()
    if problems:
        for problem in problems:
            print(f"BUILD SANITY FAIL: {problem}")
        fail(f"build output {pdf_path} failed the sanity check — refusing to copy or heal from it",
             kind="check_failed")
    print(f"build sanity: page count and dimensions PASS ({len(pages_meta)} pages)")


def _load_voice_queue():
    """The standing voice retry queue: a list of entries, one per
    edition whose recording is missing. A missing or unreadable file
    reads as an empty queue — the queue is a work list, not a gate."""
    try:
        data = json.loads(VOICE_QUEUE_PATH.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return [e for e in data if isinstance(e, dict) and e.get("date")]
    except Exception:
        pass
    return []


def _save_voice_queue(queue):
    VOICE_QUEUE_PATH.write_text(json.dumps(queue, indent=2) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Stage one Morning Scroll edition and write its publish manifest.")
    parser.add_argument("date", help="Edition date, YYYY-MM-DD")
    parser.add_argument("--manifest-only", action="store_true",
                        help="Skip prep_publish.py and archive_update.py; PDF check, copies, and manifest only")
    parser.add_argument("--force", action="store_true",
                        help="Deliberately rebuild an already-published date (prints a loud FORCED line)")
    args = parser.parse_args()

    global _STEP
    _STEP = "read arguments"
    date_str = args.date
    try:
        day = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        fail(f"bad date {date_str!r} (want YYYY-MM-DD)")

    # ---- already-published guard (review fix Q3) ---------------------------
    # prep_publish.py re-renders the staging PNGs and the copies below
    # overwrite publish-upload — and prep's renders are NOT byte-identical
    # to the ones originally published (proven 2026-10-17). So a re-run of
    # an already-published date must refuse BEFORE anything is touched:
    # staging, upload, and the caller's files stay byte-identical.
    if args.force:
        print(f"FORCED REBUILD: --force given for {date_str}; the already-published guard is bypassed on purpose")
    else:
        # Gate item 104: the published-check fetch below is gated before
        # the fetched data is used. The fetch outcome is written as a
        # fetch-state file and chain_gate.py runs the daily-jobs checker
        # on it; a stop here stops the build before anything is touched.
        # Checksum source (added 2026-10-19, completing the item-104
        # wiring): GitHub's repository contents listing for this same
        # file on main carries the file's blob SHA. The build computes
        # the git blob SHA of the bytes it actually fetched (SHA-1 of
        # "blob " + byte length + a zero byte + the bytes) and compares
        # the two. checksum_match records that real comparison — true
        # or false, never null on a completed fetch, never invented:
        # if the listing cannot be read, no match is proven and the
        # record says false, so the gate stops the build.
        _STEP = "published check"
        fetch_error = None
        live_index = None
        garbled = False
        ambiguous = False

        try:
            raw_index = _fetch_ladder(
                "published check: read of the live search index",
                "https://raw.githubusercontent.com/claypnw/morning-scroll/main/scroll-search-index.json")
        except Exception as exc:
            fetch_error = exc
            raw_index = None
        fetched_blob_sha = None
        repo_blob_sha = None
        checksum_match = False
        if raw_index is not None:
            fetched_blob_sha = hashlib.sha1(
                b"blob " + str(len(raw_index)).encode("ascii") + b"\x00" + raw_index
            ).hexdigest()

            try:
                listing_body = _fetch_ladder(
                    "published check: read of the file's listing",
                    "https://api.github.com/repos/claypnw/morning-scroll/contents/scroll-search-index.json?ref=main",
                    headers={"User-Agent": "morning-scroll-build",
                             "Accept": "application/vnd.github+json"})
                repo_blob_sha = json.loads(
                    listing_body.decode("utf-8")).get("sha")
            except Exception as exc:
                # The reason is printed, never swallowed: with no
                # listing, no checksum match can be proven, and the
                # gate record below says so — the morning record
                # quotes this line for why.
                print(f"published check: read of the file's listing "
                      f"failed after the ladder's tries ({exc}); no "
                      f"checksum match can be proven", flush=True)
                repo_blob_sha = None
            checksum_match = (repo_blob_sha is not None
                              and fetched_blob_sha == repo_blob_sha)
            try:
                live_index = json.loads(raw_index.decode("utf-8"))
                ambiguous = not isinstance(live_index, list)
            except Exception:
                garbled = True
        fetch_state = {
            "fetch_ok": raw_index is not None,
            "checksum_match": checksum_match,
            "checksum_source": "github contents listing blob sha (main)",
            "repo_blob_sha": repo_blob_sha,
            "fetched_blob_sha": fetched_blob_sha,
            "garbled": garbled,
            "ambiguous": ambiguous,
            "fell_back_to_old_copy_silently": False,
            "work_stopped": fetch_error is not None,
            "clay_asked_with_options": False,
        }
        logs_dir = BATCH_DIR / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        fetch_state_path = logs_dir / f"fetch-state-{date_str}.json"
        fetch_state_path.write_text(json.dumps(fetch_state, indent=2) + "\n", encoding="utf-8")
        gate = subprocess.run([sys.executable, str(BATCH_DIR / "chain_gate.py"),
                               "104", date_str, "--fetch-state", str(fetch_state_path)])
        if gate.returncode != 0:
            fail(f"Gate item 104 STOP: the published-check fetch record did not pass for "
                 f"{date_str}; stopping before the fetched data is used and before "
                 f"anything is touched (fetch state: {fetch_state_path})",
                 kind="check_failed")
        if fetch_error is not None:
            fail(f"PUBLISHED CHECK FAILED: could not read the live search index to confirm "
                 f"{date_str} is unpublished ({fetch_error}); stopping before anything is touched",
                 kind="check_failed")
        if garbled or ambiguous or live_index is None:
            fail(f"PUBLISHED CHECK FAILED: the live search index for {date_str} did not "
                 f"read as a JSON list; stopping before anything is touched",
                 kind="check_failed")
        if any(isinstance(e, dict) and e.get("date") == date_str for e in live_index):
            fail(f"ALREADY PUBLISHED: {date_str} is in the live search index. Refusing to re-run "
                 f"the build for a published date — staging and publish-upload are untouched. "
                 f"For a deliberate rebuild (e.g. a corrected edition), re-run with --force.",
                 kind="check_failed")
        print(f"published check: {date_str} is not in the live search index — safe to build")
    vol, no = vol_no(day)
    python = str(VENV_PY) if VENV_PY.is_file() else sys.executable

    staging_dir = ROOT / "publish-staging" / date_str
    pdf_name = f"payson-morning-scroll-{date_str}.pdf"
    goal_pdf = GOAL_FILES / pdf_name
    staging_pdf = staging_dir / pdf_name
    print(f"input: edition dir {staging_dir}")
    print(f"mode: {'manifest-only' if args.manifest_only else 'full'}")

    # ---- Step 1: prep_publish.py (full mode only) -------------------------
    if not args.manifest_only:
        # prep stages FROM the build output, so the parchment gate fires
        # before prep too: a stripped build output stops the chain here.
        _STEP = "build sanity check (pre-prep)"
        if goal_pdf.is_file():
            pre = parchment_problems(goal_pdf)
            if pre:
                for problem in pre:
                    print(f"BUILD SANITY FAIL (pre-prep): {problem}")
                fail("build output failed the parchment spot-check before staging — chain stopped",
                     kind="check_failed")
            print("build sanity (pre-prep): page 1 parchment spot-check PASS")
        _STEP = "step 1: prep_publish"
        cmd = [python, str(ROOT / "prep_publish.py"), date_str]
        print(f"run: {' '.join(cmd)}")
        result = subprocess.run(cmd)
        if result.returncode != 0:
            fail(f"prep_publish.py failed with exit code {result.returncode}")

    # ---- edition meta -------------------------------------------------------
    _STEP = "read edition meta"
    meta_path = staging_dir / "edition-meta.json"
    if not meta_path.is_file():
        fail(f"missing {meta_path}")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    page_count = len(meta.get("pages", []))
    print(f"input: {meta_path} (pages: {page_count})")

    # ---- build-output sanity check (before it may heal anything) ---------------
    _STEP = "build sanity check"
    if not goal_pdf.is_file():
        fail(f"missing build-output PDF {goal_pdf}")
    check_build_pdf(goal_pdf, meta)

    # Recordings an earlier pass of THIS date's build already put on
    # this date's manifest (a same-day re-run after a gate stop, say)
    # belong to this bundle: the audio cleanup below spares them, and
    # the voice block carries them into the new manifest. Without
    # this, a re-run would quietly drop a landed retry recording —
    # the queue entry is already cleared by then, so nothing would
    # ever name the loss.
    prior_audio_names = set()
    prior_manifest = BATCH_DIR / f"manifest-{date_str}.txt"
    if prior_manifest.is_file():
        for line in prior_manifest.read_text(encoding="utf-8").splitlines():
            parts = line.split()
            if len(parts) == 3 and parts[2].startswith("audio/"):
                prior_audio_names.add(parts[2])

    # ---- clear stale dated files out of the upload dir (Q7) ----------------------
    # publish-upload must hold only this edition's dated files plus the two
    # archive files archive_update.py refreshes. Anything dated from an
    # earlier edition is removed here, by name, so the bundle check can
    # treat any leftover as a real problem.
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    stale_re = re.compile(r"^(scroll-\d{4}-\d{2}-\d{2}-page-\d+-r1-.+\.png|payson-morning-scroll-\d{4}-\d{2}-\d{2}\.pdf|edition-\d{4}-\d{2}-\d{2}\.html)$")
    for path in sorted(UPLOAD_DIR.iterdir()):
        if stale_re.match(path.name) and date_str not in path.name:
            path.unlink()
            print(f"cleanup: removed stale upload file {path.name}")
    # Same cleanup for the recordings folder: an earlier edition's
    # recording must not ride along in publish-upload/audio/ — only
    # this edition's recording (and any queued recording the voice
    # block below lands for this bundle) belongs to it. The cleanup
    # runs before the voice block, so a queued recording whose bundle
    # never published is simply recorded again by the drain — a queue
    # entry is cleared only when a manifest names its file.
    audio_dir = UPLOAD_DIR / "audio"
    if audio_dir.is_dir():
        stale_audio_re = re.compile(r"^morning-scroll-\d{4}-\d{2}-\d{2}\.mp3$")
        for path in sorted(audio_dir.iterdir()):
            if (stale_audio_re.match(path.name) and date_str not in path.name
                    and f"audio/{path.name}" not in prior_audio_names):
                path.unlink()
                print(f"cleanup: removed stale upload file audio/{path.name}")

    # ---- PDF source check -----------------------------------------------------
    _STEP = "step 2: PDF and page PNG copies"
    if not goal_pdf.is_file():
        fail(f"missing build-output PDF {goal_pdf}")
    if not staging_pdf.is_file():
        fail(f"missing staging PDF {staging_pdf}")
    goal_md5 = md5_of(goal_pdf)
    staging_md5 = md5_of(staging_pdf)
    print(f"input: pdf source {goal_pdf} md5 {goal_md5} ({goal_pdf.stat().st_size} bytes)")
    print(f"input: staging pdf {staging_pdf} md5 {staging_md5} ({staging_pdf.stat().st_size} bytes)")
    if goal_md5 != staging_md5:
        print("COPY MISMATCH — using build output")
        print(f"COPY MISMATCH: staging md5 {staging_md5} != build output md5 {goal_md5}; "
              f"copying build output over the staging PDF and the pdf-host copy")
        shutil.copyfile(goal_pdf, staging_pdf)
        pdf_host = ROOT / "pdf-host" / pdf_name
        pdf_host.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(goal_pdf, pdf_host)
        print(f"copied: {goal_pdf} -> {staging_pdf}")
        print(f"copied: {goal_pdf} -> {pdf_host}")

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    upload_pdf = UPLOAD_DIR / pdf_name
    shutil.copyfile(goal_pdf, upload_pdf)
    print(f"output: {upload_pdf} ({upload_pdf.stat().st_size} bytes)")

    # ---- Step 2: hashed PNG copies ---------------------------------------------
    png_re = re.compile(rf"^scroll-{re.escape(date_str)}-page-(\d+)\.png$")
    staging_pngs = []
    for path in staging_dir.iterdir():
        m = png_re.match(path.name)
        if m:
            staging_pngs.append((int(m.group(1)), path))
    staging_pngs.sort()
    if not staging_pngs:
        fail(f"no staging page PNGs found in {staging_dir}")
    if len(staging_pngs) != page_count:
        fail(f"page count cross-check FAILED: {len(staging_pngs)} staging page PNGs "
             f"!= {page_count} pages in edition meta (Q6)", kind="check_failed")
    print(f"page count cross-check: {len(staging_pngs)} staging PNGs == {page_count} meta pages "
          f"== PDF pages (build sanity)")
    png_names = []
    for page_no, src in staging_pngs:
        dest_name = f"scroll-{date_str}-page-{page_no}-r1-{sha1_8_of(src)}.png"
        dest = UPLOAD_DIR / dest_name
        shutil.copyfile(src, dest)
        png_names.append(dest_name)
        print(f"output: {dest} ({dest.stat().st_size} bytes)")

    # ---- Voice: retry queue drain, this edition's recording, roll-off --------
    # Clay's rules (2026-10-26): a recording failure never stops the
    # edition. The edition publishes without its recording and without
    # its Read button; the failure is written into
    # batch/voice-notes-DATE.txt, which verify.py reads into the
    # morning record so Clay is told the same morning; and the date
    # stands in the standing queue file batch/voice-queue.json, which
    # every later run drains before its own recording step — background
    # retry until the recording lands or Clay says stop. When a queued
    # recording lands, it publishes with this run's bundle, as normal.
    # A queue entry is NOT cleared here: it clears only when
    # verify.py has confirmed the recording on the live site (see
    # verify.py's queue-clear step). A bundle that never publishes —
    # a gate stop, a failed publish — leaves the entry standing, and
    # the next run's drain tries again (record_edition.py skips when
    # the standing file already matches the text; the stale-file
    # cleanup may delete the landed file first, and the drain simply
    # records it again from the staged text).
    _STEP = "voice: queue drain and recording"
    queue = _load_voice_queue()
    landed_dates = []
    # This date's telling lines, gathered in memory and written
    # fresh (never appended to) at the end of the voice block. The
    # list starts from the notes an earlier pass of this same date's
    # build already wrote — a stall or a landing from the first pass
    # is still this date's news on a re-run — and each line is kept
    # exactly once, so verify can never quote a line twice.
    voice_notes = []
    prior_notes_path = BATCH_DIR / f"voice-notes-{date_str}.txt"
    if prior_notes_path.is_file():
        for raw in prior_notes_path.read_text(encoding="utf-8").splitlines():
            if raw.strip() and raw.strip() not in voice_notes:
                voice_notes.append(raw.strip())

    def voice_note(line):
        # One line per fact per date. A re-run of this date's build
        # gathers the earlier pass's lines first (above), and a line
        # restating the same fact — this date's recording failure, a
        # queued date's still-missing — replaces the earlier pass's
        # wording rather than standing beside it: the two wordings
        # differ (a later pass's last-try reason names a later try),
        # so exact-text keeping alone would state the fact twice and
        # verify would quote it twice. The newest wording stands.
        key = None
        if line.startswith(("VOICE FAILURE: the recording for ",
                             "VOICE: the recording for ")):
            for marker in (" failed — ", " is still missing — "):
                if marker in line:
                    key = line.split(marker)[0]
                    break
        if key:
            voice_notes[:] = [ln for ln in voice_notes
                              if not ln.startswith(key)]
        if line not in voice_notes:
            voice_notes.append(line)
        print(line)

    def voice_failure_detail(fdate):
        """The ladder detail record_edition.py leaves when a record's
        third try fails (batch/voice-failure-DATE.json, written by
        that record's own run and cleared at the start of its next):
        (tries made, ladder summary, the last try's reason), or None
        when this run left none — an earlier failure road (a missing
        staged text, a stub too short to record) leaves no detail,
        and the telling falls back to the plain words it has always
        used. The ladder summary names every value the tries stepped
        down: the chunk sizes, the concurrency values, and the wait
        limits, each in try order."""
        try:
            detail = json.loads((BATCH_DIR / f"voice-failure-{fdate}.json")
                                .read_text(encoding="utf-8"))
            ladder = detail.get("ladder") or []
            summary = (f"chunks "
                       f"{'/'.join(str(e.get('chunk_chars')) for e in ladder)}, "
                       f"concurrency "
                       f"{'/'.join(str(e.get('concurrency')) for e in ladder)}, "
                       f"wait limit "
                       f"{'/'.join(str(e.get('timeout_secs')) for e in ladder)}s")
            return (int(detail.get("tries", 0)), summary,
                    str(detail.get("last_error", "")))
        except Exception:
            return None

    for entry in queue:
        qdate = entry.get("date")
        if not qdate or qdate == date_str or entry.get("status") == "stalled":
            continue
        q_staging_text = ROOT / "publish-staging" / qdate / "search-text.txt"
        if not q_staging_text.is_file():
            entry["status"] = "stalled"
            entry["stall_reason"] = ("the staged edition text is gone, so the "
                                     "recording cannot be rebuilt")
            voice_note(f"VOICE: the missing recording for {qdate} is STALLED — "
                       f"its staged edition text is gone, so it cannot be "
                       f"rebuilt. It stays in the queue file "
                       f"(batch/voice-queue.json) for Clay's word.")
            continue
        print(f"voice queue: retrying the recording for {qdate} "
              f"(queued {entry.get('queued', 'unknown')}, "
              f"attempt {int(entry.get('attempts', 0)) + 1})")
        q_result = subprocess.run([python, str(BATCH_DIR / "record_edition.py"), qdate])
        q_mp3 = UPLOAD_DIR / "audio" / f"morning-scroll-{qdate}.mp3"
        if q_result.returncode == 0 and q_mp3.is_file():
            entry["landed_run"] = date_str
            landed_dates.append(qdate)
            voice_note(f"VOICE: the recording for {qdate} landed on retry and "
                       f"publishes with this edition ({q_mp3.name}).")
        else:
            entry["attempts"] = int(entry.get("attempts", 0)) + 1
            entry["last_try"] = datetime.now().astimezone().isoformat(timespec="seconds")
            detail = voice_failure_detail(qdate)
            entry["last_error"] = (f"record_edition.py exit code "
                                   f"{q_result.returncode} in the {date_str} run"
                                   + (f" after {detail[0]} tries ({detail[1]}); "
                                      f"last try: {detail[2]}" if detail else ""))
            voice_note(f"VOICE: the recording for {qdate} is still missing — "
                       f"retry {entry['attempts']} failed in this run"
                       + (f" after {detail[0]} tries ({detail[1]}; last try: "
                          f"{detail[2]})" if detail else "")
                       + f". The work continues in the background; the queue "
                         f"file holds it.")
    today_mp3 = UPLOAD_DIR / "audio" / f"morning-scroll-{date_str}.mp3"
    record_cmd = [python, str(BATCH_DIR / "record_edition.py"), date_str]
    print(f"run: {' '.join(record_cmd)}")
    record_result = subprocess.run(record_cmd)
    today_recorded = record_result.returncode == 0 and today_mp3.is_file()
    if today_recorded:
        for entry in queue:
            if entry.get("date") == date_str:
                entry["landed_run"] = date_str
                if date_str not in landed_dates:
                    landed_dates.append(date_str)
    else:
        detail = voice_failure_detail(date_str)
        tries_words = (f"record_edition.py exit code "
                       f"{record_result.returncode} after {detail[0]} tries "
                       f"({detail[1]}); last try: {detail[2]}" if detail else
                       f"record_edition.py exit code {record_result.returncode}")
        existing = next((e for e in queue if e.get("date") == date_str), None)
        if existing is None:
            queue.append({"date": date_str,
                          "queued": datetime.now().astimezone().isoformat(timespec="seconds"),
                          "attempts": 1,
                          "last_error": tries_words})
        else:
            existing["attempts"] = int(existing.get("attempts", 0)) + 1
            existing["last_error"] = tries_words
            existing.pop("landed_run", None)
        voice_note(f"VOICE FAILURE: the recording for {date_str} failed — this "
                   f"edition publishes WITHOUT its reading and without its "
                   f"Read button."
                   + (f" {detail[0]} tries were made — {detail[1]}; the "
                      f"last try failed: {detail[2]}." if detail else "")
                   + f" The date is queued for background retry in "
                     f"batch/voice-queue.json; the work continues until the "
                     f"recording lands or Clay says stop.")
        print(f"voice: recording for {date_str} failed (exit code "
              f"{record_result.returncode}) — the chain continues without it, "
              f"per Clay's rule that the paper publishes anyway")
    _save_voice_queue(queue)
    # Carry recordings an earlier pass of this date's build already
    # landed (they stand on this date's earlier manifest, and the
    # cleanup above spared them): they belong to this bundle too.
    for name in sorted(prior_audio_names):
        m = re.match(r"audio/morning-scroll-(\d{4}-\d{2}-\d{2})\.mp3$", name)
        if m and m.group(1) != date_str and m.group(1) not in landed_dates:
            if (UPLOAD_DIR / name).is_file():
                landed_dates.append(m.group(1))
                print(f"voice: the recording for {m.group(1)} stands on this "
                      f"date's earlier manifest — carried into this bundle")
    # The Read button's home for this run, read by archive_update.py
    # from batch/button-mode-DATE.json: "new" — this edition's
    # recording stands, so the button goes on this edition; "retry" —
    # this edition's recording is missing but a queued recording
    # landed, so the button goes on the landed edition (the newest
    # section that carries a recording); "none" — no button moves.
    if today_recorded:
        button_mode, button_date = "new", date_str
    elif landed_dates:
        button_mode, button_date = "retry", max(landed_dates)
    else:
        button_mode, button_date = "none", None
    (BATCH_DIR / f"button-mode-{date_str}.json").write_text(
        json.dumps({"mode": button_mode, "button_date": button_date}, indent=2) + "\n",
        encoding="utf-8")
    print(f"voice: read-button mode {button_mode}"
          + (f" (button edition {button_date})" if button_date else ""))

    # Roll-off (Clay's rule, 2026-10-26): recordings are kept 45 days,
    # rolling — when day 46 starts, the oldest rolls off. The mirror's
    # audio/ folder is the chain's record of what stands on the site;
    # every recording there whose edition date is more than 45 days
    # before this edition is named in batch/rolloff-DATE.txt, which
    # publish.py prints as delete instructions for this same publish.
    # verify.py names each one in its record, confirms the removal on
    # the live site, and mirrors only the confirmed removals — an
    # unconfirmed name keeps its mirror copy, so the next run's
    # roll-off names it again.
    _STEP = "voice: roll-off"
    rolloff_path = BATCH_DIR / f"rolloff-{date_str}.txt"
    rolloff_path.unlink(missing_ok=True)
    cutoff = day - timedelta(days=RETENTION_DAYS)
    rolloff_names = []
    mirror_audio = MIRROR_DIR / "audio"
    if mirror_audio.is_dir():
        audio_name_re = re.compile(r"^morning-scroll-(\d{4}-\d{2}-\d{2})\.mp3$")
        for path in sorted(mirror_audio.iterdir()):
            m = audio_name_re.match(path.name)
            if not m:
                continue
            try:
                eday = datetime.strptime(m.group(1), "%Y-%m-%d").date()
            except ValueError:
                continue
            if eday < cutoff:
                rolloff_names.append(f"audio/{path.name}")
    keep_names = {f"audio/morning-scroll-{date_str}.mp3"} | {
        f"audio/morning-scroll-{d}.mp3" for d in landed_dates}
    rolloff_names = [n for n in rolloff_names if n not in keep_names]
    if rolloff_names:
        rolloff_path.write_text("\n".join(rolloff_names) + "\n", encoding="utf-8")
        for name in rolloff_names:
            print(f"roll-off: {name} is more than {RETENTION_DAYS} days old — "
                  f"named in {rolloff_path.name} for removal in this publish")
    else:
        print(f"roll-off: no recordings older than {RETENTION_DAYS} days stand on the site")
    if voice_notes:
        (BATCH_DIR / f"voice-notes-{date_str}.txt").write_text(
            "\n".join(voice_notes) + "\n", encoding="utf-8")

    # ---- Edition web page ---------------------------------------------------
    # The reading road (the admin's ruling, 2026-10-26): each edition
    # also stands on the site as a web page — edition-DATE.html plus
    # its pictures under images/ — built by build_edition_page.py
    # from the same source as the paper. The page's listen lines
    # gate on the recordings exactly as the paper's do, so in full
    # mode this step runs here, after the voice block, when the
    # recordings stand in publish-upload/audio/. The images folder
    # is cleared first: the bundle carries this edition's pictures
    # only (standing pictures share content names across editions
    # and are copied fresh each run).
    page_files = []
    if not args.manifest_only:
        _STEP = "edition web page"
        images_dir = UPLOAD_DIR / "images"
        if images_dir.is_dir():
            shutil.rmtree(images_dir)
            print("cleanup: cleared publish-upload/images/ (rebuilt by the web page step)")
        page_cmd = [python, str(ROOT / "build_edition_page.py"), date_str]
        print(f"run: {' '.join(page_cmd)}")
        page_result = subprocess.run(page_cmd, capture_output=True, text=True)
        for line in page_result.stdout.splitlines():
            print(line)
            if line.startswith("WROTE "):
                page_files.append(line[len("WROTE "):].split(" (")[0])
        if page_result.returncode != 0:
            for line in page_result.stderr.splitlines():
                print(line)
            fail(f"build_edition_page.py failed with exit code {page_result.returncode}")
        if f"edition-{date_str}.html" not in page_files:
            fail("build_edition_page.py did not write the edition page")
        print(f"edition web page: {len(page_files)} files for the bundle")
    else:
        # Manifest-only: a standing edition page and the pictures it
        # names belong to the bundle as they stand.
        page_path = UPLOAD_DIR / f"edition-{date_str}.html"
        if page_path.is_file():
            page_files.append(page_path.name)
            for name in sorted(set(re.findall(
                    r'src="(images/[^"]+)"',
                    page_path.read_text(encoding="utf-8")))):
                if (UPLOAD_DIR / name).is_file():
                    page_files.append(name)
            print(f"edition web page (standing): {len(page_files)} files for the bundle")

    # ---- Steps 2b + 3 + 4: archive_update.py (full mode only) -------------------
    if not args.manifest_only:
        _STEP = "steps 2b-4: archive update"
        cmd = [python, str(BATCH_DIR / "archive_update.py"), date_str]
        print(f"run: {' '.join(cmd)}")
        result = subprocess.run(cmd)
        if result.returncode != 0:
            fail(f"archive_update.py failed with exit code {result.returncode}")

    # ---- manifest ------------------------------------------------------------------
    _STEP = "write manifest"
    # The manifest names a recording only when the file stands in
    # publish-upload/audio/: this edition's, when it recorded, and any
    # queued recording that landed in this run's drain.
    audio_names = []
    if today_mp3.is_file():
        audio_names.append(f"audio/morning-scroll-{date_str}.mp3")
    for landed_date in landed_dates:
        if landed_date == date_str:
            continue
        landed_name = f"audio/morning-scroll-{landed_date}.mp3"
        if (UPLOAD_DIR / landed_name).is_file() and landed_name not in audio_names:
            audio_names.append(landed_name)
    names = ["index.html", "scroll-search-index.json", pdf_name] + audio_names + png_names + page_files
    manifest_lines = [
        "# Morning Scroll publish manifest",
        f"date: {date_str}",
        f"vol: {vol}",
        f"no: {no}",
        f"pages: {page_count}",
        f"built: {datetime.now().astimezone().isoformat(timespec='seconds')}",
        "# md5  bytes  filename",
    ]
    for name in names:
        path = UPLOAD_DIR / name
        if not path.is_file():
            fail(f"manifest input missing from publish-upload: {path}")
        size = path.stat().st_size
        digest = md5_of(path)
        manifest_lines.append(f"{digest}  {size}  {name}")
        print(f"manifest: {name} md5 {digest} ({size} bytes)")
    manifest_path = BATCH_DIR / f"manifest-{date_str}.txt"
    manifest_path.write_text("\n".join(manifest_lines) + "\n", encoding="utf-8")
    print(f"output: manifest {manifest_path}")

    # ---- voice queue: landed entries stand until verify confirms -------------
    # A queue entry whose recording landed on this manifest is NOT
    # cleared here. The bundle still has gates, a publish, and a
    # verify ahead of it; if any of those fail, the entry must still
    # stand so the next run's drain lands the recording again.
    # verify.py clears the entry when it has confirmed the recording
    # on the live site — that confirmation is the only clearing.
    manifest_names = set(names)
    for entry in queue:
        if (entry.get("landed_run") == date_str
                and f"audio/morning-scroll-{entry.get('date')}.mp3" in manifest_names):
            print(f"voice queue: {entry['date']} landed on this manifest — "
                  f"its entry clears when verify confirms the recording "
                  f"on the live site")
    print(f"build_and_manifest done for {date_str}")
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
