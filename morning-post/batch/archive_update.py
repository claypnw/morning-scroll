#!/usr/bin/env python3
"""Morning Scroll batch job: archive_update.py

Mechanizes PUBLISH-RUNBOOK Steps 2b + 3 + 4 for one edition date:
  - Get a fresh index.html + scroll-search-index.json (downloaded from
    GitHub raw, or copied from --from-dir in test mode).
  - Prepend the new edition to scroll-search-index.json.
  - Add the issue item, reader section, date-slider range, JS edition
    map entry, and cache buster to index.html.

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
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_UPLOAD_DIR = ROOT / "publish-upload"
RAW_BASE = "https://raw.githubusercontent.com/claypnw/morning-scroll/main"
SITE_BASE = "https://claypnw.github.io/morning-scroll"


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


def main():
    parser = argparse.ArgumentParser(description="Update the Morning Scroll archive files for one edition.")
    parser.add_argument("date", help="Edition date, YYYY-MM-DD")
    parser.add_argument("--upload-dir", default=str(DEFAULT_UPLOAD_DIR),
                        help="Directory holding index.html / scroll-search-index.json to write (default: publish-upload)")
    parser.add_argument("--from-dir", default=None,
                        help="Test mode: copy index.html + scroll-search-index.json from this directory instead of downloading")
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
            with urllib.request.urlopen(f"{RAW_BASE}/index.html") as resp:
                index_bytes = resp.read()
            with urllib.request.urlopen(f"{RAW_BASE}/scroll-search-index.json") as resp:
                search_bytes = resp.read()
        except Exception as exc:
            fail(f"download of fresh archive files failed: {exc}", kind="foreseen")
        source_desc = f"downloaded from {RAW_BASE}"
    index_text = index_bytes.decode("utf-8")
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

    headline_esc = html.escape(headline, quote=True)
    greeting_esc = html.escape(greeting, quote=True)
    teaser_raw = greeting if len(greeting) <= 200 else greeting[:200].rstrip() + "…"
    teaser_esc = html.escape(teaser_raw, quote=True)

    issue_item = (
        " " * 40
        + f'<div class="issue-link"><a class="issue-open" href="#edition-{date_str}" '
          f'aria-label="Read the {long_date} edition: {headline_esc}"></a>'
          f'<div class="issue-date"><strong>{weekday},</strong> {month_day_year}</div>'
          f'<div class="issue-copy"><p class="greeting">"{teaser_esc}"</p>'
          f'<h2 class="issue-title">{headline_esc}</h2>'
          f'<div class="issue-number">Vol. {vol} · No. {no}</div></div>'
          f'<div class="issue-actions"><span class="read-mark" aria-hidden="true">→</span>'
          f'<a class="pdf-button" href="{SITE_BASE}/payson-morning-scroll-{date_str}.pdf" '
          f'target="_blank" rel="noopener" referrerpolicy="origin" type="application/pdf" '
          f'aria-label="Download the {long_date} PDF">Download PDF</a></div></div>'
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
        f'          <a class="pdf-button" href="{SITE_BASE}/payson-morning-scroll-{date_str}.pdf" target="_blank" rel="noopener" referrerpolicy="origin" type="application/pdf" aria-label="Download the {long_date} PDF">Download PDF</a>',
        f'          <span class="issue-number">Vol. {vol} · No. {no}</span>',
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
    if new_search_data[0].get("date") != date_str:
        fail("self-check failed: new search entry is not first")
    print(f"self-check: sections {section_count_before} -> {section_count_after}, max date {dates[-1]}, OK")

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
