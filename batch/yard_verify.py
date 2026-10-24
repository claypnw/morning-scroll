#!/usr/bin/env python3
"""
yard_verify.py — post-publish verification for the yard & estate sales sheets.

For each of the two stable-named PDFs, compares:
  - built  (~/workspace/yard-estate-sales/)
  - live   (https://claypnw.github.io/morning-scroll/, cache-busted download)
  - mirror (~/workspace/BACKUP-github-websites-only/morning-scroll/)

live-vs-built is the verdict driver; mirror-vs-built is a second check.
Either comparison failing, a missing local file, or a download failure
fails the overall verdict. Downloads go to a temporary directory only;
local files are never overwritten.

Stdlib only. Prints full output to stdout and appends the same output to
~/workspace/batch-logs/yard-estate-sales-refresh/YYYY-MM-DD.log
(America/Phoenix date) — appending, so a same-day re-run never destroys
an earlier run's evidence; each run's header carries its timestamp.
If the log write fails, the run is an overall FAIL with that reason
(printed in the output, exit 1) — never an unqualified success.
Last line is exactly:
  VERDICT: PASS
or
  VERDICT: FAIL — <reason>
Exit code 0 on PASS, 1 on FAIL.
"""

import contextlib
import hashlib
import io
import sys
import tempfile
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

TZ = ZoneInfo("America/Phoenix")
HOME = Path.home()
BUILT_DIR = HOME / "workspace" / "yard-estate-sales"
MIRROR_DIR = HOME / "workspace" / "BACKUP-github-websites-only" / "morning-scroll"
LIVE_BASE = "https://claypnw.github.io/morning-scroll"
LOG_DIR = HOME / "workspace" / "batch-logs" / "yard-estate-sales-refresh"

FILENAMES = [
    "payson-yard-estate-sales-today.pdf",
    "payson-yard-estate-sales-upcoming.pdf",
]

# --- Rule log (the admin's design, 2026-10-18) ---------------------------------
# This program writes its own rule-log marks via ~/workspace/batch/rulelog.py
# (design: ~/workspace/morning-post/RULE-LOG-DESIGN.md). Marks are decided by
# values this program itself computed — never by exit code alone and never
# by a default evidence string. Rule logging is additive only: it must never
# change this program's output or exit code, so every call is guarded and
# the writer's own prints are captured, not shown.
try:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import rulelog as _rulelog
except Exception:  # rule log unavailable — the program runs as before
    _rulelog = None

_RL_PATH = None
_RL_TOTAL = 0
_RL_LABELS = {}
_RL_ZERO = set()


def _rl_begin(batch, labels):
    global _RL_PATH, _RL_TOTAL, _RL_LABELS
    _RL_LABELS = dict(labels)
    _RL_TOTAL = len(labels)
    if _rulelog is None:
        return
    try:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            _rulelog.cmd_begin(batch, _rulelog.now().strftime("%Y-%m-%d"), _RL_TOTAL)
        _RL_PATH = buf.getvalue().strip().splitlines()[-1]
    except Exception:
        _RL_PATH = None


def _rl(kind, n, evidence=""):
    if _rulelog is None or _RL_PATH is None:
        return
    try:
        _rulelog.mark(_RL_PATH, n, _RL_LABELS.get(n, f"step_{n}"), kind, evidence)
        if kind == "FAIL":
            _RL_ZERO.add(n)
    except Exception:
        pass


def _rl_finish(failed):
    """Close the rule log. If the program failed but no step stands at 0
    (e.g. the dated-log write flipped the verdict), put the last step
    at 0 with a generic reason — the program's own output carries the
    detail."""
    if _rulelog is None or _RL_PATH is None:
        return
    try:
        if failed and not _RL_ZERO and _RL_TOTAL:
            _rl("FAIL", _RL_TOTAL,
                "program reported failure at exit — see program output for the reason")
        with contextlib.redirect_stdout(io.StringIO()):
            _rulelog.cmd_close(_RL_PATH)
    except Exception:
        pass


