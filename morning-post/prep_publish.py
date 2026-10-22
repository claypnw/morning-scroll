#!/usr/bin/env python3
"""Prep a Morning Scroll edition for archive publishing.

Reads the approved PDF + edition.json and writes publish-staging/<date>/:
  scroll-<date>-page-N.png  (alpha PNGs, 1836x2376)
  edition-meta.json         (archive entry: headline, greeting, pages, links)
  search-text.txt           (labeled full-text index sections)
  payson-morning-scroll-<date>.pdf  (copy for GitHub Pages hosting)
"""
import html
import json
import re
import shutil
import sys
from pathlib import Path

import fitz  # PyMuPDF

ROOT = Path(__file__).resolve().parent


# --- Shared error program (standards wiring step A, 2026-10-21) -------------
# The one shared error program is ~/workspace/batch/shared_error.py.
# An error this program did not foresee goes there, and the standard
# processing — write the error down in full in the dated error record,
# open an ERROR line in the completion pile, hand back STOP — happens
# in that one program, never in code copied here. This block is only
# the call. If the shared error program cannot be loaded or cannot
# record, the report prints a loud line on stderr and this program's
# own output and exit behavior are unchanged.
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
# this program's own output or exit code, and a failed record write
# prints a loud line on stderr.
import subprocess as _subprocess
from datetime import datetime as _datetime
from zoneinfo import ZoneInfo as _ZoneInfo


def _finish_writer_path():
    for parent in Path(__file__).resolve().parents:
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
             Path(__file__).name,
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


def strip_html(s: str) -> str:
    s = re.sub(r"<[^>]+>", "", s or "")
    return html.unescape(s).strip()


def main() -> int:
    _write_start_line()
    date = sys.argv[1]
    pdf_src = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "editions" / date / "edition.json"
    ed_path = ROOT / "editions" / date / "edition.json"
    ed = json.loads(ed_path.read_text())
    if len(sys.argv) <= 2:
        pdf_src = Path(
            "~/workspace/goals/morning-agenda-briefing/files/"
            f"payson-morning-scroll-{date}.pdf"
        ).expanduser()
    out = ROOT / "publish-staging" / date
    out.mkdir(parents=True, exist_ok=True)

    doc = fitz.open(pdf_src)
    pages = []
    for i, page in enumerate(doc):
        pix = page.get_pixmap(matrix=fitz.Matrix(3, 3), alpha=True)
        img_name = f"scroll-{date}-page-{i + 1}.png"
        pix.save(out / img_name)
        pw, ph = page.rect.width, page.rect.height
        links = []
        for lk in page.get_links():
            if lk.get("kind") != fitz.LINK_URI or not lk.get("uri"):
                continue
            r = lk["from"]
            links.append(
                {
                    "uri": lk["uri"],
                    "x": round(r.x0 / pw, 5),
                    "y": round(r.y0 / ph, 5),
                    "w": round(r.width / pw, 5),
                    "h": round(r.height / ph, 5),
                }
            )
        pages.append(
            {
                "page": i + 1,
                "image": img_name,
                "width": pix.width,
                "height": pix.height,
                "links": links,
            }
        )

    meta = {
        "date": date,
        "volume": 1 if date < "2027" else 2,
        "number": ed.get("edition"),
        "headline": ed.get("headline", ""),
        "greeting": ed.get("lead", ""),
        "pdf": f"payson-morning-scroll-{date}.pdf",
        "pages": pages,
    }
    (out / "edition-meta.json").write_text(json.dumps(meta, indent=1, ensure_ascii=False))

    # ---- search text, same labeled format as the 2026-09-30 staging file ----
    sec = []

    def add(label, text):
        text = strip_html(text) if text else ""
        if text:
            sec.append(f"[{label}] {text}")

    w = ed.get("weather", {})
    add("headline", ed.get("headline"))
    add("dateline", ed.get("dateline"))
    add("lead", ed.get("lead"))
    add("hero_caption", ed.get("hero_caption"))
    if w:
        add(
            "weather",
            f"{w.get('conditions','')} high {w.get('high','')} low {w.get('low','')} "
            f"rain {w.get('rain','')} sunrise {w.get('sunrise','')} sunset {w.get('sunset','')} "
            f"tomorrow {w.get('tomorrow','')}",
        )
    add("weather_caption", ed.get("weather_caption"))
    oh = ed.get("weather_overheard", "")
    if oh:
        title = ed.get("weather_overheard_title") or "Overheard Last Night"
        sec.append(f"[weather_overheard] {title} — {oh}")
    for grp in ed.get("events_today", []):
        town = grp.get("town", "")
        items = " | ".join(strip_html(it) for it in grp.get("items", []))
        if items:
            sec.append(f"[today {town}] {items}")
    for grp in ed.get("events_week", []):
        items = " | ".join(strip_html(it) for it in grp.get("items", []))
        if items:
            sec.append(f"[week {grp.get('dat','')}] {items}")
    m = ed.get("merchant", {})
    if m:
        add("merchant name", m.get("name"))
        add("merchant town", m.get("town"))
        add("merchant blurb", m.get("blurb"))
        add("merchant review", m.get("review"))
        add("merchant review_src", m.get("review_src"))
        add("merchant why", m.get("why"))
        add("merchant visit", m.get("visit"))
        add("merchant image caption", m.get("image_cap"))
    for t in ed.get("tasks", []):
        add("quest", f"{t.get('title','')} {t.get('note','')}".strip())
    add("due soon", ed.get("due_soon"))
    add("quest caption", ed.get("quest_caption"))
    tale = ed.get("tale", {})
    if tale:
        add("tale title", tale.get("title"))
        add("tale", tale.get("text"))
        add("tale image caption", tale.get("image_cap"))
    if ed.get("council"):
        add("council", ed["council"])
    (out / "search-text.txt").write_text("\n\n".join(sec) + "\n")

    shutil.copy(pdf_src, out / f"payson-morning-scroll-{date}.pdf")
    shutil.copy(pdf_src, ROOT / "pdf-host" / f"payson-morning-scroll-{date}.pdf")
    print(
        f"staged {date}: {doc.page_count} pages, "
        f"links per page {[len(p['links']) for p in pages]}, "
        f"search sections {len(sec)}"
    )
    _write_finish_line(
        f"edition {date} staged for archive publishing",
        str(out / "edition-meta.json"))
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
        _report_to_shared_error("main", exc, kind="unforeseen")
        raise
