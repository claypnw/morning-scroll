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
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BATCH_DIR = Path(__file__).resolve().parent
VENV_PY = ROOT / "venv" / "bin" / "python"
UPLOAD_DIR = ROOT / "publish-upload"
GOAL_FILES = Path.home() / "workspace" / "goals" / "morning-agenda-briefing" / "files"


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
            with urllib.request.urlopen(
                    "https://raw.githubusercontent.com/claypnw/morning-scroll/main/scroll-search-index.json",
                    timeout=60) as resp:
                raw_index = resp.read()
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
                listing_req = urllib.request.Request(
                    "https://api.github.com/repos/claypnw/morning-scroll/contents/scroll-search-index.json?ref=main",
                    headers={"User-Agent": "morning-scroll-build",
                             "Accept": "application/vnd.github+json"})
                with urllib.request.urlopen(listing_req, timeout=60) as resp:
                    repo_blob_sha = json.loads(resp.read().decode("utf-8")).get("sha")
            except Exception:
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

    # ---- clear stale dated files out of the upload dir (Q7) ----------------------
    # publish-upload must hold only this edition's dated files plus the two
    # archive files archive_update.py refreshes. Anything dated from an
    # earlier edition is removed here, by name, so the bundle check can
    # treat any leftover as a real problem.
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    stale_re = re.compile(r"^(scroll-\d{4}-\d{2}-\d{2}-page-\d+-r1-.+\.png|payson-morning-scroll-\d{4}-\d{2}-\d{2}\.pdf)$")
    for path in sorted(UPLOAD_DIR.iterdir()):
        if stale_re.match(path.name) and date_str not in path.name:
            path.unlink()
            print(f"cleanup: removed stale upload file {path.name}")

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
    names = ["index.html", "scroll-search-index.json", pdf_name] + png_names
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
