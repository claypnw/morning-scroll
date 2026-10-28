#!/usr/bin/env python3
"""Morning Scroll batch job: archive_update.py

Mechanizes PUBLISH-RUNBOOK Steps 2b + 3 + 4 for one edition date:
  - Get a fresh index.html + scroll-search-index.json (downloaded from
    GitHub raw, or copied from --from-dir in test mode).
  - Prepend the new edition to scroll-search-index.json.
  - Add the issue item, reader section, date-slider range, JS edition
    map entry, and cache buster to index.html.
  - Point every edition's title link at that edition's web page
    (the admin's ruling, 2026-10-26: the reading road is the web
    page — tonight's and later editions link to their HTML edition
    page; earlier editions link to their standing reader section
    on this page), and take every Download PDF button off the
    archive (the same ruling: the PDF file itself still publishes
    at its address every day; only the buttons go).

No AI judgment inside: every string is built from edition-meta.json,
search-text.txt, and the date, by fixed rules. Prints a plain log,
one line per edit made. Refuses (exit nonzero) if the date is already
in the index or the search index.

Usage:
  venv/bin/python batch/archive_update.py DATE [--upload-dir DIR] [--from-dir DIR]
"""
import argparse
import calendar
import html
import json
import re
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_UPLOAD_DIR = ROOT / "publish-upload"
RAW_BASE = "https://raw.githubusercontent.com/claypnw/morning-scroll/main"
SITE_BASE = "https://claypnw.github.io/morning-scroll"

# An edition's title link on the archive page (the empty overlay
# anchor that makes the whole issue card tappable). The admin's
# ruling (2026-10-26): the reading road is the web page. Editions
# from WEB_PAGE_START on carry an HTML edition page on the site
# (edition-DATE.html, published by the chain as part of the
# bundle), and their title links point at it; earlier editions
# point at their standing reader section on this page
# (#edition-DATE). web_title_links() converts every title link
# that arrives in any older shape (a reader-section link, a PDF
# address, an edition-page address) to the shape its date calls
# for; it changes nothing once converted (idempotent), and the
# new item below is generated with its own address directly.
WEB_PAGE_START = "2026-10-26"
ISSUE_OPEN_RE = re.compile(
    r'(<a class="issue-open" href=")(?:#edition-|'
    + re.escape(SITE_BASE) + r'/payson-morning-scroll-|'
    + re.escape(SITE_BASE) + r'/edition-)(\d{4}-\d{2}-\d{2})'
    r'(?:\.pdf|\.html)?(")')


def title_target(date_str):
    """Where one edition's title link points, by its date: the
    HTML edition page from WEB_PAGE_START on, the standing reader
    section before it."""
    if date_str >= WEB_PAGE_START:
        return f"{SITE_BASE}/edition-{date_str}.html"
    return f"#edition-{date_str}"


def web_title_links(text):
    """Convert every edition title link in `text` to the address
    its date calls for. Returns (new_text, converted_count)."""
    return ISSUE_OPEN_RE.subn(
        lambda mo: f"{mo.group(1)}{title_target(mo.group(2))}{mo.group(3)}",
        text)


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


def fail(message, kind="check_failed"):
    """One failure path: print the ERROR line, hand the error to the one
    shared error program, and exit on the STOP it hands back (its exit
    code: 1, or 2 when the ERROR line could not be confirmed).

    In this program a fail() is a check stopping the work — the base
    check, the duplicate refusal, an anchor, self-check, or JS check —
    so the default kind is check_failed. The few operational paths
    (a missing input file, a failed read or download) pass
    kind="foreseen" at the call site.
    """
    print(f"ERROR: {message}")
    result = _report_to_shared_error(_STEP, message, kind=kind)
    sys.exit(result["exit_code"] if result else 1)


# The two fresh-file downloads climb a step-down ladder
# (2026-10-26, second form after the fresh-eyes review). The first
# form repeated the same whole download at new time limits — and
# its first limit (60 seconds) also changed the success path,
# because the standing download had NO limit: a slow download that
# once landed in one read would have been cut off and restarted.
# The second form keeps the success path exactly as it stood and
# changes only what happens after a failure surfaces:
#   try 1 — the standing call itself, unchanged: one whole read
#     with no time limit set. A download that lands, however
#     slowly, lands as it always did. A silent hang on this try
#     remains governed by the chain's own time budget, exactly as
#     before this change — named here, not hidden.
#   try 2, after a 10-second wait — the file read in parts of at
#     most PART_BYTES, keeping the bytes that arrived and asking
#     only for the missing tail. Each part is checked against the
#     range the server says it sent; a part starting at the wrong
#     byte, or a size changing mid-read, ends the try — pieces of
#     two versions are never joined. A "no such range" answer
#     (416) ends the read only when its stated total equals the
#     bytes in hand. Per-request limit 120 seconds.
#   try 3, after a 20-second wait — the same address fetched by
#     curl, the road that came down whole in the 2026-10-26
#     diagnosis, with a total limit of 180 seconds.
# Tries 2 and 3 together are bounded by DOWNLOAD_DEADLINE_SECONDS
# (600) counted from the first failure, checked between requests
# and between pulls of a body (bodies are pulled with single-pull
# reads so a slow-drip answer cannot hold a read past it). The
# limits on those tries bound each socket operation, not the
# whole read; the deadline is the whole-read bound for them.
# Answers no later try can fix — an HTTP 4xx other than 408
# (time-out) and 429 (busy) — raise at once on any try, named.
# Each failed try is printed with its error; after the third, the
# last error is raised, so the caller's standing failure path
# runs unchanged.
DOWNLOAD_DEADLINE_SECONDS = 600
PART_BYTES = 256 * 1024


