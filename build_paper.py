#!/usr/bin/env python3
"""Build The Payson Morning Scroll PDF from a JSON content file.

Usage:
    venv/bin/python build_paper.py content.json

The JSON file has this shape:
{
  "date": "2026-09-25",            # for the output filename
  "dateline": "Friday, September 25, 2026",
  "weather": {"high": 78, "low": 57, "conditions": "Sunny",
              "rain": "10%", "sunrise": "6:15 AM", "sunset": "6:18 PM",
              "tomorrow": "Sunny, 76/55"},
  "weather_blocks": [              # optional; the "By the Hours" strip
                       # printed under the weather box — exactly four
                       # blocks from batch/weather_pull.py, copied
                       # verbatim: {"label": "Morning", "hour": 9,
                       # "temp": 55, "condition": "Partly cloudy",
                       # "art": "partly", "wind_speed": 4,
                       # "wind_direction": 320, "sock": "limp"}, then
                       # Noon, Late Afternoon, Evening. "art" names one
                       # of the six fixed sky pictures in images/sky/;
                       # "sock" names one of the three fixed windsock
                       # pictures in images/windsock/ (limp / half /
                       # straight) and the mph number prints under the
                       # windsock. Absent = no strip printed.
  "headline": "Weekend Brims With Doings About Town",
  "lead": "PAYSON — ...",
  "events_today": [{"town": "Payson", "items": ["...", "..."]}, ...],
                       # happenings today only, grouped by town (Payson,
                       # Pine-Strawberry, Camp Verde, Sedona, Show Low,
                       # Prescott); may be []
                       # (a quiet-day line is printed). One "items" string per
                       # distinct happening — each prints on its own indented
                       # line under the town's name. Keep each item to one
                       # compact line; max 3 per town. Wrap the event's name
                       # in <a href="REAL-URL">...</a> linking to the event
                       # or organizer page — real URLs only, seen during
                       # research; no link if none was found.
  "events_week": [{"dat": "Saturday, Sept. 26", "items": ["...", "..."]}, ...],
                       # upcoming: tomorrow through six days out. Same <a href>
                       # link rule as events_today: link each event's name to
                       # its real page, or leave it unlinked.
  "tasks": [{"title": "...", "note": "..."}, ...],
                       # SKYRIM-BUILD QUESTS ONLY: tasks about building the
                       # Skyrim-themed guest house (Mogollon's Hearth) that are
                       # ready to start or due within the next 7 days.
                       # Never include unrelated personal errands.
  "due_soon": "Due Saturday: ...",   # optional, may be ""
  "council": "<p>...</p>"            # optional HTML fragment; "" (or absent) skips the
                       # "Word from the Payson Hold" box entirely. When
                       # present: link the agenda, minutes, and recording with
                       # <a href="REAL-URL"> (real URLs only, taken from
                       # the town's meetings page)
  "featured": {                      # optional: big once-a-year event spread
                       # (side-by-side picture+text, like the merchant box).
                       # Absent (or empty title) skips the box.
    "kicker": "Fair Week in the Hold",  # box heading
    "title": "Two Fairs, One Hold",
    "text": "what/where/when paragraphs, blank-line separated",
    "details": "admission, hours, ticket links line",
    "why": "one line: why go",
    "image": "/abs/path/to/featured.jpg", "image_alt": "...", "image_cap": "...",
  },
  # NOTE: no "calendar" field — the daybook is private and never appears
  # in the public paper (it stays in the chat briefing only).
  "hero_image": "/abs/path/to/hero.jpg",  # optional; defaults to Rim sunrise
  "hero_caption": "...",                  # optional caption under hero image
  "weather_image": "/abs/path/to/weather.jpg",  # optional; Hearth-under-today's-skies
                                            # illustration for the weather box
  "quest_image": "/abs/path/to/quest.jpg",  # optional; illustration of the current
                                            # Hearth-build quests for the quest board
                                            # (defaults to the workshop engraving)
  "quest_caption": "...",                   # optional caption under quest illustration
  "today_plate": {"image": "...", "image_alt": "...", "image_cap": "..."},
                       # optional: old-timey plate filling the column under
                       # today's happenings (local view / town art)
  "lower_plate": {"image": "...", "image_alt": "...", "image_cap": "..."},
                       # optional: wide local-view plate after the quest board
  "closing_plate": {"image": "...", "image_alt": "...", "image_cap": "..."},
                       # optional: slim skyline strip under the colophon
  "merchant": {                           # Merchant of the Hold: one local business
    "name": "...",                        #   per edition for Hearth guests
    "town": "...",
    "blurb": "...",                       # what goods/services they offer (2-3 sentences)
    "review": "...",                      # one real review quote (verbatim, never invented)
    "review_src": "Google review",        # where the quote came from
    "review_url": "https://...",          # optional: URL of the quoted review page;
                                          #   the review source prints as a link to it
    "website": "https://...",             # optional: the business's own website;
                                          #   printed as a "their scrying-mirror page" link
    "visit": "...",                       # address, hours, phone, price range, good-to-know
    "why": "...",                         # one line: why the Hearth sends guests there
  },
  "tale": {                               # Tales from the Treeline: whimsical creature tale
    "title": "...",                       #   e.g. "The Great Cinnamon Roll Caper"
    "text": "...",                        #   short humorous tale (~150-220 words);
                                          #   separate paragraphs with blank lines
    "image": "/abs/path/to/tale.jpg",     #   engraving of the creature(s) doing the activity
    "image_alt": "...",
    "image_cap": "...",                   #   one-line caption describing the illustration
  },
  "rim": {                                # Stories Around the Rim (Fridays only)
    "title": "...",                       #   e.g. "He Was HERE Ten Minutes Ago"
    "text": "...",                        #   short travelers'-tale (~120-180 words);
                                          #   separate paragraphs with blank lines.
                                          #   Mostly the Dragonborn's latest exploit
                                          #   (the Hold always just missed him), but
                                          #   may feature other notable characters
                                          #   or creatures of the Rim.
    "image": "/abs/path/to/rim.jpg",      #   engraving of the aftermath with amazed
                                          #   onlookers — never the Dragonborn himself
    "image_alt": "...",
    "image_cap": "...",                   #   one-line caption describing the illustration
  },
  "edition": 3,                           # optional override: forces the No. (day of month) instead of deriving it from the date
  "volume": 2610,                         # optional override: forces the Vol. (YYMM) instead of deriving it from the date
}

Writes the PDF to workspace/goals/morning-agenda-briefing/files/
and prints the output path. Volume and issue numbers are derived from the
edition date (the admin's scheme, 2026-10-03): volume = YYMM (e.g. October 2026
-> 2610), number = day of the month (e.g. the 3rd -> No. 03). No counter
file is used anymore; every build of the same date prints the same numbers.

IMPORTANT: all plain-text JSON fields (headline, lead, tasks, captions,
weather strings, due_soon, merchant name/town/blurb/review/visit/why,
tale title/text) are HTML-escaped automatically — write them with real
Unicode characters (’ “ ” — …), never HTML entities like &rsquo;.
"council" and the event item strings accept raw HTML markup, so <a href>
links (and <b> tags) go straight in there. Merchant links need no markup:
just fill the merchant "website" and "review_url" fields and the builder
turns them into links.

LISTEN LINES (the admin's ruling, 2026-10-26: the listen buttons stand
at the articles — one per article, never one for the whole paper): at
the TOP of each story piece the builder prints as its own piece (lead
story, featured spread, council, merchant, rim stories, tale), the
builder adds a tappable "Listen to this story" line linked to that
article's own recording on the live site — the line prints at the
TOP of the piece (first thing in the piece, right-aligned, before
its text and picture) — but only when that
article's recording stands: its record file
(batch/record-DATE-PIECE.json, written by the recording step) names
the article's own recording, a recorded size stands on the record,
and the recording stands in publish-upload/audio/ at that size. No
standing recording, no line — the paper never carries a dead link.
See listen_line() below.
Each listen link carries the new-window flag so the recording opens in a new window and the paper stays open.
"""
import html
import json
import math
import os
import random
import sys
import hashlib
import re
from string import Template
from urllib.parse import urlparse
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HOME = os.path.expanduser("~")


# --- Shared error program (standards wiring step B, 2026-10-21) -------------
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


BASE = os.path.join(HOME, "workspace", "morning-post")
IMG = os.path.join(BASE, "images")
OUTDIR = os.path.join(HOME, "workspace", "goals", "morning-agenda-briefing", "files")
COUNTER = os.path.join(BASE, "edition_counter.txt")
CONTACT_EMAIL = "mogollonshearth@gmail.com"  # the "Ask the Hearth" button in the colophon writes here — the Hearth's main address (the admin, 2026-10-03)


def esc(s):
    return html.escape(str(s), quote=False)


SITE_BASE = "https://morning-scroll-53x.pages.dev"


# --- Picture addresses, print paper and web page (2026-10-26) ---------------
# One paper, two roads: the printed PDF reads its pictures from this
# machine (file:// addresses, exactly as always), and the edition's
# web page reads the same pictures from the site's images/ folder.
# img_src() hands back the address for the road being built; on the
# web road it also remembers each picture in WEB_IMAGES (site name ->
# the file on this machine) so the page builder can copy the pictures
# out beside the page. WEB_MODE is set by build_edition_page.py only;
# the paper build itself never sets it.
WEB_MODE = False
WEB_IMAGES = {}


def _web_image_name(path):
    """The site file name for one picture file: images/scroll-img-
    <first 10 of the file's sha1><its extension>. Named by content,
    so the same picture always carries the same name."""
    with open(path, "rb") as fh:
        digest = hashlib.sha1(fh.read()).hexdigest()[:10]
    ext = os.path.splitext(path)[1].lower() or ".jpg"
    return "images/scroll-img-%s%s" % (digest, ext)


def img_src(path):
    """The address of one tinted picture, for the road being built."""
    t = tinted(path)
    if not WEB_MODE:
        return "file://" + t
    name = _web_image_name(t)
    WEB_IMAGES[name] = t
    return name


def raw_img_src(path):
    """The address of one picture used as it stands, with no tint
    (the author badge), for the road being built."""
    if not WEB_MODE:
        return "file://" + path
    name = _web_image_name(path)
    WEB_IMAGES[name] = path
    return name


def listen_line(date_str, piece, top=False):
    """The "Listen to this story" line for one article of the paper.

    Printed at the end of an article only when that article's own
    recording stands: the recording's record file
    (batch/record-DATE-PIECE.json, written by the recording step)
    names this article's own recording
    (morning-scroll-DATE-PIECE.mp3 — any other name proves nothing),
    a recorded size stands on the record, and the recording stands
    in publish-upload/audio/ at exactly that size. Anything less,
    no line — never a dead link, never another recording's line.
    The line links to the recording's address on the live site,
    SITE_BASE/audio/morning-scroll-DATE-PIECE.mp3.
    """
    here = os.path.dirname(os.path.abspath(__file__))
    rec_path = os.path.join(here, "batch",
                            "record-%s-%s.json" % (date_str, piece))
    try:
        with open(rec_path, encoding="utf-8") as fh:
            rec = json.load(fh)
    except Exception:
        return ""
    # The record must name THIS article's own recording — a record
    # naming any other file (the whole-paper recording, another
    # article's) proves nothing about this article, and the line
    # must never point at a recording that is not the article's own.
    expected = "morning-scroll-%s-%s.mp3" % (date_str, piece)
    if rec.get("mp3") != expected:
        return ""
    mp3_path = os.path.join(here, "publish-upload", "audio", expected)
    if not os.path.isfile(mp3_path):
        return ""
    # The recorded size must stand on the record and match the file:
    # with no recorded size, "stands at the recorded size" cannot be
    # proven, so no line.
    if not rec.get("mp3_bytes") or os.path.getsize(mp3_path) != rec["mp3_bytes"]:
        return ""
    # On the web page the link opens the recording in a new window
    # (the admin's ruling, 2026-10-26: the paper stays open, and
    # closing the recording's window leaves the paper standing) —
    # a web page link can carry that instruction; a link inside a
    # PDF cannot make Chrome's PDF reader honor it.
    _target = ' target="_blank" rel="noopener"' if WEB_MODE else ""
    return ('<p class="%s"><a href="%s/audio/%s"%s>Listen to this story</a></p>'
            % (("listen top" if top else "listen"), SITE_BASE, expected, _target))


# Parchment tone of the page; engravings are tinted toward it at build time so
# they read as printed on old paper rather than pasted onto it.
PARCHMENT = (242, 230, 194)
TINT_CACHE = os.path.join(BASE, ".cache", "tinted")


def tinted(src):
    """Return a parchment-tinted copy of the image at src (cached by content).

    White in the source becomes the parchment tone; blacks stay black.
    Missing or unreadable paths pass through untouched.
    """
    if not src or not os.path.isfile(src):
        return src
    try:
        st = os.stat(src)
        key = hashlib.sha1(("%s|%d|%d" % (src, st.st_size, int(st.st_mtime))).encode()).hexdigest()
        os.makedirs(TINT_CACHE, exist_ok=True)
        dst = os.path.join(TINT_CACHE, key + ".jpg")
        if not os.path.isfile(dst):
            im = Image.open(src).convert("RGB")
            bands = [b.point(lambda v, m=m / 255.0: int(v * m + 0.5))
                     for b, m in zip(im.split(), PARCHMENT)]
            Image.merge("RGB", bands).save(dst, "JPEG", quality=92)
        return dst
    except Exception:
        return src