# --- Shared error program (standards wiring step A, 2026-10-21) -------------
# The one shared error program is shared_error.py in this same
# directory (~/workspace/batch/). A failed verdict and any unforeseen
# error are reported to it, so an error record opens in the one place.
# The standard processing — write the error down in full in the dated
# error record, open an ERROR line in the completion pile, hand back
# STOP — happens in that one program, never in code copied here. This
# block is only the call. If the shared error program cannot be loaded
# or cannot record, the report prints a loud line on stderr and this
# program's own output, dated log, verdict line, and exit code are
# unchanged.
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
# this program's own output, dated log, verdict line, or exit code,
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


LINES = []


def emit(line=""):
    LINES.append(line)


def md5_and_size(path):
    """Return (md5_hex, size_bytes) for a local file."""
    h = hashlib.md5()
    size = 0
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
            size += len(chunk)
    return h.hexdigest(), size


def download(url, dest):
    """Download url to dest (in a temp dir). Raises on failure."""
    req = urllib.request.Request(url, headers={"User-Agent": "yard_verify/1.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        if getattr(resp, "status", 200) != 200:
            raise urllib.error.HTTPError(url, resp.status, "non-200 response", resp.headers, None)
        with open(dest, "wb") as out:
            for chunk in iter(lambda: resp.read(1024 * 1024), b""):
                out.write(chunk)


def _main():
    _write_start_line()
    _rl_begin("yard", {
        1: "today_live_vs_built",
        2: "today_mirror_vs_built",
        3: "upcoming_live_vs_built",
        4: "upcoming_mirror_vs_built",
    })
    now_phx = datetime.now(TZ)
    stamp = int(time.time())
    emit("yard_verify — post-publish verification for yard & estate sales sheets")
    emit(f"Date (America/Phoenix): {now_phx.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    emit(f"Built dir: {BUILT_DIR}")
    emit(f"Mirror dir: {MIRROR_DIR}")
    emit(f"Live base: {LIVE_BASE}")
    emit("")

    failures = []  # list of human-readable reasons

    with tempfile.TemporaryDirectory(prefix="yard_verify_") as tmp:
        tmpdir = Path(tmp)
        for file_index, filename in enumerate(FILENAMES):
            live_step = 1 + file_index * 2
            mirror_step = 2 + file_index * 2
            _rl("START", live_step)
            _rl("START", mirror_step)
            built_path = BUILT_DIR / filename
            mirror_path = MIRROR_DIR / filename
            live_url = f"{LIVE_BASE}/{filename}?v={stamp}"

            # Built
            built_md5 = built_size = None
            built_err = None
            if built_path.is_file():
                try:
                    built_md5, built_size = md5_and_size(built_path)
                except OSError as e:
                    built_err = str(e)
            else:
                built_err = "missing"

            # Mirror
            mirror_md5 = mirror_size = None
            mirror_err = None
            if mirror_path.is_file():
                try:
                    mirror_md5, mirror_size = md5_and_size(mirror_path)
                except OSError as e:
                    mirror_err = str(e)
            else:
                mirror_err = "missing"

            # Live (download to temp dir only)
            live_md5 = live_size = None
            live_err = None
            dest = tmpdir / filename
            try:
                download(live_url, dest)
                live_md5, live_size = md5_and_size(dest)
            except Exception as e:  # download failure = FAIL, never a soft pass
                live_err = f"{type(e).__name__}: {e}"

            # Comparisons
            if built_err is not None:
                live_cmp = "FAIL"
                mirror_cmp = "FAIL"
                failures.append(f"{filename} built file unavailable ({built_err})")
            else:
                if live_err is not None:
                    live_cmp = "FAIL"
                    failures.append(f"{filename} live download failed ({live_err})")
                elif live_md5 == built_md5 and live_size == built_size:
                    live_cmp = "MATCH"
                else:
                    live_cmp = "FAIL"
                    failures.append(
                        f"{filename} live-vs-built mismatch "
                        f"(built md5={built_md5} size={built_size}, live md5={live_md5} size={live_size})"
                    )

                if mirror_err is not None:
                    mirror_cmp = "FAIL"
                    failures.append(f"{filename} mirror file unavailable ({mirror_err})")
                elif mirror_md5 == built_md5 and mirror_size == built_size:
                    mirror_cmp = "MATCH"
                else:
                    mirror_cmp = "FAIL"
                    failures.append(
                        f"{filename} mirror-vs-built mismatch "
                        f"(built md5={built_md5} size={built_size}, mirror md5={mirror_md5} size={mirror_size})"
                    )

            # Rule-log marks for this file's two comparisons, from the
            # values computed above.
            if built_err is not None:
                _rl("FAIL", live_step, f"{filename} built file unavailable ({built_err})")
                _rl("FAIL", mirror_step, f"{filename} built file unavailable ({built_err})")
            else:
                if live_err is not None:
                    _rl("FAIL", live_step, f"{filename} live download failed ({live_err})")
                elif live_cmp == "MATCH":
                    _rl("OK", live_step, f"{filename} live md5={live_md5} size={live_size} == built md5={built_md5} size={built_size}")
                else:
                    _rl("FAIL", live_step, f"{filename} live-vs-built mismatch (built md5={built_md5} size={built_size}, live md5={live_md5} size={live_size})")
                if mirror_err is not None:
                    _rl("FAIL", mirror_step, f"{filename} mirror file unavailable ({mirror_err})")
                elif mirror_cmp == "MATCH":
                    _rl("OK", mirror_step, f"{filename} mirror md5={mirror_md5} size={mirror_size} == built md5={built_md5} size={built_size}")
                else:
                    _rl("FAIL", mirror_step, f"{filename} mirror-vs-built mismatch (built md5={built_md5} size={built_size}, mirror md5={mirror_md5} size={mirror_size})")

            built_str = f"md5={built_md5} size={built_size}" if built_md5 else f"ERROR ({built_err})"
            live_str = f"md5={live_md5} size={live_size}" if live_md5 else f"ERROR ({live_err})"
            mirror_str = f"md5={mirror_md5} size={mirror_size}" if mirror_md5 else f"ERROR ({mirror_err})"

            emit(
                f"{filename} | built {built_str} | live {live_str} | mirror {mirror_str} "
                f"| live-vs-built {live_cmp} | mirror-vs-built {mirror_cmp}"
            )

    emit("")
    if failures:
        verdict = f"VERDICT: FAIL — {'; '.join(failures)}"
        code = 1
    else:
        verdict = "VERDICT: PASS"
        code = 0
    emit(verdict)

    output = "\n".join(LINES) + "\n"

    # Append the same full output to the dated log (never overwrite:
    # a same-day re-run must not destroy an earlier run's evidence).
    # If the log write fails, the run must not report success: print a
    # clear LOG WRITE FAILED line, change the verdict to FAIL with that
    # reason, and exit 1.
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        log_path = LOG_DIR / f"{now_phx.strftime('%Y-%m-%d')}.log"
        with open(log_path, "a", encoding="utf-8") as log:
            log.write(output)
    except OSError as e:
        reason = f"log write failed ({e})"
        all_reasons = failures + [reason]
        fail_lines = LINES[:-1]  # drop the comparison-only verdict
        fail_lines.append(f"LOG WRITE FAILED: {e}")
        fail_lines.append(f"VERDICT: FAIL — {'; '.join(all_reasons)}")
        sys.stdout.write("\n".join(fail_lines) + "\n")
        sys.stdout.flush()
        _report_to_shared_error(
            "write dated log", f"VERDICT: FAIL — {'; '.join(all_reasons)}",
            kind="foreseen")
        return 1

    sys.stdout.write(output)
    sys.stdout.flush()

    if failures:
        # A failed verdict opens an error record in the one shared
        # error program. The dated log and the verdict line above are
        # unchanged — they are the evidence reports quote.
        _report_to_shared_error("verdict", verdict, kind="check_failed")

    if code == 0:
        _write_finish_line("VERDICT: PASS", str(log_path))

    return code


def main():
    code = None
    try:
        code = _main()
    except SystemExit:
        raise
    except BaseException as exc:
        # Catch-all: an error this program did not foresee goes to the
        # one shared error program, then the program stops as it would
        # have — the traceback still prints.
        _report_to_shared_error("main", exc, kind="unforeseen")
        raise
    finally:
        _rl_finish(failed=(code != 0))
    return code


if __name__ == "__main__":
    sys.exit(main())