def _retryable_http(code):
    return code in (408, 429) or 500 <= code <= 599


def _read_body(resp, deadline_end):
    """Read a response body in pulls, enforcing the deadline
    between pulls; a stated length the body does not reach raises,
    so a short read is a failed try, never a short result."""
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
            raise TimeoutError("the download deadline ran out mid-read")
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


def _read_parts_road(url, timeout, deadline_end):
    got = bytearray()
    total = None
    stalls = 0
    while total is None or len(got) < total:
        if time.monotonic() > deadline_end:
            raise TimeoutError("the download deadline ran out during the parts read")
        start = len(got)
        request = urllib.request.Request(
            url, headers={"Range": f"bytes={start}-{start + PART_BYTES - 1}"})
        try:
            resp = urllib.request.urlopen(request, timeout=timeout)
        except urllib.error.HTTPError as err:
            if err.code == 416:
                _, _, stated_total = _parse_content_range(
                    err.headers.get("Content-Range") if err.headers else None)
                if len(got) > 0 and (stated_total == len(got) or total == len(got)):
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
                return bytes(got)
    return bytes(got)


def _read_curl_road(url, timeout, deadline_end):
    remaining = int(deadline_end - time.monotonic())
    if remaining <= 0:
        raise TimeoutError("the download deadline ran out before the curl try")
    proc = subprocess.run(
        ["/usr/bin/curl", "-fsS", "--max-time", str(min(timeout, remaining)), url],
        capture_output=True)
    if proc.returncode != 0:
        raise OSError(
            f"the curl road failed (exit {proc.returncode}): "
            f"{proc.stderr.decode('utf-8', 'replace').strip()}")
    return proc.stdout


def _download_ladder(url, what):
    """Download one file down the step-down ladder described above
    and return its bytes. After the third failed try the last error
    is raised, so the caller's standing failure path runs."""
    try:
        with urllib.request.urlopen(url) as resp:
            return resp.read()
    except urllib.error.HTTPError as exc:
        if not _retryable_http(exc.code):
            print(f"{what}: answer {exc.code} cannot be fixed by "
                  f"another try; not retrying", flush=True)
            raise
        last_exc = exc
    except Exception as exc:
        last_exc = exc
    # The 600 seconds for tries 2-3 are counted from this failure:
    # the deadline is set before the first wait and checked again
    # before the second wait, so the bound the notes state is the
    # bound the program keeps (up to one body pull already in
    # flight when the deadline passes; pulls are the short reads
    # the parts reader makes).
    deadline_end = time.monotonic() + DOWNLOAD_DEADLINE_SECONDS
    print(f"{what}: try 1 failed ({last_exc}); waiting 10 seconds "
          f"before try 2 (the read in parts)", flush=True)
    time.sleep(10)
    try:
        return _read_parts_road(url, 120, deadline_end)
    except urllib.error.HTTPError as exc:
        if not _retryable_http(exc.code):
            print(f"{what}: answer {exc.code} cannot be fixed by "
                  f"another try; not retrying", flush=True)
            raise
        last_exc = exc
    except Exception as exc:
        last_exc = exc
    print(f"{what}: try 2 failed ({last_exc}); waiting 20 seconds "
          f"before try 3 (the curl road)", flush=True)
    if time.monotonic() >= deadline_end:
        raise TimeoutError(
            f"{what}: the {DOWNLOAD_DEADLINE_SECONDS}-second limit "
            f"for the simpler tries was reached; the last error "
            f"was: {type(last_exc).__name__}: {last_exc}")
    time.sleep(20)
    return _read_curl_road(url, 180, deadline_end)


