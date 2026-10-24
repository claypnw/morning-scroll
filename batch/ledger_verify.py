#!/usr/bin/env python3
"""Post-publish verification + state gating for The Steward's Ledger.

Verifies that the locally built edition HTML and archive index match
what is live on GitHub Pages (md5), and that the local backup mirror
matches local as a second check. State (edition_number / last_edition)
is only written when the verdict is PASS and --apply-state is given.

Stdlib only. Prints full output to stdout and writes the same output to
~/workspace/batch-logs/stewards-ledger-daily/YYYY-MM-DD.log
(America/Phoenix date of the run).

State writes are crash-safe (atomic): new JSON is written to a temp file
in the same folder, flushed + fsynced, then os.replace()d over the state
file, preserving the state file's permissions — the file is always fully
old or fully new, never truncated.

The dated batch log is the evidence: if writing it fails, the outcome
becomes FAIL (exit 1), even when all checks passed.

Last line is exactly:
  VERDICT: PASS
or
  VERDICT: FAIL — <reason>
Exit 0 on PASS, 1 on FAIL.
"""
import argparse
import contextlib
import hashlib
import io
import json
import os
import stat
import sys
import tempfile
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

HOME = Path.home()
WORKSPACE = HOME / "workspace"
JOBDIR = "stewards-ledger-daily"
LOG_DIR = WORKSPACE / "batch-logs" / JOBDIR
DEFAULT_STATE = WORKSPACE / "stewards-ledger" / "state.json"
EDITION_LOCAL_TMPL = str(WORKSPACE / "stewards-ledger" / "editions" / "stewards-ledger-{date}.html")
EDITION_MIRROR_TMPL = str(WORKSPACE / "BACKUP-github-websites-only" / "morning-scroll" / "stewards-ledger-{date}.html")
EDITION_LIVE_TMPL = "https://claypnw.github.io/morning-scroll/stewards-ledger-{date}.html"
INDEX_LOCAL = WORKSPACE / "yard-estate-sales" / "stewards-ledger.html"
INDEX_MIRROR = WORKSPACE / "BACKUP-github-websites-only" / "morning-scroll" / "stewards-ledger.html"
INDEX_LIVE = "https://claypnw.github.io/morning-scroll/stewards-ledger.html"
PHOENIX = ZoneInfo("America/Phoenix")

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
    (e.g. the batch-log write in finish() flipped the verdict), put the
    last step at 0 with a generic reason — the program's own output
    carries the detail."""
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


_output_lines = []


def emit(line=""):
    _output_lines.append(line)
    print(line, flush=True)


def md5_file(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def atomic_write_json(path, data):
    """Write JSON to `path` atomically and crash-safely.

    Writes to a temp file in the SAME directory (so the rename stays on
    one filesystem), flushes + fsyncs it, sets it to the existing file's
    permissions, then os.replace()s it over `path`. A kill / power loss /
    disk error before the replace leaves the old file intact; after the
    replace the new file is complete. Never truncates `path` in place.
    """
    path = Path(path)
    try:
        mode = stat.S_IMODE(path.stat().st_mode)
    except FileNotFoundError:
        mode = 0o644
    text = json.dumps(data, indent=2) + "\n"
    fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(tmp_path, mode)
        os.replace(tmp_path, path)
        # fsync the directory so the rename itself survives a crash
        try:
            dir_fd = os.open(str(path.parent), os.O_DIRECTORY)
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
        except OSError:
            pass
    finally:
        try:
            if tmp_path.exists():
                tmp_path.unlink()
        except OSError:
            pass


def _try_write_log(lines):
    """Append `lines` to the dated batch log. Returns (ok, error_str)."""
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        log_date = datetime.now(PHOENIX).strftime("%Y-%m-%d")
        log_path = LOG_DIR / f"{log_date}.log"
        text = "\n".join(lines) + "\n"
        # Append so multiple runs on the same day are all preserved;
        # each run's block ends with its VERDICT line.
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        return True, None
    except Exception as e:
        return False, str(e)


def finish(passed, failures):
    """Emit the verdict, write the log, and return the exit code.

    The verdict is held back until the log write has been attempted:
    the log is the evidence, so if writing it fails the outcome becomes
    FAIL with that reason (exit 1) even when every check passed.
    """
    if passed:
        verdict = "VERDICT: PASS"
        code = 0
    else:
        reason = "; ".join(failures) if failures else "unknown failure"
        verdict = f"VERDICT: FAIL — {reason}"
        code = 1
    ok, err = _try_write_log(_output_lines + [verdict])
    if ok:
        emit(verdict)
        if not passed:
            # A failed verdict opens an error record in the one shared
            # error program. The dated log and the verdict line above
            # are unchanged — they are the evidence reports quote.
            _report_to_shared_error("verdict", verdict, kind="check_failed")
        if passed:
            log_path = LOG_DIR / f"{datetime.now(PHOENIX).strftime('%Y-%m-%d')}.log"
            _write_finish_line(verdict, str(log_path))
        return code
    # Log write failed — outcome becomes FAIL regardless of the checks.
    print(f"WARNING: could not write batch log: {err}", file=sys.stderr)
    if passed:
        fail_verdict = f"VERDICT: FAIL — batch log write failed: {err}"
    else:
        reason = "; ".join(failures) if failures else "unknown failure"
        fail_verdict = f"VERDICT: FAIL — {reason}; batch log write failed: {err}"
    emit(fail_verdict)
    _report_to_shared_error("write dated log", fail_verdict, kind="foreseen")
    return 1


def download(url, dest):
    req = urllib.request.Request(url, headers={"User-Agent": "ledger_verify/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        if getattr(resp, "status", 200) != 200:
            raise RuntimeError(f"HTTP {resp.status} for {url}")
        data = resp.read()
    Path(dest).write_bytes(data)
    return dest


def _main():
    _write_start_line()
    parser = argparse.ArgumentParser(description="Ledger post-publish verification + state gating")
    parser.add_argument("--date", required=True, help="Edition date YYYY-MM-DD")
    parser.add_argument("--edition", required=True, type=int, help="Edition number")
    parser.add_argument("--apply-state", action="store_true", help="Write state file on PASS only")
    parser.add_argument("--state-file", default=None, help="State file path override (for tests)")
    args = parser.parse_args()

    date_str = args.date
    edition = args.edition
    state_path = Path(args.state_file) if args.state_file else DEFAULT_STATE

    # Rule log: the state step exists only in --apply-state runs.
    _rl_labels = {
        1: "edition_live_vs_local",
        2: "index_live_vs_local",
        3: "edition_mirror_vs_local",
        4: "index_mirror_vs_local",
    }
    if args.apply_state:
        _rl_labels[5] = "state_update"
    _rl_begin("ledger", _rl_labels)
    _rl("START", 1)

    # Validate date format early
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        _rl("FAIL", 1, f"invalid --date '{date_str}' (expected YYYY-MM-DD)")
        emit(f"ledger_verify date={date_str} edition={edition}")
        return finish(False, [f"invalid --date '{date_str}' (expected YYYY-MM-DD)"])

    now_phx = datetime.now(PHOENIX)
    emit(f"ledger_verify job={JOBDIR} date={date_str} edition={edition} run_at={now_phx.isoformat()} America/Phoenix")
    emit(f"state_file={state_path} apply_state={args.apply_state}")

    edition_local = Path(EDITION_LOCAL_TMPL.format(date=date_str))
    edition_mirror = Path(EDITION_MIRROR_TMPL.format(date=date_str))
    edition_live_url = EDITION_LIVE_TMPL.format(date=date_str)
    emit(f"edition_local={edition_local}")
    emit(f"edition_live={edition_live_url}")
    emit(f"edition_mirror={edition_mirror}")
    emit(f"index_local={INDEX_LOCAL}")
    emit(f"index_live={INDEX_LIVE}")
    emit(f"index_mirror={INDEX_MIRROR}")

    failures = []  # list of (category, reason)

    # Helper to run one live check
    def check_live(label, local_path, live_url, tmpdir, tmp_name):
        if not local_path.exists():
            emit(f"{label} live vs local: local=missing live=not-checked FAIL")
            failures.append(f"{label} local file missing: {local_path}")
            return None
        local_md5 = md5_file(local_path)
        dest = Path(tmpdir) / tmp_name
        try:
            download(live_url, dest)
        except Exception as e:
            emit(f"{label} live vs local: local_md5={local_md5} live=download-failed ({e}) FAIL")
            failures.append(f"{label} live download failed: {e}")
            return local_md5
        live_md5 = md5_file(dest)
        match = (live_md5 == local_md5)
        emit(f"{label} live vs local: local_md5={local_md5} live_md5={live_md5} {'MATCH' if match else 'FAIL'}")
        if not match:
            failures.append(f"{label} live md5 mismatch (local={local_md5} live={live_md5})")
        return local_md5

    def check_mirror(label, local_path, mirror_path, local_md5):
        if local_md5 is None:
            # local missing already recorded; mirror check cannot pass
            if not mirror_path.exists():
                emit(f"{label} mirror vs local: local=missing mirror=missing FAIL")
            else:
                emit(f"{label} mirror vs local: local=missing mirror_md5={md5_file(mirror_path)} FAIL")
            failures.append(f"mirror {label} check failed: local file missing")
            return
        if not mirror_path.exists():
            emit(f"{label} mirror vs local: local_md5={local_md5} mirror=missing FAIL")
            failures.append(f"mirror {label} missing: {mirror_path}")
            return
        mirror_md5 = md5_file(mirror_path)
        match = (mirror_md5 == local_md5)
        emit(f"{label} mirror vs local: local_md5={local_md5} mirror_md5={mirror_md5} {'MATCH' if match else 'FAIL'}")
        if not match:
            failures.append(f"mirror {label} md5 mismatch (local={local_md5} mirror={mirror_md5})")

    def _ev():
        # Evidence for a check = the check's own result line, as emitted.
        line = _output_lines[-1] if _output_lines else ""
        for prefix in ("edition ", "index "):
            if line.startswith(prefix):
                return line[len(prefix):]
        return line

    with tempfile.TemporaryDirectory(prefix="ledger_verify_") as tmpdir:
        before = len(failures)
        edition_local_md5 = check_live("edition", edition_local, edition_live_url, tmpdir, "edition_live.html")
        _rl("OK" if len(failures) == before else "FAIL", 1, _ev())
        _rl("START", 2)
        before = len(failures)
        index_local_md5 = check_live("index", INDEX_LOCAL, INDEX_LIVE, tmpdir, "index_live.html")
        _rl("OK" if len(failures) == before else "FAIL", 2, _ev())
        # Mirror checks (second check; failure fails verdict with its own reason)
        # Recompute local md5 if check_live returned None due to missing file handling
        if edition_local_md5 is None and edition_local.exists():
            edition_local_md5 = md5_file(edition_local)
        if index_local_md5 is None and INDEX_LOCAL.exists():
            index_local_md5 = md5_file(INDEX_LOCAL)
        _rl("START", 3)
        before = len(failures)
        check_mirror("edition", edition_local, edition_mirror, edition_local_md5)
        _rl("OK" if len(failures) == before else "FAIL", 3, _ev())
        _rl("START", 4)
        before = len(failures)
        check_mirror("index", INDEX_LOCAL, INDEX_MIRROR, index_local_md5)
        _rl("OK" if len(failures) == before else "FAIL", 4, _ev())

    passed = len(failures) == 0

    # State gating
    if args.apply_state:
        _rl("START", 5)
        state_failed = False
        if passed:
            try:
                data = json.loads(state_path.read_text(encoding="utf-8"))
                data["edition_number"] = edition
                data["last_edition"] = date_str
                # preserve sections and all other keys untouched (only those two changed above)
                # crash-safe: temp file in same folder, flush+fsync, os.replace
                atomic_write_json(state_path, data)
                emit(f"STATE: updated {state_path} edition_number={edition} last_edition={date_str} (atomic replace)")
            except Exception as e:
                passed = False
                state_failed = True
                failures.append(f"state update failed: {e}")
                emit(f"STATE: update failed for {state_path}: {e}")
        else:
            emit(f"STATE: not updated — verdict FAIL, state file left untouched: {state_path}")
        # On a FAIL run the gate holding (state untouched) is the step
        # working as specified; only a failed write itself is a 0.
        _rl("FAIL" if state_failed else "OK", 5, _output_lines[-1] if _output_lines else "")
    else:
        emit("STATE: not updated — --apply-state not given (verify-only)")

    return finish(passed, failures)


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