BADGE_CACHE = os.path.join(BASE, ".cache", "badge")
MOON_CACHE = os.path.join(BASE, ".cache", "moon")
MOON_FACE = os.path.join(IMG, "moon-face.jpg")  # the Hearth's standing moon face (the admin, 2026-10-04); only the phase changes nightly
MOON_SYNODIC = 29.53058867
MOON_NAMES = ("New Moon", "Waxing Crescent", "First Quarter", "Waxing Gibbous",
              "Full Moon", "Waning Gibbous", "Last Quarter", "Waning Crescent")


def moon_phase_triptych(date_iso):
    """Mask the standing moon face into yesterday/today/tomorrow phases.

    Returns [(label, phase_name, jpg_path), ...], cached by date. The dark
    limb keeps a whisper of the engraving, like earthshine.
    """
    from datetime import date as _date, timedelta as _td
    import math
    day = _date.fromisoformat(str(date_iso))
    ref = _date(2000, 1, 6)
    try:
        face = Image.open(MOON_FACE).convert("RGB")
    except Exception:
        return []
    W, H = face.size
    cx, cy, R = W // 2, H // 2, int(W * 0.47)
    circ = Image.new("L", (W, H), 0)
    ImageDraw.Draw(circ).ellipse([cx - R, cy - R, cx + R, cy + R], fill=255)
    face = Image.composite(face, Image.new("RGB", (W, H), (255, 255, 255)), circ)
    # Dark limb: dark grey, not black — like the real moon's earthshine, with
    # the engraving's texture faintly visible (the admin, 2026-10-04).
    dk = face.point(lambda v: int(v * 0.52))
    dark = Image.merge("RGB", [dk.split()[0].point(lambda v: int(v * 0.72)),
                               dk.split()[1].point(lambda v: int(v * 0.75)),
                               dk.split()[2].point(lambda v: int(v * 0.92))])
    edge = Image.new("L", (W, H), 0)
    ImageDraw.Draw(edge).ellipse([cx - R, cy - R, cx + R, cy + R], fill=255)
    out = []
    os.makedirs(MOON_CACHE, exist_ok=True)
    for label, d in (("Yesterday", day - _td(days=1)), ("Tonight", day), ("Tomorrow", day + _td(days=1))):
        age = ((d - ref).days) % MOON_SYNODIC
        theta = 2 * math.pi * age / MOON_SYNODIC
        waxing = theta <= math.pi
        c = abs(math.cos(theta))
        mask = Image.new("L", (W, H), 0)
        dm = ImageDraw.Draw(mask)
        if waxing:
            dm.rectangle([cx, 0, W, H], fill=255)
        else:
            dm.rectangle([0, 0, cx, H], fill=255)
        rx = int(c * R)
        if theta < math.pi / 2 or (math.pi < theta < 3 * math.pi / 2):
            dm.ellipse([cx - rx, cy - R, cx + rx, cy + R], fill=0)
        else:
            dm.ellipse([cx - rx, cy - R, cx + rx, cy + R], fill=255)
        m = Image.new("L", (W, H), 0)
        mask = Image.composite(mask, m, edge)
        phase = Image.composite(face, dark, mask)
        phase = Image.composite(phase, Image.new("RGB", (W, H), (255, 255, 255)), edge)
        dst = os.path.join(MOON_CACHE, "%s-%s.jpg" % (date_iso, label.lower()))
        phase.save(dst, "JPEG", quality=90)
        out.append((label, MOON_NAMES[int((age / MOON_SYNODIC) * 8 + 0.5) % 8], dst, age))
    return out


MUGGY_AVATAR = os.path.join(HOME, "workspace", "avatars",
                            "avatar-1794103850012532792-13.webp")
# Muggy's own avatar picture — the brown Mogollon Monster holding his
# pewter mug, the same picture that stands as his mark on report pages.

MAGGIE_PORTRAIT = os.path.join(IMG, "maggie-circle.png")
# Maggie's approved round portrait — the circular master she sent for
# the Scroll bylines (claypnw/system-documentation, portraits/
# Maggie-Skyrim-Bard-Circle-2026-11-21.png, blob 68c2d27c), placed on
# this machine 2026-11-23 after Clay approved all the portraits. It is
# already a circle on clear ground, so the byline mark carries it as
# it stands, at byline size, with the paper's ink ring drawn round it.