def main():
    parser = argparse.ArgumentParser(description="Update the Morning Scroll archive files for one edition.")
    parser.add_argument("date", help="Edition date, YYYY-MM-DD")
    parser.add_argument("--upload-dir", default=str(DEFAULT_UPLOAD_DIR),
                        help="Directory holding index.html / scroll-search-index.json to write (default: publish-upload)")
    parser.add_argument("--from-dir", default=None,
                        help="Test mode: copy index.html + scroll-search-index.json from this directory instead of downloading")
    parser.add_argument("--button-mode", default=None, choices=["new", "retry", "none"],
                        help="Where the Read button goes this run (default: read "
                             "batch/button-mode-DATE.json, written by "
                             "build_and_manifest.py; no file means 'new')")
    parser.add_argument("--button-date", default=None,
                        help="For --button-mode retry: the edition whose section "
                             "carries the button")
    args = parser.parse_args()

    global _STEP
    _STEP = "read arguments"
    date_str = args.date
    try:
        day = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        fail(f"bad date {date_str!r} (want YYYY-MM-DD)")

    upload_dir = Path(args.upload_dir).expanduser()

    vol = f"{day.year % 100:02d}{day.month:02d}"
    no = f"{day.day:02d}"
    weekday = calendar.day_name[day.weekday()]
    month_name = calendar.month_name[day.month]
    long_date = f"{weekday}, {month_name} {day.day}, {day.year}"
    month_day_year = f"{month_name} {day.day}, {day.year}"
    month_label = f"{month_name} {day.year}"

    # ---- staging inputs -------------------------------------------------
    _STEP = "read staging inputs"
    staging_dir = ROOT / "publish-staging" / date_str
    meta_path = staging_dir / "edition-meta.json"
    search_text_path = staging_dir / "search-text.txt"
    if not meta_path.is_file():
        fail(f"missing {meta_path}", kind="foreseen")
    if not search_text_path.is_file():
        fail(f"missing {search_text_path}", kind="foreseen")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    if meta.get("date") != date_str:
        fail(f"edition-meta.json date {meta.get('date')!r} does not match {date_str!r}")
    headline = meta.get("headline", "")
    greeting = meta.get("greeting", "")
    # Verbatim, including any trailing newline.
    search_text = search_text_path.read_text(encoding="utf-8")
    print(f"input: {meta_path}")
    print(f"input: {search_text_path} ({len(search_text)} chars)")

    # ---- fresh archive files (into memory first) ------------------------
    _STEP = "get fresh archive files"
    if args.from_dir:
        from_dir = Path(args.from_dir).expanduser()
        try:
            index_bytes = (from_dir / "index.html").read_bytes()
            search_bytes = (from_dir / "scroll-search-index.json").read_bytes()
        except OSError as exc:
            fail(f"could not read fresh files from {from_dir}: {exc}", kind="foreseen")
        source_desc = f"copied from {from_dir}"
    else:
        try:
            index_bytes = _download_ladder(f"{RAW_BASE}/index.html",
                                           "download of the fresh archive page")
            search_bytes = _download_ladder(f"{RAW_BASE}/scroll-search-index.json",
                                            "download of the fresh search list")
        except Exception as exc:
            fail(f"download of fresh archive files failed: {exc}", kind="foreseen")
        source_desc = f"downloaded from {RAW_BASE}"
    index_text = index_bytes.decode("utf-8")

    # ---- Read-button placement for this run ------------------------------
    # build_and_manifest.py works out where the button goes and writes
    # batch/button-mode-DATE.json; the explicit flags win over the file,
    # and no file and no flags means "new" — the button on this
    # edition, the plain case (and the only case before this change).
    # "new": this edition's recording stands, the button goes on this
    # edition. "retry": this edition's recording is missing, but a
    # queued earlier recording landed this run, so the button goes on
    # that edition (button_date). "none": no button moves — the one
    # standing, on the newest edition that has a recording, stays.
    _STEP = "read-button placement"
    button_mode = args.button_mode
    button_date = args.button_date
    if button_mode is None:
        mode_path = Path(__file__).resolve().parent / f"button-mode-{date_str}.json"
        if mode_path.is_file():
            try:
                mode_data = json.loads(mode_path.read_text(encoding="utf-8"))
                button_mode = mode_data.get("mode")
                button_date = mode_data.get("button_date")
            except Exception as exc:
                fail(f"button-mode file {mode_path} did not read as JSON: {exc}",
                     kind="foreseen")
        else:
            button_mode = "new"
    if button_mode not in ("new", "retry", "none"):
        fail(f"bad button mode {button_mode!r} (want new, retry, or none)")
    if button_mode == "retry" and not button_date:
        fail("button mode 'retry' needs a button date (the landed edition)")
    input_btn_count = index_text.count('<button class="scroll-read-btn"')
    print(f"read-button placement: mode {button_mode}"
          + (f", button edition {button_date}" if button_mode == "retry" else "")
          + f" (buttons on the incoming page: {input_btn_count})")
    try:
        search_data = json.loads(search_bytes.decode("utf-8"))
    except Exception as exc:
        fail(f"fresh scroll-search-index.json is not valid JSON: {exc}", kind="foreseen")
    if not isinstance(search_data, list):
        fail("fresh scroll-search-index.json is not a list")

    # ---- previous-edition base guard (Q5) --------------------------------
    _STEP = "base check"
    # The downloaded base must be CURRENT: it has to contain the previous
    # edition (the newest edition on local record before this one), in
    # both the search index and the page, with nothing in between. A stale
    # base (CDN lag, an old raw copy) would silently drop recent editions
    # from the archive — stop loudly instead.
    batch_dir = Path(__file__).resolve().parent
    local_dates = set()
    staging_root = ROOT / "publish-staging"
    if staging_root.is_dir():
        for child in staging_root.iterdir():
            if child.is_dir() and re.fullmatch(r"\d{4}-\d{2}-\d{2}", child.name):
                local_dates.add(child.name)
    for manifest_file in batch_dir.glob("manifest-*.txt"):
        m = re.fullmatch(r"manifest-(\d{4}-\d{2}-\d{2})\.txt", manifest_file.name)
        if m:
            local_dates.add(m.group(1))
    prior_local = sorted(d for d in local_dates if d < date_str)
    if not prior_local:
        fail(f"BASE CHECK FAILED: no local record of any edition before {date_str} "
             f"(looked in publish-staging/ and batch/manifest-*.txt) — cannot confirm "
             f"the downloaded base is current; stopping")
    expected_prev = prior_local[-1]
    base_dates = sorted({e.get("date") for e in search_data if isinstance(e, dict) and e.get("date")})
    base_prior = [d for d in base_dates if d < date_str]
    if not base_prior or base_prior[-1] != expected_prev:
        fail(f"BASE CHECK FAILED: downloaded base's newest edition before {date_str} is "
             f"{base_prior[-1] if base_prior else 'none'} but the previous edition on record is "
             f"{expected_prev} — the base is stale; stopping before any edit")
    if f'id="edition-{expected_prev}"' not in index_text:
        fail(f"BASE CHECK FAILED: downloaded index.html has no reader section for the previous "
             f"edition {expected_prev} — the base is stale; stopping before any edit")
    print(f"base check: previous edition {expected_prev} confirmed in the downloaded base "
          f"(search index + reader section)")

    # ---- refuse duplicates ----------------------------------------------
    if f'id="edition-{date_str}"' in index_text:
        fail(f"REFUSED: edition {date_str} already appears in index.html (id=\"edition-{date_str}\")")
    if any(isinstance(e, dict) and e.get("date") == date_str for e in search_data):
        fail(f"REFUSED: edition {date_str} already appears in scroll-search-index.json")

    # ---- take the Download PDF buttons off (2026-10-26 ruling) ----------
    # The reading road is the web page now, so no Download PDF
    # button stands anywhere on the archive: the buttons in the
    # downloaded base (one on each issue card, one in each reader
    # section) come off here, and the new item and reader section
    # below are generated without one. The PDF file itself still
    # publishes at its address every day — only the buttons go.
    # The self-check at the end fails the run if any button
    # survives.
    _STEP = "download-button removal"
    index_text, removed_btns = re.subn(
        r'<a class="pdf-button"[^>]*>Download PDF</a>', "", index_text)
    print(f"edit: {removed_btns} Download PDF button(s) taken off the archive page")

    # ---- place the fresh copies in the upload dir ------------------------
    upload_dir.mkdir(parents=True, exist_ok=True)
    (upload_dir / "index.html").write_bytes(index_bytes)
    (upload_dir / "scroll-search-index.json").write_bytes(search_bytes)
    print(f"fresh index.html {source_desc} -> {upload_dir / 'index.html'} ({len(index_bytes)} bytes)")
    print(f"fresh scroll-search-index.json {source_desc} -> {upload_dir / 'scroll-search-index.json'} ({len(search_bytes)} bytes)")

    # ---- hashed page PNGs must already be in the upload dir -------------
    png_re = re.compile(rf"^scroll-{re.escape(date_str)}-page-(\d+)-r1-.+\.png$")
    pngs = []
    for path in upload_dir.iterdir():
        m = png_re.match(path.name)
        if m:
            pngs.append((int(m.group(1)), path.name))
    pngs.sort()
    if not pngs:
        fail(f"no hashed page PNGs for {date_str} found in {upload_dir} "
             f"(expected scroll-{date_str}-page-N-r1-<hash>.png; run the PNG copy step first)")
    print(f"hashed PNGs found: {len(pngs)} ({pngs[0][1]} .. {pngs[-1][1]})")

    # ---- search index edit ----------------------------------------------
    _STEP = "archive edits"
    new_entry = {
        "date": date_str,
        "headline": headline,
        "greeting": greeting,
        "text": search_text,
        "vol": vol,
        "no": no,
    }
    new_search_data = [new_entry] + search_data
    # Matches the current file format exactly: indent=1, no trailing newline.
    search_out = json.dumps(new_search_data, indent=1, ensure_ascii=False)
    print(f"edit: scroll-search-index.json prepended entry for {date_str} (Vol. {vol}, No. {no})")

    # ---- index.html edits (line based, anchors checked) ------------------
    had_trailing_newline = index_text.endswith("\n")
    lines = index_text.splitlines()

    def count_lines_with(needle):
        return sum(1 for ln in lines if needle in ln)

    # Anchor pre-checks: each anchor must be found exactly once.
    if count_lines_with("var editions = {") != 1:
        fail('anchor check failed: "var editions = {" not found exactly once')
    if count_lines_with('<input id="date-range-start"') != 1:
        fail('anchor check failed: <input id="date-range-start"> not found exactly once')
    if count_lines_with('<input id="date-range-end"') != 1:
        fail('anchor check failed: <input id="date-range-end"> not found exactly once')
    cache_re = re.compile(r"scroll-search-index\.json\?v=\d+")
    if len(cache_re.findall(index_text)) != 1:
        fail("anchor check failed: scroll-search-index.json?v=<digits> not found exactly once")
    section_count_before = sum(ln.count('<section class="edition-view"') for ln in lines)
    if section_count_before < 1:
        fail('anchor check failed: no existing <section class="edition-view"> found')
    print(f"anchor check: all anchors found exactly once (edition sections before: {section_count_before})")

    # a0. Edition title links point at the editions' web pages ---------
    # The admin's ruling (2026-10-26), see web_title_links() above:
    # every existing edition's title link is converted to the
    # address its date calls for, and the new item below is
    # generated with its own address directly. Nothing else on the
    # page changes.
    converted = 0
    for i, ln in enumerate(lines):
        new_ln, n = web_title_links(ln)
        if n:
            lines[i] = new_ln
            converted += n
    print(f"edit: {converted} existing edition title link(s) now point at their web pages")

    headline_esc = html.escape(headline, quote=True)
    greeting_esc = html.escape(greeting, quote=True)
    teaser_raw = greeting if len(greeting) <= 200 else greeting[:200].rstrip() + "…"
    teaser_esc = html.escape(teaser_raw, quote=True)

    issue_item = (
        " " * 40
        + f'<div class="issue-link"><a class="issue-open" href="{title_target(date_str)}" '
          f'aria-label="Read the {long_date} edition: {headline_esc}"></a>'
          f'<div class="issue-date"><strong>{weekday},</strong> {month_day_year}</div>'
          f'<div class="issue-copy"><p class="greeting">"{teaser_esc}"</p>'
          f'<h2 class="issue-title">{headline_esc}</h2>'
          f'<div class="issue-number">Vol. {vol} · No. {no}</div></div>'
          f'<div class="issue-actions"><span class="read-mark" aria-hidden="true">→</span></div></div>'
    )

    # a. Issue item + month count ------------------------------------------
    details_idx = [i for i, ln in enumerate(lines) if '<details class="month"' in ln]
    if not details_idx:
        fail('anchor check failed: no <details class="month"> block found')
    block_start = None
    for start in details_idx:
        for ln in lines[start:start + 8]:
            if f"<span>{month_label}</span>" in ln:
                block_start = start
                break
        if block_start is not None:
            break
    if block_start is not None:
        count_re = re.compile(r'(<span class="count">)(\d+)( editions</span>)')
        count_done = False
        for i in range(block_start, min(block_start + 8, len(lines))):
            m = count_re.search(lines[i])
            if m:
                old_n = int(m.group(2))
                lines[i] = count_re.sub(rf"\g<1>{old_n + 1}\g<3>", lines[i], count=1)
                count_done = True
                print(f"edit: month {month_label} count {old_n} -> {old_n + 1} editions")
                break
        if not count_done:
            fail(f'anchor check failed: no <span class="count"> in the {month_label} month block')
        insert_at = None
        block_end = next((s for s in details_idx if s > block_start), len(lines))
        for i in range(block_start, block_end):
            if '<div class="issue-link">' in lines[i]:
                insert_at = i
                break
        if insert_at is None:
            fail(f"anchor check failed: no issue-link div in the {month_label} month block")
        lines.insert(insert_at, issue_item)
        print(f"edit: issue item for {date_str} inserted at top of {month_label} block")
    else:
        new_block = [
            '        <details class="month" open>',
            '          <summary>',
            f'            <span>{month_label}</span>',
            '            <span class="count">1 editions</span>',
            '          </summary>',
            issue_item,
            '        </details>',
            '',
        ]
        lines[details_idx[0]:details_idx[0]] = new_block
        print(f"edit: created new month block for {month_label} with the {date_str} issue item")

    # b. Reader section ------------------------------------------------------
    reader_lines = [
        " " * 32 + f'<section class="edition-view" id="edition-{date_str}" hidden aria-labelledby="edition-title-{date_str}">',
        '        <nav class="back-row" aria-label="Archive navigation">',
        '          <a class="back-link" href="#archive"><span aria-hidden="true">←</span> All editions</a>',
        f'          <span class="issue-number">Vol. {vol} · No. {no}</span>',
        '          <button class="scroll-read-btn" id="scroll-read-btn" type="button">Read this edition aloud</button>',
        '        </nav>',
        '        <article class="edition-sheet">',
        '          <header class="edition-heading">',
        '            <div>',
        f'              <p class="date">{long_date}</p>',
        f'              <h1 id="edition-title-{date_str}">{headline_esc}</h1>',
        f'              <p class="edition-greeting">“{greeting_esc}”</p>',
        '            </div>',
        '          </header>',
        '          <div class="reader-label">',
        '            <p>Tap a page to read it full-size.</p>',
        '          </div>',
        '          <div class="page-reader">',
    ]
    for page_no, png_name in pngs:
        reader_lines.append(
            " " * 10 + f'<img src="{png_name}" alt="Page {page_no} of the {long_date} edition">'
        )
    reader_lines += [
        '          </div>',
        '        </article>',
        '      </section>',
        '',
    ]
    first_section = next(i for i, ln in enumerate(lines) if '<section class="edition-view"' in ln)
    lines[first_section:first_section] = reader_lines
    print(f"edit: reader section for {date_str} inserted before the previous newest section ({len(pngs)} page images)")

    # b2. Read-button placement. The button lives on exactly one
    # edition: the newest one whose recording stands. Which edition
    # that is comes from the placement read at the top of this run
    # (build_and_manifest.py works it out from the recording and the
    # retry queue): "new" — this edition's recording stands; the
    # button is in the reader lines just inserted, and it comes off
    # every earlier section. "retry" — this edition's recording is
    # missing, but a queued earlier recording landed this run; the
    # button goes on that edition's section (button_date) and off
    # every other. "none" — this edition's recording is missing and
    # nothing landed; the just-inserted section's button line comes
    # off, and the button standing on an earlier edition stays where
    # it is. A section spans from its edition-id line to its own
    # closing </section>.
    def section_span(sec_id):
        start = next((i for i, ln in enumerate(lines) if f'id="{sec_id}"' in ln), None)
        if start is None:
            return None
        end = next((i for i in range(start, len(lines)) if '</section>' in lines[i]), None)
        return (start, end) if end is not None else None

    btn_line = ('          <button class="scroll-read-btn" id="scroll-read-btn" '
                'type="button">Read this edition aloud</button>')
    if button_mode in ("new", "retry"):
        target_id = f"edition-{date_str if button_mode == 'new' else button_date}"
        span = section_span(target_id)
        if span is None:
            fail(f"button placement failed: no reader section {target_id} on the page")
        removed = 0
        for i in range(len(lines) - 1, -1, -1):
            if '<button class="scroll-read-btn"' in lines[i] and not (span[0] <= i <= span[1]):
                del lines[i]
                removed += 1
        span = section_span(target_id)
        in_target = [i for i in range(span[0], span[1] + 1)
                     if '<button class="scroll-read-btn"' in lines[i]]
        if len(in_target) > 1:
            fail(f"button placement failed: section {target_id} carries "
                 f"{len(in_target)} read buttons (want one)")
        if not in_target:
            nav_idx = [i for i in range(span[0], span[1] + 1)
                       if '<span class="issue-number">' in lines[i]]
            if len(nav_idx) != 1:
                fail(f"button placement failed: no issue-number line in section "
                     f"{target_id} to set the button beside")
            lines.insert(nav_idx[0] + 1, btn_line)
            print(f"edit: read button set on {target_id} (mode {button_mode})")
        else:
            print(f"edit: read button stands on {target_id} (mode {button_mode})")
        if removed:
            print(f"edit: read button removed from {removed} other section(s) — "
                  f"it lives on the newest edition whose recording stands")
    else:
        span = section_span(f"edition-{date_str}")
        if span is not None:
            for i in range(span[1], span[0] - 1, -1):
                if '<button class="scroll-read-btn"' in lines[i]:
                    del lines[i]
                    print(f"edit: no read button on edition {date_str} — its "
                          f"recording is missing, so the edition publishes "
                          f"without one (mode none)")

    # c. Date slider ----------------------------------------------------------
    dates = sorted({e.get("date") for e in new_search_data if isinstance(e, dict) and e.get("date")})
    maxidx = len(dates) - 1

    def fix_slider(which, set_value):
        idxs = [i for i, ln in enumerate(lines) if f'<input id="date-range-{which}"' in ln]
        if len(idxs) != 1:
            fail(f"anchor check failed: date-range-{which} input found {len(idxs)} times")
        i = idxs[0]
        ln = lines[i]
        for attr, val in (("max", str(maxidx)), ("data-min-date", dates[0]), ("data-max-date", dates[-1])):
            ln, n = re.subn(rf'{attr}="[^"]*"', f'{attr}="{val}"', ln, count=1)
            if n != 1:
                fail(f"anchor check failed: {attr} not found on date-range-{which} input")
        if set_value:
            ln, n = re.subn(r'value="[^"]*"', f'value="{maxidx}"', ln, count=1)
            if n != 1:
                fail("anchor check failed: value not found on date-range-end input")
        lines[i] = ln

    fix_slider("start", set_value=False)
    fix_slider("end", set_value=True)
    print(f"edit: date slider max={maxidx}, data-min-date={dates[0]}, data-max-date={dates[-1]}, end value={maxidx}")

    # d. JS edition map --------------------------------------------------------
    map_idx = [i for i, ln in enumerate(lines) if "var editions = {" in ln]
    if len(map_idx) != 1:
        fail('anchor check failed: "var editions = {" line not unique at map edit')
    entry_lines = [
        " " * 32 + f"'#edition-{date_str}': {{",
        f"            element: document.getElementById('edition-{date_str}'),",
        '          },',
    ]
    lines[map_idx[0] + 1:map_idx[0] + 1] = entry_lines
    print(f"edit: JS edition map entry added for #edition-{date_str}")

    # e. Cache buster -----------------------------------------------------------
    buster = f"scroll-search-index.json?v={date_str.replace('-', '')}"
    done = False
    for i, ln in enumerate(lines):
        if cache_re.search(ln):
            lines[i] = cache_re.sub(buster, ln, count=1)
            done = True
            break
    if not done:
        fail("anchor check failed: cache buster pattern vanished before edit")
    print(f"edit: cache buster set to {buster}")

    # f. Self-check before writing ----------------------------------------------
    final_text = "\n".join(lines) + ("\n" if had_trailing_newline else "")
    section_count_after = final_text.count('<section class="edition-view"')
    if section_count_after != section_count_before + 1:
        fail(f"self-check failed: edition section count {section_count_before} -> {section_count_after} (want +1)")
    if dates[-1] != date_str:
        fail(f"self-check failed: new date {date_str} is not the max date ({dates[-1]})")
    if final_text.count(f'id="edition-{date_str}"') != 1:
        fail(f'self-check failed: id="edition-{date_str}" does not appear exactly once after edits')
    # Title-link audit (the admin's ruling, 2026-10-26): every
    # edition's title link must point where its date calls for —
    # the HTML edition page for WEB_PAGE_START and later, the
    # standing reader section for earlier editions — and no other
    # shape may stand on the page.
    for _m in re.finditer(r'class="issue-open" href="([^"]+)"', final_text):
        _href = _m.group(1)
        _dm = re.search(r'(\d{4}-\d{2}-\d{2})', _href)
        if not _dm or _href != title_target(_dm.group(1)):
            fail(f"self-check failed: an edition title link points at "
                 f"{_href!r}, not at the web page its date calls for")
    if 'class="pdf-button"' in final_text or '>Download PDF<' in final_text:
        fail("self-check failed: a Download PDF button still stands "
             "on the archive page")
    if new_search_data[0].get("date") != date_str:
        fail("self-check failed: new search entry is not first")
    btn_total = final_text.count('<button class="scroll-read-btn"')
    if button_mode in ("new", "retry"):
        target_id = f"edition-{date_str if button_mode == 'new' else button_date}"
        sec_start = final_text.find(f'id="{target_id}"')
        sec_end = final_text.find('</section>', sec_start) if sec_start >= 0 else -1
        btn_at = final_text.find('<button class="scroll-read-btn"')
        if btn_total != 1 or sec_start < 0 or not (sec_start < btn_at < sec_end):
            fail(f'self-check failed: the read button must appear exactly once, '
                 f'inside section {target_id} (mode {button_mode}); found '
                 f'{btn_total} on the page')
    else:
        if btn_total != input_btn_count or btn_total > 1:
            fail(f'self-check failed: button mode "none" must leave the page '
                 f'button as it stood ({input_btn_count}); found {btn_total}')
    print(f"self-check: sections {section_count_before} -> {section_count_after}, max date {dates[-1]}, "
          f"read button count {btn_total} (mode {button_mode}), OK")

    # h. Read-button furniture: the button styles and the player script.
    # They are page furniture, not per-edition content: inserted once,
    # on the first run of this change, and left standing after that —
    # the guard is the "scroll-read-player" marker in the script. The
    # player takes the edition date from the button's own section id,
    # so the same script serves each day's newest edition. If the
    # recording cannot load or play, the player shows a plain-words
    # line under the button saying so — a failed tap is never silent.
    # Runs before
    # the JS validation below, so the player is syntax-checked with
    # the rest of the page script on every run.
    # Archive fallback update (2026-10-27): a page carrying the first
    # player (marker "scroll-read-player" without the archive fallback)
    # has that player block lifted out here, so the new block below —
    # the same player with the archive road added — takes its place.
    if "scroll-read-player-archive" not in final_text and "scroll-read-player" in final_text:
        s0 = final_text.find("/* scroll-read-player */")
        tag0 = final_text.rfind("<script>", 0, s0)
        end0 = final_text.find("</script>", s0)
        if tag0 >= 0 and end0 > s0:
            final_text = final_text[:tag0] + final_text[end0 + len("</script>"):]
            print("edit: the first read player was lifted out — the archive-fallback player takes its place")
    if "scroll-read-player-archive" not in final_text:
        if final_text.count("</head>") != 1 or final_text.count("</body>") != 1:
            fail("anchor check failed: read-button furniture needs exactly one "
                 "</head> and one </body> to attach to")
        style_block = (
            "<style>\n"
            ".scroll-read-btn{font:inherit;font-size:0.9em;padding:8px 16px;"
            "border:1px solid #8a6d3b;border-radius:6px;background:#f7f0dc;"
            "color:#3a2f16;cursor:pointer}\n"
            ".scroll-read-btn.reading{background:#8a6d3b;color:#fff}\n"
            ".scroll-read-note{display:block;margin-top:6px;font-size:0.9em;"
            "color:#7a1f1f}\n"
            ".scroll-read-note[hidden]{display:none}\n"
            "</style>\n"
        )
        final_text = final_text.replace("</head>", style_block + "</head>", 1)
        player_block = (
            "<script>\n"
            "/* scroll-read-player-archive */\n"
            "(function(){\n"
            "  var audio = new Audio();\n"
            "  audio.preload = 'none';\n"
            "  var triedArchive = false;\n"
            "  var btn = document.querySelector('.scroll-read-btn');\n"
            "  if (!btn) return;\n"
            "  var section = btn.closest('section');\n"
            "  var date = section ? section.id.replace('edition-', '') : '';\n"
            "  var note = document.createElement('span');\n"
            "  note.className = 'scroll-read-note';\n"
            "  note.setAttribute('role', 'status');\n"
            "  note.hidden = true;\n"
            "  btn.after(note);\n"
            "  function showNote(){\n"
            "    note.textContent = 'The reading could not be played. The recording for this edition is not available right now.';\n"
            "    note.hidden = false;\n"
            "  }\n"
            "  function stopAll(){\n"
            "    audio.pause();\n"
            "    try { audio.currentTime = 0; } catch(e) {}\n"
            "    btn.textContent = 'Read this edition aloud';\n"
            "    btn.classList.remove('reading');\n"
            "  }\n"
            "  audio.addEventListener('ended', stopAll);\n"
                        "  audio.addEventListener('error', function(){\n"
            "    if (btn.classList.contains('reading')){ fallback(); }\n"
            "  });\n"
            "  function fallback(){\n"
            "    if (!triedArchive && date){\n"
            "      triedArchive = true;\n"
            "      audio.src = 'https://raw.githubusercontent.com/claypnw/scroll-archive-1/main/audio/morning-scroll-' + date + '.mp3';\n"
            "      var p = audio.play();\n"
            "      if (p && p.catch) p.catch(function(){ stopAll(); showNote(); });\n"
            "    } else { stopAll(); showNote(); }\n"
            "  }\n"
            "  btn.addEventListener('click', function(){\n"
            "    if (!audio.paused){ stopAll(); return; }\n"
            "    note.hidden = true;\n"
            "    triedArchive = false;\n"
            "    if (!date){ showNote(); return; }\n"
            "    if (!audio.src) audio.src = 'audio/morning-scroll-' + date + '.mp3';\n"
            "    btn.textContent = 'Stop';\n"
            "    btn.classList.add('reading');\n"
            "    var p = audio.play();\n"
                        "    if (p && p.catch) p.catch(function(){ fallback(); });\n"
            "  });\n"
            "})();\n"
            "</script>\n"
        )
        final_text = final_text.replace("</body>", player_block + "</body>", 1)
        print("edit: read-button styles and player script added to the page "
              "(first run of this change)")
    else:
        print("read-button styles and player script already stand on the page — "
              "left as they are")

    # g. JavaScript validation (Q8, runbook Step 3.4) --------------------------
    # The edition-map entry was just inserted into the page's script; a
    # malformed entry breaks the whole script silently. Extract every
    # JavaScript <script> block (no src=, no non-JS type) and syntax-check
    # the joined source with node --check before anything is written.
    script_blocks = []
    for m in re.finditer(r"<script\b([^>]*)>(.*?)</script>", final_text, re.DOTALL | re.IGNORECASE):
        attrs, body = m.group(1), m.group(2)
        if re.search(r"\bsrc\s*=", attrs, re.IGNORECASE):
            continue
        type_m = re.search(r'type\s*=\s*"([^"]*)"', attrs, re.IGNORECASE)
        if type_m and type_m.group(1).lower() not in ("text/javascript", "application/javascript", "module"):
            continue
        script_blocks.append(body)
    if not script_blocks:
        fail("JS CHECK FAILED: no JavaScript <script> blocks found in index.html")
    joined_script = "\n;\n".join(script_blocks)
    if f"'#edition-{date_str}'" not in joined_script:
        fail(f"JS CHECK FAILED: the edition map entry '#edition-{date_str}' is not in the page script")
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as tmp:
        tmp.write(joined_script)
        tmp_path = tmp.name
    result = subprocess.run(["node", "--check", tmp_path], capture_output=True, text=True)
    Path(tmp_path).unlink(missing_ok=True)
    if result.returncode != 0:
        fail(f"JS CHECK FAILED: node --check rejected the page script after the map edit: "
             f"{(result.stderr or result.stdout).strip()[:400]}")
    print(f"js check: page script validates with node --check ({len(script_blocks)} script blocks, "
          f"edition map entry present)")

    # ---- write -------------------------------------------------------------------
    _STEP = "write archive files"
    (upload_dir / "index.html").write_text(final_text, encoding="utf-8")
    (upload_dir / "scroll-search-index.json").write_text(search_out, encoding="utf-8")
    print(f"wrote: {upload_dir / 'index.html'} ({len(final_text.encode('utf-8'))} bytes)")
    print(f"wrote: {upload_dir / 'scroll-search-index.json'} ({len(search_out.encode('utf-8'))} bytes, no trailing newline)")
    print(f"archive_update done for {date_str}")
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
