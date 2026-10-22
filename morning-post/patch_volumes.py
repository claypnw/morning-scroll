#!/usr/bin/env python3
"""Surgically renumber the masthead 'Vol. X, No. Y' in old Morning Scroll PDFs.

Only the masthead strip text changes; parchment, stains, edges, folios and
all other content stay byte-identical. Usage:
    patch_volumes.py <input.pdf> <output.pdf> <new_vol> <new_no>
"""
import fitz, re, sys

# --- Shared error program (standards wiring step C, 2026-10-21) -------------
# The one shared error program is ~/workspace/batch/shared_error.py.
# An error in this program goes there, and the standard processing —
# write the error down in full in the dated error record, open an
# ERROR line in the completion pile, append the problem entry to the
# quality record, hand back STOP — happens in that one program, never
# in code copied here. This block is only the call. If the shared
# error program cannot be loaded or cannot record, the report prints
# a loud line on stderr and this program's own output and exit
# behavior are unchanged.
from pathlib import Path as _Path


def _load_shared_error():
    for parent in _Path(__file__).resolve().parents:
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
            program=_Path(__file__).name, step=step, error=error, kind=kind,
            error_type="FailedVerdict" if kind == "check_failed" else None)
    except Exception as exc:
        print(f"SHARED ERROR PROGRAM FAILED — error not recorded: {exc}",
              file=sys.stderr)
        return None


# --- Start and finish records (standards wiring step C, 2026-10-21) --------
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

SERIF = "/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf"
BIG, SMALL = 8.5, 5.96
INK = (0.1, 0.1, 0.1)

def find_section(page):
    """Return (start_idx, end_idx, spans) for 'Morning Edition — Vol. a, No. b'."""
    d = page.get_text("dict")
    spans = []
    for block in d["blocks"]:
        for line in block.get("lines", []):
            for s in line["spans"]:
                spans.append(s)
    joined = "".join(s["text"] for s in spans)
    m = re.search(r"morning edition\s*—\s*vol\.\s*(\d+),\s*no\.\s*(\d+)",
                  joined, re.IGNORECASE)
    if not m:
        raise RuntimeError("masthead section not found")
    # map char offsets back to span indices
    offs, acc = [], 0
    for idx, s in enumerate(spans):
        offs.append(acc)
        acc += len(s["text"])
    def span_at(pos):
        for idx, o in enumerate(offs):
            if o <= pos < o + len(spans[idx]["text"]):
                return idx
        return len(spans) - 1
    s0, s1 = span_at(m.start()), span_at(m.end() - 1)
    return s0, s1, spans, m.group(1), m.group(2)

def smallcaps_sizes(word):
    """Per-char font sizes replicating the small-caps look."""
    out = []
    first = True
    for ch in word:
        if ch == " ":
            out.append((ch, SMALL)); first = True; continue
        if first:
            out.append((ch, BIG)); first = False
        elif ch.islower():
            out.append((ch, SMALL))
        else:
            out.append((ch, BIG))
    return out

def main():
    _write_start_line()
    src, dst, new_vol, new_no = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4])
    doc = fitz.open(src)
    page = doc[0]
    s0, s1, spans, old_vol, old_no = find_section(page)
    new_text = "Morning Edition \u2014 Vol. %s, No. %02d" % (new_vol, new_no)
    print("replacing 'Vol. %s, No. %s' -> 'Vol. %s, No. %02d'" % (old_vol, old_no, new_vol, new_no))

    # union rect of the section spans, padded
    r = fitz.Rect(spans[s0]["bbox"])
    for s in spans[s0 + 1:s1 + 1]:
        r |= fitz.Rect(s["bbox"])
    r.x0 -= 1.5; r.x1 += 1.5; r.y0 -= 1.0; r.y1 += 1.0

    # remove the old glyphs via redaction, keeping images (the parchment)
    # and line art (the rules) intact; then typeset the replacement
    page.add_redact_annot(r, fill=None)
    page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE,
                          graphics=fitz.PDF_REDACT_LINE_ART_NONE)

    # typeset the replacement in Liberation Serif, small-caps style
    # (TextWriter + explicit Font: insert_text mis-maps the em-dash)
    font = fitz.Font(fontfile=SERIF)
    tw = fitz.TextWriter(page.rect)
    baseline = spans[s0]["bbox"][1] + BIG * font.ascender
    x = spans[s0]["bbox"][0]
    for word in new_text.split(" "):
        for ch, size in smallcaps_sizes(word):
            tw.append(fitz.Point(x, baseline), ch, font=font, fontsize=size)
            x += font.text_length(ch, size)
        x += font.text_length(" ", SMALL)  # word space
    tw.write_text(page, overlay=True, color=INK)
    doc.save(dst, garbage=3, deflate=True)
    print("wrote", dst)
    _write_finish_line("masthead renumbered", dst)

if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except BaseException as exc:
        # Catch-all: an error this program did not foresee goes to the
        # one shared error program, then the program stops as it would
        # have — the traceback still prints.
        _report_to_shared_error("main", exc, kind="unforeseen")
        raise