def author_badge(author):
    """Circular badge for one story's author (Clay's order, 2026-11-16
    — the wolf badge labeled DUDE is retired). Since Clay's correction
    later that morning, this ring form serves only as Maggie's byline
    mark (see author_mark); Muggy's mark is his plain picture circle,
    and no badge of either kind stands in the paper's headrow.

    The ring is the paper's standing badge form: a parchment band with
    the author's name arced along the bottom edge of the circle. Muggy's
    badge carries his own avatar picture. Maggie's badge is a plain
    parchment circle with her name standing inside it — the placeholder
    Clay himself named; it stood as her byline mark until her approved
    portrait reached this machine (2026-11-23), and now serves only as
    the fallback in author_mark. Returns a transparent PNG (cached by
    author and, for Muggy, by the avatar's stamp).
    """
    if author == "maggie":
        src = None
        name = ""
        inner_word = "Aela"
        stamp = "aela-name-circle-v1"
    else:
        src = MUGGY_AVATAR
        name = "MUGGY"
        inner_word = None
        if not os.path.isfile(src):
            return tinted(src)
        st = os.stat(src)
        stamp = "%d|%d" % (st.st_size, int(st.st_mtime))
    try:
        key = hashlib.sha1(("author-badge|%s|%s" % (author, stamp)).encode()).hexdigest()
        os.makedirs(BADGE_CACHE, exist_ok=True)
        dst = os.path.join(BADGE_CACHE, key + ".png")
        if os.path.isfile(dst):
            return dst
        S = 900
        c = S // 2
        R_out, band = c - 8, 96
        R_pic = R_out - band
        badge = Image.new("RGBA", (S, S), (0, 0, 0, 0))
        bd = ImageDraw.Draw(badge)
        ink = (26, 26, 26, 255)
        # parchment ring band carrying the name
        bd.ellipse([c - R_out, c - R_out, c + R_out, c + R_out], fill=PARCHMENT + (255,))
        if src is not None:
            im = Image.open(tinted(src)).convert("RGB")
            w0, h0 = im.size
            m = min(w0, h0)
            im = im.crop(((w0 - m) // 2, (h0 - m) // 2,
                          (w0 + m) // 2, (h0 + m) // 2)).resize((S, S), Image.LANCZOS)
            pmask = Image.new("L", (S, S), 0)
            ImageDraw.Draw(pmask).ellipse([c - R_pic, c - R_pic, c + R_pic, c + R_pic], fill=255)
            badge.paste(im, (0, 0), pmask)
            bd = ImageDraw.Draw(badge)
        else:
            # plain parchment inside the ring, her name standing in it
            bd.ellipse([c - R_pic, c - R_pic, c + R_pic, c + R_pic],
                       fill=(240, 214, 158, 255))
            wfont = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf", 160)
            bb = bd.textbbox((0, 0), inner_word, font=wfont)
            bd.text((c - (bb[2] - bb[0]) / 2 - bb[0],
                     c - (bb[3] - bb[1]) / 2 - bb[1]), inner_word, font=wfont, fill=ink)
        bd.ellipse([c - R_out, c - R_out, c + R_out, c + R_out], outline=ink, width=9)
        bd.ellipse([c - R_pic, c - R_pic, c + R_pic, c + R_pic], outline=ink, width=5)
        if name:
            # the name arced along the bottom of the ring, letters standing on the arc
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf", 84)
            widths = []
            for ch in name:
                bb = bd.textbbox((0, 0), ch, font=font)
                widths.append(bb[2] - bb[0])
            R_text = R_pic + band // 2
            total = sum(widths) + 26 * (len(name) - 1)
            ang = -math.degrees(total / 2.0 / R_text)  # start angle, deg from bottom
            for ch, cwd in zip(name, widths):
                half = math.degrees((cwd / 2.0) / R_text)
                theta = 90 - (ang + half)  # image coords: 90 deg = straight down; run left->right
                tile = Image.new("RGBA", (170, 170), (0, 0, 0, 0))
                td = ImageDraw.Draw(tile)
                bb = td.textbbox((0, 0), ch, font=font)
                td.text(((170 - (bb[2] - bb[0])) / 2 - bb[0],
                         (170 - (bb[3] - bb[1])) / 2 - bb[1]), ch, font=font, fill=ink)
                tile = tile.rotate(-(theta - 90), resample=Image.BICUBIC, expand=False)
                x = c + R_text * math.cos(math.radians(theta))
                y = c + R_text * math.sin(math.radians(theta))
                badge.alpha_composite(tile, (int(x - 85), int(y - 85)))
                ang += math.degrees((cwd + 26) / R_text)
            # small diamonds closing the arc at both ends
            for sgn in (-1, 1):
                theta = 90 + sgn * (math.degrees(total / 2.0 / R_text) + 10)
                x = c + R_text * math.cos(math.radians(theta))
                y = c + R_text * math.sin(math.radians(theta))
                bd.polygon([(x, y - 10), (x + 10, y), (x, y + 10), (x - 10, y)], fill=ink)
        badge.save(dst, "PNG")
        return dst
    except Exception:
        return tinted(src) if src else ""


def author_mark(author):
    """The small writer's mark that stands on a story's own byline line
    (Clay's correction, 2026-11-16, with his screenshot of that morning's
    edition as the evidence): no writer picture stands at the top of the
    paper — each story carries its writer's mark small, beside the
    writer's name on that story's byline. Muggy's mark is his own avatar
    picture in a plain ink-ringed circle. Maggie's mark is her approved
    round portrait in the same plain ink-ringed circle (placed
    2026-11-23, on Clay's approval of all the portraits); her name
    circle (author_badge) stands as the fallback if the portrait file
    is ever missing. Returns a transparent PNG (cached like the badge)."""
    if author == "maggie":
        if not os.path.isfile(MAGGIE_PORTRAIT):
            return author_badge("maggie")
        try:
            st = os.stat(MAGGIE_PORTRAIT)
            stamp = "%d|%d" % (st.st_size, int(st.st_mtime))
            key = hashlib.sha1(("author-mark|maggie-portrait|%s" % stamp).encode()).hexdigest()
            os.makedirs(BADGE_CACHE, exist_ok=True)
            dst = os.path.join(BADGE_CACHE, key + ".png")
            if os.path.isfile(dst):
                return dst
            S = 360
            c = S // 2
            R = c - 6
            im = Image.open(MAGGIE_PORTRAIT).convert("RGBA")
            w0, h0 = im.size
            m = min(w0, h0)
            im = im.crop(((w0 - m) // 2, (h0 - m) // 2,
                          (w0 + m) // 2, (h0 + m) // 2)).resize((S, S), Image.LANCZOS)
            out = Image.new("RGBA", (S, S), (0, 0, 0, 0))
            out.alpha_composite(im, (0, 0))
            ImageDraw.Draw(out).ellipse([c - R, c - R, c + R, c + R],
                                        outline=(26, 26, 26, 255), width=7)
            out.save(dst, "PNG")
            return dst
        except Exception:
            return author_badge("maggie")
    src = MUGGY_AVATAR
    if not os.path.isfile(src):
        return ""
    try:
        st = os.stat(src)
        stamp = "%d|%d" % (st.st_size, int(st.st_mtime))
        key = hashlib.sha1(("author-mark|muggy|%s" % stamp).encode()).hexdigest()
        os.makedirs(BADGE_CACHE, exist_ok=True)
        dst = os.path.join(BADGE_CACHE, key + ".png")
        if os.path.isfile(dst):
            return dst
        S = 360
        c = S // 2
        R = c - 6
        im = Image.open(tinted(src)).convert("RGB")
        w0, h0 = im.size
        m = min(w0, h0)
        im = im.crop(((w0 - m) // 2, (h0 - m) // 2,
                      (w0 + m) // 2, (h0 + m) // 2)).resize((S, S), Image.LANCZOS)
        out = Image.new("RGBA", (S, S), (0, 0, 0, 0))
        pmask = Image.new("L", (S, S), 0)
        ImageDraw.Draw(pmask).ellipse([c - R, c - R, c + R, c + R], fill=255)
        out.paste(im, (0, 0), pmask)
        ImageDraw.Draw(out).ellipse([c - R, c - R, c + R, c + R],
                                    outline=(26, 26, 26, 255), width=7)
        out.save(dst, "PNG")
        return dst
    except Exception:
        return ""


def _piece_author(f):
    """Who wrote a contributed piece: its own author field when one is
    recorded, else the 'by Maggie' line the piece carries in its why."""
    a = (f.get("author") or "").strip().lower()
    if a in ("maggie", "muggy"):
        return a
    if "by Maggie" in (f.get("why") or ""):
        return "maggie"
    return ""


# Aged-parchment page backgrounds. Each page gets its own unique sheet,
# generated with PIL and composited BEHIND the content, so stains are always
# background, never over text. Seeded by date: rebuilds are stable, and no
# two pages (or editions) ever share the same marks. Stains stay sparse —
# zero to two coffee rings in the whole scroll (the admin, 2026-09-29).
PARCHMENT_BG = (232, 201, 140)
PARCH_CACHE = os.path.join(BASE, ".cache", "parchment")
PARCH_W, PARCH_H = 1275, 1650  # 8.5x11in at 150dpi
PARCH_VERSION = "v10"  # v10: folio rules drawn in the parchment — a printed rule under the running header and above the footer on pages 2+ (the admin 2026-10-03; WeasyPrint margin boxes are shrink-to-fit and can't span full width); v9: rounded corners (radius 56, the admin 2026-10-02 — the pointy corners looked weird); v8: corner pinning against triangular flaps; v7: deeper deckled waves (max_depth 55); v6: warm amber sheet, faint creases, from his reference image; v5: varied hand-torn edges (the admin 2026-10-01); v4: rougher torn edges, darker at the edges


def _paper_imperfections(base, rng, w, h):
    """Honest Skyrim-era paper character: uneven pulp tone, flecks, fibers,
    and a little foxing. All subtle — texture, not dirt."""
    # mottled, unbleached tone: large soft blotches, darker and lighter
    mottle = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    md = ImageDraw.Draw(mottle)
    for _ in range(9):
        r = rng.uniform(180, 420)
        cx, cy = rng.uniform(0, w), rng.uniform(0, h)
        tone = (186, 155, 105, 16) if rng.random() < 0.6 else (255, 250, 236, 16)
        md.ellipse([cx - r, cy - r * 0.8, cx + r, cy + r * 0.8], fill=tone)
    mottle = mottle.filter(ImageFilter.GaussianBlur(70))
    base = Image.alpha_composite(base.convert("RGBA"), mottle)
    # pulp flecks and short fibers
    fleck = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    fd = ImageDraw.Draw(fleck)
    for _ in range(240):
        x, y = rng.uniform(0, w), rng.uniform(0, h)
        s = rng.uniform(1, 2.6)
        fd.ellipse([x, y, x + s, y + s], fill=(139, 105, 62, rng.randint(35, 75)))
    for _ in range(55):
        x, y = rng.uniform(0, w), rng.uniform(0, h)
        a = rng.uniform(0, 6.28)
        ln = rng.uniform(6, 22)
        fd.line([x, y, x + ln * math.cos(a), y + ln * math.sin(a)],
                fill=(150, 118, 78, 38), width=1)
    # foxing: small soft age spots
    for _ in range(16):
        x, y = rng.uniform(0, w), rng.uniform(0, h)
        r = rng.uniform(2, 6)
        fd.ellipse([x - r, y - r, x + r, y + r], fill=(140, 95, 50, 55))
    # faint creases: the sheet was folded and flattened long ago (v6)
    for _ in range(4):
        x0, y0 = rng.uniform(0, w), rng.uniform(0, h)
        a = rng.uniform(0, 6.28)
        ln = rng.uniform(200, 520)
        fd.line([x0, y0, x0 + ln * math.cos(a), y0 + ln * math.sin(a)],
                fill=(118, 86, 50, 24), width=rng.randint(2, 4))
    fleck = fleck.filter(ImageFilter.GaussianBlur(1.2))
    return Image.alpha_composite(base, fleck).convert("RGB")


def _draw_coffee_ring(layer, rng, w, h):
    r = rng.uniform(0.9, 1.6) * (w / 8.5)
    cx = rng.uniform(r + 18, w - r - 18)
    cy = rng.uniform(r + 18, h - r - 18)
    x0, y0, x1, y1 = cx - r, cy - r * 0.96, cx + r, cy + r * 0.96
    d = ImageDraw.Draw(layer)
    d.ellipse([x0, y0, x1, y1], outline=(110, 74, 34, 92), width=max(5, int(r / 16)))
    inset = r * 0.18
    d.ellipse([x0 + inset, y0 + inset, x1 - inset, y1 - inset], fill=(120, 82, 38, 26))
    a0 = rng.uniform(0, 360)
    d.arc([x0, y0, x1, y1], start=a0, end=a0 + rng.uniform(60, 160),
          fill=(100, 66, 30, 115), width=max(5, int(r / 14)))
    return layer.filter(ImageFilter.GaussianBlur(4))


def _draw_water_spot(layer, rng, w, h):
    """A dried water mark: a soft tide-line ring, nearly clear in the
    middle — the kind of stain that simply appears on paper one day."""
    r = rng.uniform(0.7, 1.3) * (w / 8.5)
    cx = rng.uniform(r + 14, w - r - 14)
    cy = rng.uniform(r + 14, h - r - 14)
    d = ImageDraw.Draw(layer)
    d.ellipse([cx - r, cy - r * 0.94, cx + r, cy + r * 0.94],
              outline=(150, 126, 86, 48), width=max(3, int(r / 22)))
    inset = r * 0.13
    d.ellipse([cx - r + inset, cy - r * 0.94 + inset, cx + r - inset, cy + r * 0.94 - inset],
              outline=(150, 126, 86, 30), width=max(2, int(r / 30)))
    d.ellipse([cx - r, cy - r * 0.94, cx + r, cy + r * 0.94], fill=(122, 100, 62, 7))
    return layer.filter(ImageFilter.GaussianBlur(3))


def _draw_ale_ring(layer, rng, w, h):
    """A smaller, paler ring than coffee's — a mug of something golden
    set down a moment too long."""
    r = rng.uniform(0.5, 0.9) * (w / 8.5)
    cx = rng.uniform(r + 14, w - r - 14)
    cy = rng.uniform(r + 14, h - r - 14)
    d = ImageDraw.Draw(layer)
    d.ellipse([cx - r, cy - r * 0.96, cx + r, cy + r * 0.96],
              outline=(172, 118, 38, 58), width=max(4, int(r / 18)))
    a0 = rng.uniform(0, 360)
    d.arc([cx - r, cy - r * 0.96, cx + r, cy + r * 0.96], start=a0,
          end=a0 + rng.uniform(80, 190), fill=(150, 100, 34, 66),
          width=max(4, int(r / 16)))
    return layer.filter(ImageFilter.GaussianBlur(3))


def _draw_splatter(layer, rng, w, h):
    """A small splash: one main blot and its satellite drops."""
    cx = rng.uniform(w * 0.12, w * 0.88)
    cy = rng.uniform(h * 0.10, h * 0.90)
    d = ImageDraw.Draw(layer)
    r1 = rng.uniform(6, 15)
    d.ellipse([cx - r1, cy - r1 * 0.8, cx + r1, cy + r1 * 0.8], fill=(110, 76, 36, 52))
    for _ in range(rng.randint(8, 14)):
        a = rng.uniform(0, 6.283)
        dist = rng.uniform(12, 95)
        x, y = cx + dist * math.cos(a), cy + dist * math.sin(a) * 0.85
        r = rng.uniform(1, 4.6)
        d.ellipse([x - r, y - r, x + r, y + r], fill=(110, 76, 36, rng.randint(38, 68)))
    return layer.filter(ImageFilter.GaussianBlur(1.2))


def _draw_damp_blotch(layer, rng, w, h):
    """A broad, faint damp patch — paper that once got wet and dried
    none the worse, only slightly darker for it."""
    cx = rng.uniform(w * 0.2, w * 0.8)
    cy = rng.uniform(h * 0.15, h * 0.85)
    rx = rng.uniform(130, 300)
    ry = rx * rng.uniform(0.55, 0.95)
    ImageDraw.Draw(layer).ellipse([cx - rx, cy - ry, cx + rx, cy + ry],
                                  fill=(158, 126, 78, 22))
    return layer.filter(ImageFilter.GaussianBlur(42))


STAIN_DRAWERS = {"coffee": _draw_coffee_ring, "water": _draw_water_spot,
                 "ale": _draw_ale_ring, "splash": _draw_splatter,
                 "damp": _draw_damp_blotch}
def _frayed_alpha(w, h, rng, max_depth=38):
    """Alpha mask for torn old-scroll edges: opaque interior, rough torn
    boundary. v5 (the admin, 2026-10-01): the v4 uniform noise made endless
    matching sharp triangles — the tear now mixes scales and shapes:
    broad scallops, medium notches, occasional deep rounded bites, and
    fine fibre jitter, so no two stretches of edge repeat and it reads
    hand-torn rather than machine-cut."""
    per = 2 * (w + h)
    step = 3  # px between boundary samples — dense enough for fibre detail
    n = int(per // step)
    depth = [0.0] * n
    # multi-octave periodic noise: one phase loop around the whole sheet,
    # so corners stay continuous and every scale of tear can appear
    for points, weight in ((9, 0.55), (23, 0.30), (61, 0.22), (173, 0.13)):
        vals = [rng.uniform(0, 1) for _ in range(points)]
        for i in range(n):
            u = i * points / n
            i0 = int(u) % points
            frac = u - int(u)
            frac = frac * frac * (3 - 2 * frac)  # smoothstep: rounded scallops
            depth[i] += weight * (vals[i0] * (1 - frac) + vals[(i0 + 1) % points] * frac)
    lo, hi = min(depth), max(depth)
    depth = [(d - lo) / (hi - lo) for d in depth]
    # occasional deep bites: smooth rounded scoops, varied widths
    for _ in range(rng.randint(4, 7)):
        ctr = rng.randrange(n)
        hw = max(3.0, rng.uniform(24, 130) / step)
        amp = rng.uniform(0.35, 0.95)
        k = int(hw * 2)
        for j in range(-k, k + 1):
            depth[(ctr + j) % n] += amp * math.exp(-(j * j) / (2 * (hw / 2) ** 2))
    hi = max(depth)
    depth = [d / hi for d in depth]
    # fibre jitter: the torn edge is never clean even at print scale
    depth = [min(1.0, d + rng.uniform(0, 0.03)) for d in depth]
    pts = []
    for i in range(n):
        s = per * i / n  # arclength position around the rectangle
        d = depth[i] * max_depth
        if s < w:                # top edge, left -> right
            x, y, ix, iy = s, 0, 0, 1
        elif s < w + h:          # right edge, top -> bottom
            x, y, ix, iy = w, s - w, -1, 0
        elif s < 2 * w + h:      # bottom edge, right -> left
            x, y, ix, iy = w - (s - w - h), h, 0, -1
        else:                    # left edge, bottom -> top
            x, y, ix, iy = 0, h - (s - 2 * w - h), 1, 0
        pts.append((x + ix * d, y + iy * d))
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).polygon(pts, fill=255)
    return mask.filter(ImageFilter.GaussianBlur(0.7))  # slight AA; tear stays rough


def _deckled_alpha(w, h, rng, max_depth=55):
    """Alpha mask for scorched/deckled old-parchment edges (v9, the admin,
    2026-10-02, from his reference image): deep smooth waves like a
    burnt deckle on ROUNDED corners (v9 — he found the pointy corners
    weird) — gentle fibre jitter, no jagged teeth, so the edge reads
    hand-aged rather than hand-torn or machine-straight."""
    r = 56.0  # corner radius
    # walk the rounded-rectangle perimeter: 4 straight runs + 4 arcs
    segs = [
        ("top", float(w - 2 * r), None),
        ("arc", math.pi * r / 2.0, ((w - r, r), -math.pi / 2)),   # top-right
        ("right", float(h - 2 * r), None),
        ("arc", math.pi * r / 2.0, ((w - r, h - r), 0.0)),        # bottom-right
        ("bottom", float(w - 2 * r), None),
        ("arc", math.pi * r / 2.0, ((r, h - r), math.pi / 2)),    # bottom-left
        ("left", float(h - 2 * r), None),
        ("arc", math.pi * r / 2.0, ((r, r), math.pi)),            # top-left
    ]
    per = sum(s[1] for s in segs)
    step = 3
    n = int(per // step)
    depth = [0.0] * n
    for points, weight in ((5, 0.50), (11, 0.30), (23, 0.20), (47, 0.12)):
        vals = [rng.uniform(0, 1) for _ in range(points)]
        for i in range(n):
            u = i * points / n
            i0 = int(u) % points
            frac = u - int(u)
            frac = frac * frac * (3 - 2 * frac)  # smoothstep: rounded waves
            depth[i] += weight * (vals[i0] * (1 - frac) + vals[(i0 + 1) % points] * frac)
    lo, hi = min(depth), max(depth)
    depth = [(d - lo) / (hi - lo) for d in depth]
    # gentle fibre jitter only — the burnt edge never runs clean
    depth = [min(1.0, d + rng.uniform(0, 0.03)) for d in depth]
    pts = []
    for i in range(n):
        s = per * i / n
        d = depth[i] * max_depth
        acc = 0.0
        for kind, ln, payload in segs:
            if s <= acc + ln:
                t = s - acc
                if kind == "top":
                    x, y = r + t, d
                elif kind == "right":
                    x, y = w - d, r + t
                elif kind == "bottom":
                    x, y = w - r - t, h - d
                elif kind == "left":
                    x, y = d, h - r - t
                else:  # arc: wave pushes radially inward; never invert
                    (cx, cy), a0 = payload
                    th = a0 + t / r
                    rr = max(r - d, 10.0)
                    x, y = cx + rr * math.cos(th), cy + rr * math.sin(th)
                pts.append((x, y))
                break
            acc += ln
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).polygon(pts, fill=255)
    return mask.filter(ImageFilter.GaussianBlur(0.9))  # soft burnt line

def parchment_sheet(date_str, page_index):
    """Build (or fetch from cache) one page's aged-parchment background.
    Stains are NOT baked in here — they go on top of the finished page via
    stain_overlay(), because a coffee ring lands on the whole paper, never
    behind a picture (the admin, 2026-10-02)."""
    key = "%s-%s-p%d.png" % (PARCH_VERSION, date_str, page_index)
    os.makedirs(PARCH_CACHE, exist_ok=True)
    dst = os.path.join(PARCH_CACHE, key)
    if os.path.isfile(dst):
        return dst
    w, h = PARCH_W, PARCH_H
    rng = random.Random("parchment|%s|%d" % (date_str, page_index))
    base = Image.new("RGB", (w, h), PARCHMENT_BG)
    # gentle vignette: darker toward the edges, like aged paper
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).ellipse([-w * 0.25, -h * 0.25, w * 1.25, h * 1.25], fill=42)
    mask = mask.filter(ImageFilter.GaussianBlur(140))
    base = Image.composite(Image.new("RGB", (w, h), (198, 160, 106)), base, mask)
    # paper grain
    base = Image.blend(base, Image.effect_noise((w, h), 4).convert("RGB"), 0.035)
    # Skyrim-era imperfections: uneven pulp, flecks, fibers, foxing
    base = _paper_imperfections(base, rng, w, h)
    base = base.convert("RGBA")
    # scorched/deckled old-parchment edges (the admin, 2026-10-02; was torn
    # edges v4/v5): wavy silhouette with alpha, scorch-darkened toward
    # the edges, lighter in the middle
    fray = _deckled_alpha(w, h, rng)
    # soft edge darkening: strongest at the burnt boundary, decaying inward
    edge_grad = fray.filter(ImageFilter.MinFilter(5)).filter(
        ImageFilter.GaussianBlur(46))
    halo_alpha = Image.eval(edge_grad, lambda a: int((255 - a) * 0.55))
    halo = Image.new("RGBA", (w, h), (100, 68, 32, 255))
    halo.putalpha(halo_alpha)
    base = Image.alpha_composite(base, halo)
    # darker scorched rim right at the edge
    rim = fray.filter(ImageFilter.MinFilter(33)).filter(ImageFilter.GaussianBlur(7))
    rim_band = Image.composite(Image.new("L", (w, h), 0),
                               Image.new("L", (w, h), 132), rim)
    dark_layer = Image.new("RGBA", (w, h), (96, 64, 30, 255))
    dark_layer.putalpha(rim_band)
    base = Image.alpha_composite(base, dark_layer)
    if page_index > 0:
        # folio rules (the admin, 2026-10-03): a printed rule under the running
        # header and above the footer, separating the folio from the page.
        # Drawn here in the parchment (150dpi) — WeasyPrint's margin boxes
        # are shrink-to-fit and can't span a full-width rule.
        dr = ImageDraw.Draw(base)
        rule = (58, 44, 28, 255)  # the folio ink
        x0, x1 = int(0.5 * 150), int(8.0 * 150)
        dr.rectangle([x0, int(0.595 * 150), x1, int(0.595 * 150) + 2], fill=rule)
        dr.rectangle([x0, int(10.425 * 150), x1, int(10.425 * 150) + 2], fill=rule)
    base.putalpha(fray)
    base.save(dst, "PNG")
    return dst


STAIN_VERSION = "s2"  # bump to regenerate the stain overlays


def stain_overlay(date_str, page_index, stains):
    """Build (or fetch from cache) a transparent PNG carrying ONLY the
    day's stains. It is composited OVER the finished page in
    apply_parchment_backgrounds — a coffee ring lands on top of the whole
    paper, crossing pictures and print, never behind them (the admin, 2026-10-02).
    At most one coffee ring per edition; the rest of the cast (water spots,
    ale rings, splashes, damp blotches) is seeded by date in
    apply_parchment_backgrounds so every edition differs and rebuilds
    are stable."""
    key = "%s-%s-p%d.png" % (STAIN_VERSION, date_str, page_index)
    os.makedirs(PARCH_CACHE, exist_ok=True)
    dst = os.path.join(PARCH_CACHE, key)
    if os.path.isfile(dst):
        return dst
    w, h = PARCH_W, PARCH_H
    acc = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    for kind, sseed in stains:
        layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        layer = STAIN_DRAWERS[kind](layer, random.Random(sseed), w, h)
        acc = Image.alpha_composite(acc, layer)
    acc.save(dst, "PNG")
    return dst


def apply_parchment_backgrounds(pdf_path, date_str):
    """Composite a unique aged-parchment sheet behind every page."""
    import fitz
    doc = fitz.open(pdf_path)
    n = doc.page_count
    # The day's blemishes, seeded by date so every edition differs and
    # rebuilds are stable: at most ONE ring-shaped stain in the whole scroll
    # (the admin, 2026-10-06 — a coffee ring plus an ale ring reads as two cup-rings).
    # When the coffee ring lands, the other marks must not be ring-shaped.
    s_rng = random.Random("stains|%s" % date_str)
    plan = {}
    has_coffee = False
    if s_rng.random() < 0.85:
        has_coffee = True
        plan.setdefault(s_rng.randrange(n), []).append(
            ("coffee", "stain|%s|coffee" % date_str))
    others = ["water", "splash", "damp"] if has_coffee else ["water", "ale", "splash", "damp"]
    for kind in s_rng.sample(others,
                             k=s_rng.randint(1, 3)):
        plan.setdefault(s_rng.randrange(n), []).append(
            (kind, "stain|%s|%s" % (date_str, kind)))
    for i, page in enumerate(doc):
        bg = parchment_sheet(date_str, i)
        page.insert_image(page.rect, filename=bg, overlay=False)
        # The day's blemishes go ON TOP of the finished page — a coffee
        # ring lands on the whole paper, crossing pictures and print,
        # never behind them (the admin, 2026-10-02).
        st = plan.get(i)
        if st:
            ov = stain_overlay(date_str, i, tuple(st))
            page.insert_image(page.rect, filename=ov, overlay=True)
    tmp = pdf_path + ".aged"
    doc.save(tmp, garbage=4, deflate=True)
    doc.close()
    os.replace(tmp, pdf_path)


def apply_listen_new_window(pdf_path):
    """Set the new-window flag on recording links only.

    For each link whose URI is a recording address (starts with
    "https://morning-scroll-53x.pages.dev/audio/morning-scroll-"
    and ends with ".mp3"), set A/NewWindow to true on its action, so
    the recording opens in a new window and the paper stays open.
    Every other link is left exactly as it is. Returns the number of
    links flagged. A paper with no recording links is a quiet no-op
    (returns 0, file untouched). A recording link whose flag cannot
    be set or read back is a loud error, never a silent pass.
    """
    import fitz
    prefix = "https://morning-scroll-53x.pages.dev/audio/morning-scroll-"
    doc = fitz.open(pdf_path)
    flagged = 0
    tmp = pdf_path + ".newwin"
    try:
        for page in doc:
            for link in page.get_links():
                uri = link.get("uri") or ""
                if not (uri.startswith(prefix) and uri.endswith(".mp3")):
                    continue
                xref = link.get("xref")
                try:
                    if not xref:
                        raise RuntimeError("link has no xref")
                    doc.xref_set_key(xref, "A/NewWindow", "true")
                    _typ, _val = doc.xref_get_key(xref, "A/NewWindow")
                    if _val != "true":
                        raise RuntimeError(
                            "NewWindow read back as %r %r, not true" % (_typ, _val))
                except Exception as exc:
                    print("ERROR: could not set NewWindow on recording link %s: %s"
                          % (uri, exc), file=sys.stderr)
                    raise
                flagged += 1
        if flagged == 0:
            doc.close()
            return 0
        doc.save(tmp, garbage=4, deflate=True)
    except Exception:
        doc.close()
        raise
    doc.close()
    os.replace(tmp, pdf_path)
    return flagged


TEMPLATE = Template("""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Payson's Morning Scroll — $dateline</title>
<style>
  @page { size: Letter; margin: 0.62in 0.5in 0.60in 0.5in;
    @top-left { content: "Payson's Morning Scroll"; font-variant: small-caps; font-weight: bold; letter-spacing: 1px; font-size: 8.5pt; color: #3a2c1c; vertical-align: bottom; padding-bottom: 5px; }
    @top-right { content: "$folio_date"; font-variant: small-caps; letter-spacing: 0.5px; font-size: 8pt; color: #3a2c1c; vertical-align: bottom; padding-bottom: 5px; }
    @bottom-center { content: "\\00B7  Page " counter(page) "  \\00B7"; font-variant: small-caps; letter-spacing: 1px; font-size: 8.5pt; color: #3a2c1c; vertical-align: top; padding-top: 5px; }
  }
  @page :first { margin: 0.45in 0.5in 0.44in 0.5in;
    @top-left { content: none; } @top-right { content: none; } @bottom-center { content: none; }
  }
  * { box-sizing: border-box; }
  body {
    font-family: Georgia, 'Times New Roman', serif;
    color: #1a1a1a; background: transparent;
    margin: 0; padding: 0; font-size: 10pt; line-height: 1.4;
    -webkit-print-color-adjust: exact; print-color-adjust: exact;
  }
  .masthead { text-align: center; border-bottom: 4px double #1a1a1a; padding-bottom: 3px; }
  .masthead .nameplate {
    font-weight: 900; font-size: 36pt; letter-spacing: 1.5px;
    margin: 0; line-height: 1.0; font-variant: small-caps; white-space: nowrap;
  }
  .masthead .dedication {
    font-variant: small-caps; letter-spacing: 2px; font-size: 10pt;
    margin: 2px 0 0 0;
  }
  .masthead .motto { font-style: italic; font-size: 9.5pt; margin: 1px 0 0 0; }
  .masthead .publisher { font-variant: small-caps; letter-spacing: 2px; font-size: 9.5pt; font-weight: bold; margin: 2px 0 0 0; }
  .dateline {
    font-size: 8.5pt; font-variant: small-caps; letter-spacing: 0.5px;
    border-bottom: 1px solid #1a1a1a; padding: 3px 2px; margin-bottom: 6px;
    text-align: center; word-spacing: 6px;
  }
  .dateline .sec { white-space: nowrap; }
  .weather {
    border: 1.5px solid #1a1a1a; padding: 6px 8px; margin-bottom: 6px;
    font-size: 10.5pt; width: 100%; box-sizing: border-box; line-height: 1.25;
  }
  .wxrow1 { display: table; width: 100%; }
  .weather .wimg { display: table-cell; width: 1.8in; vertical-align: middle; padding-right: 10px; }
  .weather .wimg img { width: 1.6in; display: block; margin: 0 0 3px 0; border: 1px solid #1a1a1a; }
  .weather .wcap { font-size: 10pt; font-style: italic; color: #444; line-height: 1.3; padding-top: 1px; }
  .weather .wbody { display: table-cell; vertical-align: middle; text-align: center; }
  .weather .wbody > div { margin: 0; }
  .weather .wtitle { font-weight: 900; font-variant: small-caps; letter-spacing: 1px; font-size: 12pt; }
  .weather .wnow { font-size: 22pt; font-weight: 900; line-height: 1.1; }
  .weather .wcond { font-size: 12pt; font-weight: bold; }
  .weather .wcall { font-size: 11pt; font-style: italic; }
  .weather .wdet { font-size: 10.5pt; color: #333; line-height: 1.3; }
  .weather .wheard { font-size: 10.5pt; font-style: italic; color: #333; margin-top: 2px; }
  .weather .wquote { display: table-cell; width: 1.55in; vertical-align: middle;
    font-size: 10.5pt; font-style: italic; color: #333; line-height: 1.3;
    border-left: 1px solid #999; padding-left: 8px; }
  .weather .wqhead { font-size: 10.5pt; font-weight: 900; font-style: normal;
    font-variant: small-caps; letter-spacing: 1px; color: #1a1a1a;
    margin-bottom: 2px; }
  .wxdiv { border-top: 1px solid #999; margin: 1px 0 0 0; }
  /* By the Hours strip (the admin, 2026-10-23): four hour blocks under
     the weather box. Words on the left of each block (temperature big,
     condition under it), the fixed sky picture on the right, and under
     the sky picture the fixed windsock picture with its mph number
     printed under the sock. */
  .wxrow2 { display: table; width: 100%; box-sizing: border-box; }
  .wxbox { display: table-cell; width: 25%; box-sizing: border-box;
    padding: 0 3px; border-left: 1px solid #999; text-align: center; }
  .wxbox:first-child { border-left: none; }
  .wxlabel { font-weight: 900; font-variant: small-caps; letter-spacing: 0.5px;
    font-size: 11pt; margin-bottom: 2px; line-height: 1.15; }
  .wxmain { display: table; width: 100%; }
  .wxwords { display: table-cell; vertical-align: middle; text-align: center; }
  .wxwords .wxtemp { display: block; font-size: 16pt; font-weight: 900; line-height: 1.1; }
  .wxwords .wxcond { display: block; margin-left: 0; }
  .wxcond { font-size: 11pt; font-weight: bold; margin-top: 2px; }
  .wxpics { display: table-cell; width: 1.04in; vertical-align: top; padding-left: 4px; white-space: nowrap; }
  .wxpics img { width: 0.5in; display: inline-block; border: 1px solid #1a1a1a; }
  .wxpics .wxsock { margin-left: 3px; }
  .wxmph { display: block; font-size: 10pt; color: #333; white-space: nowrap; margin: 1px 0 0 0; }
  .box .ffig { float: left; width: 2.9in; margin: 2px 10px 4px 0; }
  .box .ffig img { width: 100%; display: block; border: 1px solid #1a1a1a; }
  .box .ffig figcaption { font-size: 7.5pt; font-style: italic; color: #444; padding-top: 2px; }
  .box .qfig { float: right; width: 2.7in; margin: 2px 0 4px 10px; }
  .box .qfig img { width: 100%; display: block; border: 1px solid #1a1a1a; }
  .box .qfig figcaption { font-size: 7.5pt; font-style: italic; color: #444; padding-top: 2px; }
  .clear { clear: both; }
  .kicker { font-variant: small-caps; letter-spacing: 1.5px; font-size: 9pt; font-weight: bold; margin: 0 0 2px 0; }
  h1.headline { font-size: 25pt; line-height: 1.08; margin: 0 0 2px 0; font-weight: 900; }
  .byline { font-size: 8.5pt; font-style: italic; color: #444; margin: 0 0 8px 0; border-bottom: 1px solid #ccc; padding-bottom: 6px; }
  .headrow { display: flex; gap: 14px; align-items: flex-start; margin: 0 0 8px 0; border-bottom: 1px solid #ccc; padding-bottom: 6px; }
  .headtxt { flex: 1; }
  .writermark { width: 0.34in; height: 0.34in; vertical-align: middle; margin-right: 5px; }
  figure { margin: 0 0 8px 0; }
  figure img { width: 100%; display: block; border: 1px solid #1a1a1a; }
  figcaption { font-size: 8pt; font-style: italic; color: #444; padding-top: 3px; }
  .frontpic { float: right; width: 2.0in; margin: 2px 0 8px 10px; }
  .frontpic img { width: 100%; height: auto; border: 1px solid #1a1a1a; }
  .frontpic figcaption { font-size: 7.5pt; font-style: italic; color: #444; padding-top: 2px; }
  .story::after { content: ""; display: block; clear: both; }
  p.lead { font-size: 11.5pt; text-align: justify; hyphens: auto; margin: 0 0 10px 0; }
  p.lead::first-letter { font-size: 15pt; font-weight: 900; }
  ul.eventlist { list-style: none; margin: 0; padding: 0; border-top: 2.5px solid #1a1a1a; break-inside: auto; }
  ul.eventlist li { position: relative; font-size: 10pt; line-height: 1.4;
    padding: 4px 0 4px 20px; border-bottom: 1px solid #999; }
  ul.eventlist li::before { content: "\\2022"; position: absolute; left: 4px; top: 6px; font-size: 12pt; }
  /* Days Ahead flow (the admin, 2026-10-01): a day's item may break BETWEEN its
     indented event lines so the list fills the columns instead of leaving
     a half-empty page — but the date header stays glued to its first line,
     and no single event line ever splits. */
  ul.eventlist li .dat { display: block; break-after: avoid; }
  .subev { display: block; margin: 1px 0 1px 1.6em; break-inside: avoid; }
  h3.evhead { font-variant: small-caps; letter-spacing: 1px; font-size: 11pt; font-weight: 900;
    margin: 6px 0 0 0; padding-bottom: 2px; border-bottom: 1px solid #1a1a1a;
    break-inside: avoid; break-after: avoid; }
  ul.eventlist li.quiet { font-style: italic; color: #444; }
  ul.eventlist li.quiet::before { content: ""; }
  .holdbanner { height: .32in; vertical-align: -.06in; margin-right: .07in; }
  /* Gap-filler engraving (the admin, 2026-10-01): an optional floated figure at the
     top of The Days Ahead, closely related to what's on that page — fresh
     every edition, fun and light. Text wraps around it. */
  .wfig { float: right; width: 2.2in; margin: 2px 0 6px 10px; break-inside: avoid; }
  /* Blank-space plates (the admin, 2026-10-01): old-timey pictures, local art, and
     views of the town used to fill page/column gaps — never story filler. */
  .plateitem { break-inside: avoid; padding-left: 0 !important; }
  .plateitem::before { content: "" !important; }
  .plateitem figure { margin: 4px 0 2px 0; }
  .plateitem img { width: 100%; height: 1.5in; object-fit: cover; object-position: 50% 82%; display: block; border: 1px solid #1a1a1a; }
  .wideplate { margin-top: 8px; break-inside: avoid; }
  .wideplate img { width: 100%; height: 1.6in; object-fit: cover; display: block; border: 1px solid #1a1a1a; }
  .wideplate figcaption { font-size: 7.5pt; font-style: italic; color: #444; padding-top: 2px; }
  .closingplate { margin: 4px auto 0 auto; width: 5.4in; break-inside: avoid; }
  .closingplate img { width: 100%; height: 1.7in; object-fit: cover; display: block; border: 1px solid #1a1a1a; }
  .closingplate figcaption { font-size: 7.5pt; font-style: italic; color: #444; padding-top: 2px; text-align: center; }
  /* Closing filler advertisement (2026-10-30): a fake display ad in the
     newspaper manner, filling the last page's open bottom (gap 13). Double-rule
     border like the masthead. The box height is set inline by filler_ad_html()
     from the night's measured last-page remainder (see the height rule by
     FILLER_ADS below); the form variants shrink the type as the box shrinks. */
  .fillerad { margin-top: 10px; border: 4px double #1a1a1a; padding: 10px 16px 8px 16px;
    text-align: center; break-inside: avoid; box-sizing: border-box; overflow: hidden; }
  .fillerad .fadtag { font-variant: small-caps; letter-spacing: 2px; font-size: 8pt; color: #444; margin: 0 0 4px 0; }
  .fillerad .fadhead { font-size: 21pt; font-weight: 900; line-height: 1.08; margin: 0 0 2px 0; }
  .fillerad .fadsub { font-size: 12pt; font-weight: 900; font-variant: small-caps; letter-spacing: 1px; margin: 0 0 4px 0; }
  .fillerad img.fadart { width: auto; max-width: 92%; display: block; margin: 2px auto 6px auto; }
  .fillerad .fadcopy { font-size: 10.5pt; line-height: 1.42; margin: 0 0 5px 0; }
  .fillerad .fadfoot { border-top: 1px solid #1a1a1a; padding-top: 4px; font-size: 8.5pt;
    font-variant: small-caps; letter-spacing: 1px; margin: 5px 0 0 0; }
  .fillerad.short { padding: 8px 14px 6px 14px; }
  .fillerad.short .fadhead { font-size: 17pt; }
  .fillerad.compact { margin-top: 6px; padding: 5px 10px 4px 10px; }
  .fillerad.compact .fadtag { font-size: 7pt; margin: 0 0 2px 0; }
  .fillerad.compact .fadhead { font-size: 13pt; margin: 0 0 1px 0; }
  .fillerad.compact .fadsub { font-size: 9.5pt; margin: 0; }
  .fillerad.compact img.fadart { margin: 1px auto 2px auto; }
  .fillerad.micro { margin-top: 6px; padding: 4px 10px 3px 10px; }
  .fillerad.micro .fadhead { font-size: 12pt; margin: 0 0 1px 0; }
  .fillerad.micro .fadsub { font-size: 9pt; margin: 0; }
  .story { column-count: 2; column-gap: 22px; margin-bottom: 10px; }
  .story .lead { margin-bottom: 8px; }
  .lower { margin-top: 8px; border-top: 1px solid #999; padding-top: 8px; }
  .lower .box { margin-bottom: 8px; }
  .sidecols { width: 100%; border-collapse: collapse; }
  .sidecols td { vertical-align: top; padding: 0; }
  .sidecols td.sidepic { width: 3.1in; }
  .sidecols td.sidepic.padright { padding-right: 10px; }
  .sidecols td.sidepic.padleft { padding-left: 10px; }
  .sidecols td.sidepic img { width: 100%; height: auto; display: block; border: 1px solid #1a1a1a; }
  .sidecols td.sidepic figcaption { font-size: 7.5pt; font-style: italic; color: #444; padding-top: 2px; }
  .box { border: 1.5px solid #1a1a1a; break-inside: avoid; }
  .box h2 {
    margin: 0; padding: 5px 10px; font-size: 11.5pt; font-variant: small-caps;
    letter-spacing: 1px; border-bottom: 1.5px solid #1a1a1a; background: #e7d3a3;
  }
  .box .body { padding: 6px 10px; font-size: 10.5pt; line-height: 1.45; }
  .box .body p { margin: 0 0 6px 0; }
  .box ul { margin: 0; padding-left: 15px; }
  .box li { margin-bottom: 5px; }
  .box figure img { border: none; border-bottom: 1px solid #1a1a1a; }
  .due { font-style: italic; color: #444; }
  .box.merchant { margin-top: 8px; break-inside: avoid; }
  .box.featured { margin-top: 8px; break-inside: avoid; }
  .weather .wmoons { display: table-cell; width: 1.55in; vertical-align: middle;
    text-align: center; border-left: 1px solid #999; padding-left: 7px; }
  .weather .wmhead { font-size: 10.5pt; font-weight: 900; font-variant: small-caps;
    letter-spacing: 0.5px; margin-bottom: 1px; }
  .weather .wmcap { font-size: 10pt; color: #444; margin-top: 1px; line-height: 1.3; }
  .weather .wmoonrow { white-space: nowrap; }
  .weather .wmoon { display: inline-block; vertical-align: middle; width: 30px; margin: 0 1px; }
  .weather .wmoon.tonight { width: 38px; }
  .weather .wmoon img { width: 100%; display: block; }
  .weather .wmoon figcaption { font-size: 10pt; line-height: 1.2; color: #444; }
  .weather .wmtrend { font-size: 10pt; font-style: italic; color: #555; margin-top: 1px; line-height: 1.3; }
  .box.merchant .body { font-size: 9.5pt; line-height: 1.4; }
  .box.taletale, .box.rimstories { margin-top: 8px; break-inside: avoid; }
  .box.taletale .body, .box.rimstories .body { font-size: 9.5pt; line-height: 1.4; }
  .taletitle { font-size: 12pt; font-weight: 900; font-variant: small-caps; letter-spacing: 1px; margin: 0 0 4px 0; }
  .mname { font-size: 13pt; font-weight: 900; margin: 0 0 4px 0; }
  .mtown { font-size: 10pt; font-weight: 400; font-style: italic; color: #444; }
  .mcols { width: 100%; border-collapse: collapse; margin-top: 2px; }
  .mcols td.mcol { vertical-align: top; padding: 0; }
  .mcols td.mphoto { width: 2.3in; padding-right: 10px; }
  .mcols td.mphoto img { width: 100%; height: auto; display: block; border: 1px solid #1a1a1a; }
  .mcols td.mphoto figcaption { font-size: 7.5pt; font-style: italic; color: #444; padding-top: 2px; }
  .mcols td.mtext1 { width: 2.85in; padding-right: 10px; }
  .mcols td.mtext2 { padding-left: 10px; border-left: 1px solid #999; }
  .mquote { font-style: italic; border-left: 2.5px solid #1a1a1a; padding-left: 8px; margin: 6px 0 0 0; }
  .msrc { font-style: normal; font-size: 8.5pt; color: #444; }
  .mvisit { font-size: 9pt; color: #333; margin: 0 0 6px 0; }
  .mwhy { margin: 0; }
  .colophon {
    margin-top: 4px; border-top: 4px double #1a1a1a; padding-top: 4px;
    font-size: 8.5pt; font-style: italic; text-align: center; color: #444;
  }
  .contact-btn {
    display: inline-block; margin-top: 6px; padding: 4px 18px;
    border: 1.5px solid #7a5c2e; border-radius: 6px; background: #e7d3a3;
    color: #3a2a12; text-decoration: none; font-style: normal; font-size: 9.5pt;
  }
  .contact-addr {
    display: inline-block; margin-top: 3px; font-style: normal; font-size: 7.5pt;
    color: #5a4a2e;
  }
  .listen { margin: 6px 0 0 0; text-align: right; }
  .listen.top { margin: 0 0 6px 0; break-inside: avoid; }
  .listen a {
    display: inline-block; padding: 3px 12px;
    border: 1.5px solid #7a5c2e; border-radius: 6px; background: #e7d3a3;
    color: #3a2a12; text-decoration: none; font-style: normal; font-size: 9pt;
  }
  a { color: #1a1a1a; text-decoration: underline; }
</style>
</head>
<body>

<div class="masthead">
  <p class="nameplate">Payson's Morning Scroll</p>
  <p class="dedication">Made Exclusively for the Mogollon&rsquo;s Hearth Guests</p>
  <p class="motto">&ldquo;All the news worth knowing before the mead hall opens.&rdquo;</p>
  <p class="publisher">The Greybeards of High Hrothgar &mdash; Publisher &amp; Proprietor</p>
</div>
<div class="dateline"><span class="sec">Payson, Arizona</span> &middot; <span class="sec">$dateline</span> &middot; <span class="sec">Morning Edition &mdash; Vol. $volume, No. $edition</span> &middot; <span class="sec">Price: One Septim</span></div>

<div class="weather">
 <div class="wxrow1">
  <div class="wimg">
    <img src="$weather_img" alt="The Hearth's cats in today's weather">
    <div class="wcap">$weather_caption</div>
  </div>
  <div class="wbody">
    <div class="wtitle">Skies O&rsquo;er the Hold &nbsp; <span class="wnow">$high&deg; / $low&deg;</span> &nbsp; <span class="wcond">$conditions</span></div>
    <div class="wcall">$weather_call</div>
    <div class="wdet">Wind $weather_wind &nbsp;&middot;&nbsp; Feels like $weather_feels&deg; &nbsp;&middot;&nbsp; UV $weather_uv &nbsp;&middot;&nbsp; Rain $rain_label</div>
    <div class="wdet">Sunrise $sunrise &nbsp;&middot;&nbsp; Sunset $sunset &nbsp;&middot;&nbsp; Tomorrow &mdash; $tomorrow_label</div>
  </div>
  $weather_overheard
  $mooncol
 </div>
 <div class="wxdiv"></div>
 $weather_strip
</div>
<div class="headrow">
  <div class="headtxt">
    <p class="kicker">Around the Holds &middot; The Week Ahead</p>
    <h1 class="headline">$headline</h1>
  </div>
</div>
<div class="story">
  <p class="byline">$lead_mark By $lead_byline_name &middot; Payson, Ariz.</p>
  $listen_lead
  <figure class="frontpic">
    <img src="$hero_img" alt="Front page engraving">
    <figcaption>$hero_caption</figcaption>
  </figure>
  <p class="lead">$lead</p>
  <h3 class="evhead">Happening in the Holds Today</h3>
  $listen_today
  <ul class="eventlist">
    $events_today
  </ul>
  <h3 class="evhead">The Days Ahead</h3>
  $listen_ahead
  $days_ahead_figure
  <ul class="eventlist">
    $events_week
  </ul>
</div>

$featured_box
<div class="lower">
  $council_box
  $lower_plate
</div>

<div class="box merchant">
  <h2>Merchant of the Hold</h2>
  <div class="body">
    $listen_merchant
    <p class="mname">$merchant_name <span class="mtown">&middot; $merchant_town</span></p>
    <table class="mcols"><tr>
      <td class="mcol mphoto">$merchant_photos</td>
      <td class="mcol mtext1">$merchant_blurb
        <p class="mquote">&ldquo;$merchant_review&rdquo; <span class="msrc">&mdash; $merchant_review_src</span></p>
      </td>
      <td class="mcol mtext2">
        <p class="mvisit">$merchant_visit</p>
        <p class="mwhy"><b>Why the Hearth sends you:</b> $merchant_why</p>
      </td>
    </tr></table>
  </div>
</div>

$rimstories_html
<div class="box taletale">
  <h2>Tales from the Treeline</h2>
  <div class="body">
    $listen_tale
    <p class="taletitle">$tale_title</p>
    <table class="mcols"><tr>
      <td class="mcol mphoto"><figure style="margin:0"><img src="$tale_image" alt="$tale_image_alt"><figcaption>$tale_image_cap</figcaption></figure></td>
      <td class="mcol">$tale_text</td>
    </tr></table>
  </div>
</div>

<div class="colophon">
  Printed with pride in Payson, in the shadow of the Rim &middot; Set in hot metal by Muggy, Bard of the Morning Scroll &middot; May your $weekday be free of $beast, the admin.
  <br><a class="contact-btn" href="$contact_href">Ask the Hearth &#9993;</a>
  <br><span class="contact-addr">$contact_addr</span>
</div>
$closing_plate
$filler_ad

</body>
</html>
""")


def _stacked_figs(m, specs):
    """Build stacked <figure> HTML for the merchant photo column.

    specs: list of (key, default_img, default_alt, default_cap). Keys whose
    image is missing and have no default are skipped, so image2/image3 are
    optional (e.g. an interior shot added later).
    """
    figs = []
    for key, dimg, dalt, dcap in specs:
        p = m.get(key) or dimg
        if not p:
            continue
        figs.append(
            '<figure style="margin:0 0 8px 0"><img src="%s" alt="%s">'
            "<figcaption>%s</figcaption></figure>"
            % (img_src(p), esc(m.get(key + "_alt", dalt)),
               esc(m.get(key + "_cap", dcap))))
    return "".join(figs)


# --- Closing filler advertisements (2026-10-30) ------------------------------
# Fake in-world display ads that fill the last page's open bottom (gap 13),
# the way newspapers fill a short page. Art is drawn in-house (ads/ folder,
# made by make_ad_art.py); no outside pictures. STANDING RULE — the Closing
# Filler Rotation: the edition's date picks the ad, day-of-year modulo the
# size of the set, so the nightly build varies the filler on its own and the
# same date always carries the same ad.
FILLER_AD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ads")
FILLER_ADS = [
    {
        "art": "sweetroll.png", "alt": "A sweetroll, drawn by our staff artist",
        "head": "STOLEN SWEETROLL?", "sub": "We can help.",
        "copy": [
            "Let me guess \u2014 somebody stole your sweetroll. Again. It is the "
            "oldest crime in the Holds, and the guards are no closer to solving it.",
            "The Hungry Horker bakes two hundred fresh sweetrolls every morning. "
            "Replacement rolls are half price to any victim who swears a statement "
            "before a guard. No questions asked. Some questions asked.",
        ],
        "foot": "The Hungry Horker Bakery \u00b7 Market Row, Payson Hold \u00b7 Open at first light",
    },
    {
        "art": "anvil.png", "alt": "An anvil and hammer, drawn by our staff artist",
        "head": "DRAGON ATE YOUR SWORD?", "sub": "It happens more than you\u2019d think.",
        "copy": [
            "Rimrock Forge re-forges, re-edges, and re-fits any blade a dragon, "
            "bandit, or butter knife has ruined. Sharpening while you wait. "
            "Mammoth-tusk handles fitted Thursdays.",
            "Mention this notice and the anvil rings twice \u2014 once for the "
            "steel, once for luck.",
        ],
        "foot": "Rimrock Forge & Smithy \u00b7 Below the Rim, Payson Hold \u00b7 Ask for Bryn",
    },
    {
        "art": "potion.png", "alt": "A potion flask, drawn by our staff artist",
        "head": "CURE DISEASE. RESIST FROST.", "sub": "Impress Nords.",
        "copy": [
            "Elberta\u2019s Elixirs has a potion for every peril the Rim can pour: "
            "cure disease, resist frost, breathe water, and a courage tonic strong "
            "enough to make a skeever apologize.",
            "Side effects include confidence, glowing slightly, and telling the "
            "truth at feasts. Two septims back on every empty bottle.",
        ],
        "foot": "Elberta\u2019s Elixirs \u00b7 Next to the apothecary, Payson Hold \u00b7 Taste before you travel",
    },
    {
        "art": "hearth.png", "alt": "The Hearth's fire, drawn by our staff artist",
        "head": "TIRED OF SLEEPING IN A TENT?", "sub": "The Hearth is warm.",
        "copy": [
            "Mogollon\u2019s Hearth keeps a fire through the coldest Rim night, stew "
            "in the pot, and beds that have never once been slept in by a draugr. "
            "Cats welcome. Dragons checked at the door.",
            "Show this notice and your first bowl of stew is on the house. The "
            "second bowl is on you. Fair is fair.",
        ],
        "foot": "Mogollon\u2019s Hearth \u00b7 Payson Hold \u00b7 A light in the window means come in",
    },
]


def _last_page_free_pt(page_html):
    """Free space on the last page of a rendered paper, in points: the
    distance from the bottom of the last content on the page to the
    bottom of the text area (@page margins: top 0.62in, bottom 0.60in).
    Measured on a first pass printed without the filler ad. None when
    the measurement cannot be made — the caller then falls back to
    the standing full-size ad."""
    try:
        from weasyprint import HTML
        import fitz
        data = HTML(string=page_html, base_url=BASE).write_pdf()
        doc = fitz.open(stream=data, filetype="pdf")
        page = doc[doc.page_count - 1]
        height, width = page.rect.height, page.rect.width
        text_bottom = height - 43.2
        bottom = 0.0
        for blk in page.get_text("blocks"):
            if blk[1] >= 43.6 and blk[3] <= text_bottom + 1:
                bottom = max(bottom, blk[3])
        for dr in page.get_drawings():
            r = dr["rect"]
            if (r.y0 >= 43.6 and r.y1 <= text_bottom + 1
                    and r.width < 0.95 * width):
                bottom = max(bottom, r.y1)
        for im in page.get_image_info():
            bb = im["bbox"]
            if bb[1] >= 43.6 and bb[3] <= text_bottom + 1:
                bottom = max(bottom, bb[3])
        doc.close()
        if bottom <= 0:
            return None
        return text_bottom - bottom
    except Exception:
        return None


# --- The filler height rule (production, 2026-10-30) -------------------------
# The ad is built to the night's own last page, never to a fixed size:
# render_page first prints the edition with no ad and measures the last
# page's free space F (points). The box height H = F - 13.5 (the 7.5pt
# top margin plus a 6pt safety), capped at 360pt (5.0in). The form is
# chosen by H, and in each form the drawn art is the one flexible
# element — its height is H minus that form's fixed remainder (the
# CHROME constants, calibrated on the built editions of 2026-10-27..30
# so the whole form stands inside its box):
#   H >= 300        full:    tag, headline, sub, art, both copy
#                            paragraphs, foot line.
#   150 <= H < 300  short:   smaller headline, first copy paragraph
#                            only, foot line kept; art capped at
#                            110pt so it stays a spot drawing.
#   60 <= H < 150   compact: tag, headline, art, and the sub as the
#                            one line — no copy, no foot.
#   36 <= H < 60    micro:   headline and the sub line only.
#   H < 36          no ad: the space is already small; a box that
#                            cannot hold a headline is not forced.
# If a form's art would come out under 24pt (short) or 12pt
# (compact), the ad drops to the next smaller form instead — an art
# height is never allowed to go negative or squeeze the type.
# Because H is measured from the night's own page and the box never
# splits (break-inside: avoid), the ad can never push onto a new page.
# On the web road (WEB_MODE) and whenever the measurement cannot be
# made, the ad stands at the tested full size: H = 360, art 1.85in.
FILLER_CHROME = {"full": 227.0, "short": 125.0, "compact": 53.0}
FILLER_MAX_H = 360.0
FILLER_RESERVE = 13.5


def filler_ad_html(d, free_pt=None):
    """The closing filler ad for this edition's date (rotation rule
    above), sized by the height rule above. free_pt is the last page's
    measured free space from the first pass; None stands the ad at
    the full tested size."""
    try:
        yday = _datetime.strptime(d.get("date", ""), "%Y-%m-%d").timetuple().tm_yday
    except Exception:
        yday = 0
    ad = FILLER_ADS[yday % len(FILLER_ADS)]
    if free_pt is None:
        box_h, form, art_h = FILLER_MAX_H, "full", 133.2
    else:
        box_h = min(free_pt - FILLER_RESERVE, FILLER_MAX_H)
        if box_h < 36.0:
            return ""
        if box_h >= 300.0:
            form = "full"
        elif box_h >= 150.0:
            form = "short"
        elif box_h >= 60.0:
            form = "compact"
        else:
            form = "micro"
        art_h = (box_h - FILLER_CHROME[form]) if form in FILLER_CHROME else 0.0
        if form == "short":
            art_h = min(art_h, 110.0)
            if art_h < 24.0:
                form = "compact"
                art_h = box_h - FILLER_CHROME["compact"]
        if form == "compact" and art_h < 12.0:
            form = "micro"
            art_h = 0.0
        art_h = max(art_h, 0.0)
    src = img_src(os.path.join(FILLER_AD_DIR, ad["art"]))
    tag = '<p class="fadtag">&mdash; Advertisement &mdash;</p>'
    head = '<p class="fadhead">%s</p>' % esc(ad["head"])
    sub = '<p class="fadsub">%s</p>' % esc(ad["sub"])
    art = ('<img class="fadart" src="%s" alt="%s" style="height:%.1fpt">'
           % (src, esc(ad["alt"]), art_h))
    foot = '<p class="fadfoot">%s</p>' % esc(ad["foot"])
    if form == "full":
        inner = tag + head + sub + art + "".join(
            '<p class="fadcopy">%s</p>' % esc(c) for c in ad["copy"]) + foot
        cls = "fillerad"
    elif form == "short":
        inner = tag + head + sub + art + (
            '<p class="fadcopy">%s</p>' % esc(ad["copy"][0])) + foot
        cls = "fillerad short"
    elif form == "compact":
        inner = tag + head + art + sub
        cls = "fillerad compact"
    else:  # micro
        inner = head + sub
        cls = "fillerad micro"
    return ('<div class="%s" style="height:%.1fpt">%s</div>'
            % (cls, box_h, inner))


# --- Login-walled links: the guest-tablet mark (2026-10-31) ------------------
# Clay's rule: no logins on his guest Fire tablet — not his, not a guest's.
# A link that leans on a login shows as plain words on that one tablet and
# stands live everywhere else. The tablet is singled out by a mark saved in
# its browser at setup (see ~/workspace/guest-tablet/tablet-setup.html); the
# paper's part is only to MARK the walled links. Every link this build
# writes whose address sits on a walled host gets the attribute
# data-login-link, in this one pass over the finished page, and the web
# road's checker (guest-tablet-check.js, loaded by build_edition_page.py)
# does the rest in the browser. The print road ignores the attribute.
# THE WALLED LIST — the one named place; add a host here and only here:
LOGIN_LINK_WALLED_HOSTS = [
    "facebook.com",  # the proven wall (Clay hit it on the tablet, 2026-10-31)
]

_LOGIN_LINK_RE = re.compile(r'<a\b([^>]*?)href="([^"]*)"([^>]*)>',
                            re.IGNORECASE)


def _mark_login_links(page):
    """Add data-login-link to every link on a walled host, in place."""
    def repl(m):
        pre, url, post = m.group(1), m.group(2), m.group(3)
        if "data-login-link" in pre + post:
            return m.group(0)
        host = urlparse(html.unescape(url)).hostname or ""
        if any(host == h or host.endswith("." + h)
               for h in LOGIN_LINK_WALLED_HOSTS):
            return '<a%shref="%s"%s data-login-link>' % (pre, url, post)
        return m.group(0)
    return _LOGIN_LINK_RE.sub(repl, page)


def render_page(d):
    """Build the paper's HTML page from the edition data `d` —
    the one source both roads print from: the PDF build (main(),
    below) and the edition's web page (build_edition_page.py,
    with WEB_MODE set). Fills in the derived fields on `d` the
    way the paper build always has (the Skyrim dateline, the
    colophon beast, the folio date)."""
    # Skyrim calendar (the admin, 2026-09-29): the old Tamrielic reckoning. Months
    # map 1:1 onto the lowlanders' months (Morning Star = January, Sun's Dawn
    # = February, First Seed = March, Rain's Hand = April, Second Seed = May,
    # Mid Year = June, Sun's Height = July, Last Seed = August, Hearthfire =
    # September, Frostfall = October, Sun's Dusk = November, Evening Star =
    # December); days map Morndas = Monday through Sundas = Sunday. Month
    # lengths match, so day numbers carry straight across. Derived from the
    # edition date so the JSON never carries it (a missing value once printed
    # "May your be free of dragons") and rebuilds are stable.
    SKYRIM_MONTHS = ("Morning Star", "Sun's Dawn", "First Seed", "Rain's Hand",
                     "Second Seed", "Mid Year", "Sun's Height", "Last Seed",
                     "Hearthfire", "Frostfall", "Sun's Dusk", "Evening Star")
    SKYRIM_DAYS = ("Morndas", "Tirdas", "Middas", "Turdas", "Fredas",
                   "Loredas", "Sundas")
    def _ordinal(n):
        if 10 <= n % 100 <= 20:
            suf = "th"
        else:
            suf = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
        return "%d%s" % (n, suf)
    _sky = None
    if d.get("date"):
        from datetime import date as _date
        try:
            _sky = _date.fromisoformat(str(d["date"]))
        except ValueError:
            _sky = None
    if _sky is not None:
        _sky_day = SKYRIM_DAYS[_sky.weekday()]
        # The closing blessing keeps the Skyrim day-name:
        # "May your Tirdas be free of wolves, the admin."
        if not d.get("weekday"):
            d["weekday"] = _sky_day
        # The masthead dateline flies the Skyrim reckoning first, with the
        # lowlanders' date alongside so the facts stay plain:
        # "Tirdas, the 29th of Hearthfire (Tuesday, September 29, 2026)".
        if d.get("dateline"):
            d["dateline"] = "%s, the %s of %s (%s)" % (
                _sky_day, _ordinal(_sky.day),
                SKYRIM_MONTHS[_sky.month - 1], d["dateline"])
        # Running-head date for the page headers on pages 2+ (the admin asked for
        # headers and footers, 2026-10-01): the short Skyrim reckoning with
        # the lowlanders' date alongside, one line: "1st of Frostfall (Oct 1, 2026)".
        d["folio_date"] = "%s of %s (%s %d, %d)" % (
            _ordinal(_sky.day), SKYRIM_MONTHS[_sky.month - 1],
            _sky.strftime("%b"), _sky.day, _sky.year)
    elif not d.get("weekday"):
        d["weekday"] = ""

    # Colophon beast: rotate the blessing's menace daily (the admin, 2026-09-29) —
    # "May your [day] be free of dragons" becomes wolves, bears, trolls,
    # spiders... A true rotation off the calendar date: no repeats, and
    # rebuilds are stable.
    COLOPHON_BEASTS = ("dragons", "wolves", "bears", "trolls", "spiders",
                       "skeevers", "giants", "sabre cats")
    if not d.get("beast") and d.get("date"):
        from datetime import date as _date
        try:
            _ord = _date.fromisoformat(str(d["date"])).toordinal()
        except ValueError:
            _ord = 0
        d["beast"] = COLOPHON_BEASTS[_ord % len(COLOPHON_BEASTS)]

    ed_year = int(str(d["date"])[:4])          # volume = YYMM of the edition date (the admin 2026-10-03)
    ed_month = int(str(d["date"])[5:7])
    ed_day = int(str(d["date"])[8:10])
    volume = ed_year % 100 * 100 + ed_month   # e.g. October 2026 -> 2610
    edition = ed_day                           # No. = day of the month, zero-padded at print
    if "volume" in d:
        volume = int(d["volume"])  # explicit override
    if "edition" in d:
        edition = int(d["edition"])  # explicit override

    w = d["weather"]
    HOLD_ALIAS = {"pine": "rim-country", "strawberry": "rim-country",
                  "pine-strawberry": "rim-country",
                  "pine & strawberry": "rim-country",
                  "pine and strawberry": "rim-country"}
    def hold_banner(town):
        # Engraved hold banner flown beside the town name in the events
        # section, drawn from the town's real flag or city logo.
        # images/hold-<slug>.jpg; Pine and Strawberry are a single Hold
        # (Pine-Strawberry) and fly the shared Rim Country banner.
        # A town with no banner file simply gets no banner.
        slug = town.lower().replace(" ", "-")
        slug = HOLD_ALIAS.get(slug, slug)
        p = os.path.join(IMG, "hold-%s.jpg" % slug)
        if os.path.exists(p):
            return '<img class="holdbanner" src="%s">' % img_src(p)
        return ""
    def town_list(groups, quiet_note):
        # Happenings This Day: [{"town": "Payson", "items": ["...", ...]}, ...]
        # one subsection per town; each item prints on its own indented line.
        # Falls back to ev_list rendering for entries without a "town" key.
        if not groups:
            return '<li class="quiet">%s</li>' % quiet_note
        out = []
        for g in groups:
            if "town" not in g:
                subs = "".join('<span class="subev">&mdash; %s</span>' % s for s in g["items"])
                out.append('<li><b class="dat">%s</b>%s</li>' % (esc(g.get("dat", "")), subs))
                continue
            subs = "".join('<span class="subev">&mdash; %s</span>' % s for s in g["items"])
            out.append('<li class="towngroup"><b class="dat">%s%s</b>%s</li>' % (hold_banner(g["town"]), esc(g["town"]), subs))
        return "\n  ".join(out)

    def ev_list(items, quiet_note):
        if not items:
            return '<li class="quiet">%s</li>' % quiet_note
        out = []
        for e in items:
            if "items" in e:  # one indented line per happening
                subs = "".join('<span class="subev">&mdash; %s</span>' % s for s in e["items"])
                out.append('<li><b class="dat">%s</b>%s</li>' % (esc(e["dat"]), subs))
            else:  # legacy single text block
                out.append('<li><b class="dat">%s</b> &mdash; %s</li>' % (esc(e["dat"]), e["text"]))
        return "\n  ".join(out)
    # New schema: events_today / events_week. Fall back to legacy "events".
    if "events_today" in d or "events_week" in d:
        events_today = town_list(d.get("events_today", []),
            "The hold is quiet this day &mdash; a fine one for the trails.")
        events_week = ev_list(d.get("events_week", []),
            "Nothing further on the town crier's board.")
    else:
        events_today = ev_list([], "The hold is quiet this day &mdash; a fine one for the trails.")
        events_week = ev_list(d.get("events", []), "Nothing further on the town crier's board.")
    tasks = "\n          ".join(
        "&#9744; <b>%s</b> &mdash; %s" % (esc(t["title"]), esc(t["note"]))
        for t in d.get("tasks", [])
    )
    tasks = tasks.replace("\n          ", "</li>\n          <li>")
    tasks = "<li>" + tasks + "</li>" if tasks else "<li>&#9744; Nothing pending. A rare and beautiful thing.</li>"
    due_soon = '<p class="due">%s</p>' % esc(d["due_soon"]) if d.get("due_soon") else ""
    m = d.get("merchant", {})
    t = d.get("tale", {})
    tale_paras = [p.strip() for p in str(t.get("text", "")).split("\n\n") if p.strip()]
    tale_html = "".join("<p>%s</p>" % esc(p) for p in tale_paras)
    r = d.get("rim")
    if r:
        rim_paras = [p.strip() for p in str(r.get("text", "")).split("\n\n") if p.strip()]
        rim_text = "".join("<p>%s</p>" % esc(p) for p in rim_paras)
        rimstories_html = (
            '<div class="box rimstories">\n'
            '  <h2>Stories Around the Rim</h2>\n'
            '  <div class="body">\n'
            '    %s\n'
            '    <p class="taletitle">%s</p>\n'
            '    <table class="mcols"><tr>\n'
            '      <td class="mcol mphoto"><figure style="margin:0"><img src="%s" alt="%s"><figcaption>%s</figcaption></figure></td>\n'
            '      <td class="mcol">%s</td>\n'
            '    </tr></table>\n'
            '  </div>\n'
            '</div>\n'
        ) % (
            listen_line(d["date"], "rim", top=True),
            esc(r.get("title", "Word from Afar")),
            img_src(r.get("image", os.path.join(IMG, "rim.jpg"))),
            esc(r.get("image_alt", "Amazed onlookers at the edge of the Rim")),
            esc(r.get("image_cap", "Word travels fast around the Rim.")),
            rim_text,
        )
    else:
        rimstories_html = ""

    # Merchant links: optional website + review_url become real <a href> links.
    mvisit = esc(m.get("visit", ""))
    if m.get("website"):
        mvisit += ' &middot; <a href="%s">their scrying-mirror page (other travelers call it a ‘website’)</a>' % html.escape(str(m["website"]), quote=True)
    msrc = esc(m.get("review_src", ""))
    if m.get("review_url"):
        msrc = '<a href="%s">%s</a>' % (html.escape(str(m["review_url"]), quote=True), msrc)

    council_html = str(d.get("council", "")).strip()
    if council_html:
        council_box = (
            '<div class="box">\n'
            '  <h2>Word from the Payson Hold</h2>\n'
            '  <div class="body">\n'
            '    %s\n'
            '    <table class="sidecols"><tr>\n'
            '      <td class="sidepic padright"><figure style="margin:0">\n'
            '        <img src="%s" alt="Town hall, engraving">\n'
            '      </figure></td>\n'
            '      <td class="sidetext">\n'
            '        %s\n'
            '      </td>\n'
            '    </tr></table>\n'
            '  </div>\n'
            '</div>\n'
        ) % (listen_line(d["date"], "council", top=True),
               img_src(os.path.join(IMG, "townhall.jpg")), council_html)
    else:
        council_box = ""

    # Featured spread (the admin, 2026-09-29): big once-a-year events get a bigger
    # box with what/where/when, admission, and a "why go" line. Absent (or
    # empty title) skips the box entirely.
    f = d.get("featured")
    if f and str(f.get("title", "")).strip():
        f_paras = [p.strip() for p in str(f.get("text", "")).split("\n\n") if p.strip()]
        f_text = "".join("<p>%s</p>" % esc(p) for p in f_paras)
        # The writer's mark (Clay's correction, 2026-11-16): no emblem
        # at the head of the box — the writer's small mark stands on
        # the box's own byline line, the "Why go" line that carries the
        # writer's name ("brought to the Scroll by Maggie").
        f_mark = ""
        _fauthor = _piece_author(f)
        if _fauthor in ("maggie", "muggy"):
            _mp = author_mark(_fauthor)
            if _mp:
                f_mark = ('<img class="writermark" src="%s" alt="%s"> '
                          % (raw_img_src(_mp),
                             "Aela" if _fauthor == "maggie" else "Muggy"))
        featured_box = (
            '<div class="box featured">\n'
            '  <h2>%s</h2>\n'
            '  <div class="body">\n'
            '    %s\n'
            '    <p class="mname">%s</p>\n'
            '    <figure class="ffig"><img src="%s" alt="%s"><figcaption>%s</figcaption></figure>\n'
            '    %s\n'
            '    <p class="mvisit">%s</p>\n'
            '    <p class="mwhy">%s<b>Why go:</b> %s</p>\n'
            '    <div class="clear"></div>\n'
            '  </div>\n'
            '</div>\n'
        ) % (
            esc(f.get("kicker", "A Special Spread")),
            listen_line(d["date"], "featured", top=True),
            esc(f.get("title", "")),
            img_src(f.get("image", os.path.join(IMG, "rim.jpg"))),
            esc(f.get("image_alt", "A grand doings in the Hold")),
            esc(f.get("image_cap", "Not to be missed.")),
            f_text,
            esc(f.get("details", "")),
            f_mark,
            esc(f.get("why", "")),
        )
    else:
        featured_box = ""

    # Blank-space plates (the admin, 2026-10-01): optional old-timey pictures that
    # fill gaps a page would otherwise leave blank — a column plate under
    # today's happenings, a wide local view after the quest board, and a
    # closing skyline strip under the colophon. Pictures, not story filler.
    def _plate(field, cls):
        p = d.get(field) or {}
        if not p.get("image"):
            return ""
        return ('<figure class="%s"><img src="%s" alt="%s">'
                '<figcaption>%s</figcaption></figure>') % (
            cls, img_src(p["image"]),
            esc(p.get("image_alt", "An engraving")),
            esc(p.get("image_cap", "")))
    today_plate = _plate("today_plate", "platefig")
    if today_plate:
        events_today += '\n  <li class="plateitem">' + today_plate + "</li>"
    lower_plate = _plate("lower_plate", "wideplate")
    closing_plate = _plate("closing_plate", "closingplate")

    # "Send word to the admin" button (the admin, 2026-10-03): mailto his address with
    # the edition's date in the subject, so he knows which Scroll the guest
    # is writing about.
    from urllib.parse import quote as _quote
    _contact_subject = "The Payson Morning Scroll"
    if _sky is not None:
        # ASCII hyphen in the mailto subject (not the em dash): some
        # Android PDF viewers / mail apps choke on percent-encoded
        # non-ASCII in mailto: subjects (the admin, 2026-10-12 — button did nothing).
        _contact_subject += " - %s %d, %d" % (_sky.strftime("%B"), _sky.day, _sky.year)

    # The Moon's Reckoning (the admin, 2026-10-04): the fourth section of the
    # weather box — yesterday / tonight / tomorrow moons from the true phase.
    # The phase is named once (on Tonight; on a neighbor only if it differs)
    # and the strip names the trend — waxing or waning — instead of repeating.
    _trip = moon_phase_triptych(d["date"])
    _tonight = [t for t in _trip if t[0] == "Tonight"]
    _tonight_name = _tonight[0][1] if _tonight else ""
    _tonight_age = _tonight[0][3] if _tonight else 0
    _trend = ("waxing toward the full moon" if _tonight_age < MOON_SYNODIC / 2
              else "waning toward the new moon")
    _moonfigs = []
    for _mlabel, _mname, _mpath, _mage in _trip:
        _cls = "tonight" if _mlabel == "Tonight" else ""
        _moonfigs.append(
            '<figure class="wmoon %s"><img src="%s" alt="The moon, %s" /></figure>'
            % (_cls, img_src(_mpath), esc(_mname)))
    if _sky is not None:
        _reckon = "%s of %s = %s %d" % (_ordinal(_sky.day), SKYRIM_MONTHS[_sky.month - 1],
                                       _sky.strftime("%B"), _sky.day)
    else:
        _reckon = ""
    _mooncap = " &middot; ".join(
        esc(_ml) + ((" (%s)" % esc(_mn))
                    if (_ml == "Tonight" or _mn != _tonight_name) else "")
        for _ml, _mn, _mp, _ma in _trip)
    mooncol = (
        '<div class="wmoons">'
        '<div class="wmhead">The Moon&rsquo;s Reckoning</div>'
        '<div class="wmoonrow">' + "".join(_moonfigs) + '</div>'
        '<div class="wmcap">' + _mooncap + '</div>'
        '<div class="wmtrend">%s</div>'
        '</div>'
    ) % esc(_trend) if _moonfigs else ""

    # "By the Hours" strip (the admin, 2026-10-23): four hour blocks from
    # batch/weather_pull.py, copied verbatim into the JSON as
    # "weather_blocks". Each block: its label on top; temperature and the
    # condition word on the left; the fixed sky picture on the right;
    # and under the sky picture the fixed windsock picture for the
    # hour's wind, with the wind number (mph) printed under the sock.
    # A strip that is present but wrong is a loud BUILD FAIL — never a
    # silently dropped or half-printed strip. Absent = no strip (the
    # shape every edition before 2026-10-24 was built with).
    weather_strip = ""
    _blocks = d.get("weather_blocks")
    if _blocks is not None:
        _WX_LABELS = ["Morning", "Noon", "Late Afternoon", "Evening"]
        _WX_ART = {"sunny", "partly", "cloudy", "drizzle", "lightrain", "hardrain"}
        _WX_SOCK = {"limp", "half", "straight"}
        _problems = []
        if not isinstance(_blocks, list) or len(_blocks) != 4:
            _problems.append("weather_blocks must hold exactly four blocks")
            _blocks = _blocks if isinstance(_blocks, list) else []
        for _i, _b in enumerate(_blocks):
            _want = _WX_LABELS[_i] if _i < 4 else "?"
            if not isinstance(_b, dict):
                _problems.append("weather block %d is not an object" % (_i + 1))
                continue
            if _b.get("label") != _want:
                _problems.append("weather block %d label %r, want %r"
                                 % (_i + 1, _b.get("label"), _want))
            if _b.get("art") not in _WX_ART:
                _problems.append("weather block %s art %r is not one of the six sky pictures"
                                 % (_want, _b.get("art")))
            if _b.get("sock") not in _WX_SOCK:
                _problems.append("weather block %s sock %r is not one of the three windsock pictures"
                                 % (_want, _b.get("sock")))
            if not isinstance(_b.get("temp"), (int, float)) or isinstance(_b.get("temp"), bool):
                _problems.append("weather block %s temp %r is not a number"
                                 % (_want, _b.get("temp")))
            if not isinstance(_b.get("wind_speed"), (int, float)) or isinstance(_b.get("wind_speed"), bool):
                _problems.append("weather block %s wind_speed %r is not a number"
                                 % (_want, _b.get("wind_speed")))
            if not _b.get("condition"):
                _problems.append("weather block %s has no condition word" % _want)
            for _pic in (os.path.join(IMG, "sky", "sky-%s.jpg" % _b.get("art")),
                         os.path.join(IMG, "windsock", "%s.jpg" % _b.get("sock"))):
                if not os.path.isfile(_pic):
                    _problems.append("weather block %s picture missing: %s"
                                     % (_want, _pic))
        if _problems:
            _verdict = "BUILD FAIL — By the Hours strip: " + "; ".join(_problems)
            print(_verdict)
            _report_to_shared_error("build check", _verdict, kind="check_failed")
            raise SystemExit(1)
        _cells = []
        for _b in _blocks:
            _sky_pic = os.path.join(IMG, "sky", "sky-%s.jpg" % _b["art"])
            _sock_pic = os.path.join(IMG, "windsock", "%s.jpg" % _b["sock"])
            _cells.append(
                '<div class="wxbox"><div class="wxlabel">%s</div>'
                '<div class="wxmain"><div class="wxwords">'
                '<div class="wxtemp">%s&deg;</div>'
                '<div class="wxcond">%s</div></div>'
                '<div class="wxpics">'
                '<img src="%s" alt="The sky at %s">'
                '<img class="wxsock" src="%s" alt="The windsock at %s">'
                '<div class="wxmph">%s mph</div>'
                '</div></div></div>'
                % (esc(_b["label"]), esc(_b["temp"]), esc(_b["condition"]),
                   img_src(_sky_pic), esc(_b["label"].lower()),
                   img_src(_sock_pic), esc(_b["label"].lower()),
                   esc(int(round(_b["wind_speed"])))))
        weather_strip = '<div class="wxrow2">' + "".join(_cells) + "</div>"

    # Weather-box fields (2026-10-26): the quarter-size weather area
    # prints the plain-words call and the facts line from the weather
    # dict's call / wind / feels / uv / rain fields, all written by
    # batch/weather_pull.py. A field missing or blank is a loud BUILD
    # FAIL — the same rule the strip follows above — never a weather
    # area printed with holes and a PASS on top.
    _wx_problems = []
    for _f in ("call", "wind", "uv", "rain"):
        if not str(w.get(_f) or "").strip():
            _wx_problems.append("weather %s is missing or blank" % _f)
    if not isinstance(w.get("feels"), (int, float)) or isinstance(w.get("feels"), bool):
        _wx_problems.append("weather feels %r is not a number" % (w.get("feels"),))
    if _wx_problems:
        _verdict = "BUILD FAIL — weather box: " + "; ".join(_wx_problems)
        print(_verdict)
        _report_to_shared_error("build check", _verdict, kind="check_failed")
        raise SystemExit(1)

    # The lead story's writer (Clay's order, 2026-11-16, corrected the
    # same morning): no picture at the top of the paper — the writer's
    # small mark stands on the lead story's own byline line, beside the
    # writer's name. Muggy's picture, unless the edition records the
    # lead as Maggie's.
    lead_author = "maggie" if (d.get("author") or "").strip().lower() == "maggie" else "muggy"
    _lead_mark_path = author_mark(lead_author)
    lead_mark = ('<img class="writermark" src="%s" alt="%s">'
                 % (raw_img_src(_lead_mark_path),
                    "Aela" if lead_author == "maggie" else "Muggy")) if _lead_mark_path else ""

    subs = {
        "contact_href": "mailto:%s?subject=%s" % (CONTACT_EMAIL, _quote(_contact_subject)),
        "contact_addr": "…or write to us straight: %s" % CONTACT_EMAIL,
        "mooncol": mooncol,
        "weather_strip": weather_strip,
        "dateline": esc(d["dateline"]),
        "folio_date": esc(d.get("folio_date", "")),
        "edition": "%02d" % edition,
        "volume": volume,
        "weekday": esc(d.get("weekday", "")),
        "beast": esc(d.get("beast", "dragons")),
        "high": esc(w["high"]),
        "low": esc(w["low"]),
        "conditions": esc(w["conditions"]),
        "sunrise": esc(w["sunrise"]),
        "sunset": esc(w["sunset"]),
        "tomorrow_label": esc(w["tomorrow"]),
        "weather_call": esc(w.get("call", "")),
        "weather_wind": esc(w.get("wind", "")),
        "weather_uv": esc(w.get("uv", "")),
        "weather_feels": esc(w.get("feels", "")),
        "rain_label": esc(w.get("rain", "")),
        "headline": esc(d["headline"]),
        "lead": esc(d["lead"]),
        "listen_lead": listen_line(d["date"], "lead", top=True),
        "listen_today": listen_line(d["date"], "today", top=True),
        "listen_ahead": listen_line(d["date"], "ahead", top=True),
        "listen_merchant": listen_line(d["date"], "merchant", top=True),
        "listen_tale": listen_line(d["date"], "tale", top=True),
        "events_today": events_today,
        "events_week": events_week,
        "tasks": tasks,
        "due_soon": due_soon,
        "council_box": council_box,  # pre-built safe HTML fragment ("" skips the box)
        "lower_plate": lower_plate,  # wide local-view plate after the quest board ("" skips)
        "closing_plate": closing_plate,
        "filler_ad": "",  # closing filler ad — sized and set below, after the first pass
        "featured_box": featured_box,  # pre-built safe HTML fragment ("" skips the box)
        "merchant_name": esc(m.get("name", "")),
        "merchant_town": esc(m.get("town", "")),
        "merchant_blurb": esc(m.get("blurb", "")),
        "merchant_review": esc(m.get("review", "")),
        "merchant_review_src": msrc,
        "merchant_visit": mvisit,
        "merchant_why": esc(m.get("why", "")),
        "merchant_photos": _stacked_figs(m, (
            ("image", os.path.join(IMG, "market.jpg"), "At the merchant's counter", "Fresh from the merchant's kitchen."),
            ("image2", None, "", ""),
            ("image3", None, "", ""),
        )),
        "tale_title": esc(t.get("title", "A Tale from the Treeline")),
        "tale_text": tale_html,
        "tale_image": img_src(t.get("image", os.path.join(IMG, "rim.jpg"))),
        "tale_image_alt": esc(t.get("image_alt", "A creature of the Hold, up to mischief")),
        "tale_image_cap": esc(t.get("image_cap", "Spotted in the Hold.")),
        "rimstories_html": rimstories_html,        "quest_caption": esc(d.get("quest_caption", "The workshop, where the Hearth takes shape.")),
        "lead_mark": lead_mark,
        "lead_byline_name": "Aela" if lead_author == "maggie" else "Muggy",
        "hero_img": img_src(d.get("hero_image", os.path.join(IMG, "rim.jpg"))),
        "weather_img": img_src(d.get("weather_image", os.path.join(IMG, "rim.jpg"))),
        "hero_caption": esc(d.get("hero_caption", "Daybreak over the Mogollon Rim, as seen by our staff engraver.")),
        "weather_caption": esc(d.get("weather_caption", "The Hearth\u2019s chicken, out enjoying the weather.")),
        "weather_overheard": ('<div class="wquote"><div class="wqhead">' + esc(d.get("weather_overheard_title", "Overheard Last Night")) + '</div><div>' + esc(d.get("weather_overheard", "")) + '</div></div>') if d.get("weather_overheard") else "",
        "days_ahead_figure": ('<figure class="wfig"><img src="' + img_src(d["days_ahead_figure"]["image"]) +
            '" alt="' + esc(d["days_ahead_figure"].get("image_alt", "An engraving")) +
            '"><figcaption>' + esc(d["days_ahead_figure"].get("image_cap", "")) + '</figcaption></figure>')
            if d.get("days_ahead_figure") else "",
        "quest_img": img_src(d.get("quest_image", os.path.join(IMG, "workshop.jpg"))),
        "townhall_img": img_src(os.path.join(IMG, "townhall.jpg")),
    }
    # Closing filler ad, two passes (the height rule by FILLER_ADS):
    # print the edition with no ad, measure the last page's free
    # space, then set the ad to that measure. The web road has no
    # printed pages to measure — its ad stands at the full size.
    if WEB_MODE:
        subs["filler_ad"] = filler_ad_html(d)
    else:
        _free = _last_page_free_pt(TEMPLATE.substitute(subs))
        subs["filler_ad"] = filler_ad_html(d, _free)
    page = TEMPLATE.substitute(subs)
    page = _mark_login_links(page)
    return page


def main():
    _write_start_line()
    with open(sys.argv[1], encoding="utf-8") as f:
        d = json.load(f)
    page = render_page(d)

    os.makedirs(OUTDIR, exist_ok=True)
    out = os.path.join(OUTDIR, "payson-morning-scroll-%s.pdf" % d["date"])
    # The state of the output file before this run builds, for the
    # build check at the end: a file this run does not touch must
    # not pass on an earlier run's build.
    pre_state = None
    if os.path.isfile(out):
        _st = os.stat(out)
        pre_state = (_st.st_mtime_ns, _st.st_size)
    from weasyprint import HTML
    HTML(string=page, base_url=BASE).write_pdf(out)
    apply_parchment_backgrounds(out, d["date"])
    _listen_flagged = apply_listen_new_window(out)
    print("Listen links flagged for new window: %d" % _listen_flagged)
    print(out)

    # --- Build verdict (standards wiring step C, 2026-10-21; audit fix
    # item 7) ---------------------------------------------------------
    # The paper carries its own printed proof, in the same shape as the
    # verify programs: checks on the built file, then a closing verdict
    # line. A failed check stops the run — the verdict goes to the one
    # shared error program, no finish line is written, and the run
    # exits 1. One check compares the file against its state when
    # this run began: a file an earlier run left behind must not
    # pass for this run's build.
    failures = []
    if not os.path.isfile(out):
        failures.append("the paper PDF was not written")
    else:
        _st = os.stat(out)
        if pre_state is not None and pre_state == (_st.st_mtime_ns, _st.st_size):
            failures.append("the paper PDF was not written by this run")
        elif _st.st_size == 0:
            failures.append("the paper PDF is empty")
        else:
            try:
                import fitz
                _doc = fitz.open(out)
                if _doc.page_count < 1:
                    failures.append("the paper PDF has no pages")
                for _page in _doc:
                    for _link in _page.get_links():
                        _uri = _link.get("uri") or ""
                        if _uri.startswith("https://morning-scroll-53x.pages.dev/audio/morning-scroll-") and _uri.endswith(".mp3"):
                            _typ, _val = _doc.xref_get_key(_link.get("xref"), "A/NewWindow")
                            if _val != "true":
                                failures.append(f"recording link lacks NewWindow true: {_uri}")
                _doc.close()
            except Exception as exc:
                failures.append(f"the paper PDF does not open: {exc}")
    if failures:
        verdict = "VERDICT: FAIL — " + "; ".join(failures)
        print(verdict)
        _report_to_shared_error("build check", verdict, kind="check_failed")
        raise SystemExit(1)
    print("VERDICT: PASS")
    _write_finish_line("paper built", out)


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
