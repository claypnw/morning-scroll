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
edition date (Clay's scheme, 2026-10-03): volume = YYMM (e.g. October 2026
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
"""
import html
import json
import math
import os
import random
import sys
import hashlib
from string import Template
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HOME = os.path.expanduser("~")
BASE = os.path.join(HOME, "workspace", "morning-post")
IMG = os.path.join(BASE, "images")
OUTDIR = os.path.join(HOME, "workspace", "goals", "morning-agenda-briefing", "files")
COUNTER = os.path.join(BASE, "edition_counter.txt")
CONTACT_EMAIL = "mogollonshearth@gmail.com"  # the "Ask the Hearth" button in the colophon writes here — the Hearth's main address (Clay, 2026-10-03)


def esc(s):
    return html.escape(str(s), quote=False)


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
MOON_FACE = os.path.join(IMG, "moon-face.jpg")  # the Hearth's standing moon face (Clay, 2026-10-04); only the phase changes nightly
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
    # the engraving's texture faintly visible (Clay, 2026-10-04).
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


def dude_badge():
    """Circular byline badge: the Dude's portrait in a ring with his name
    arced along the bottom edge of the circle (Clay, 2026-10-01). Built from
    images/dude.jpg at build time, so the portrait's daily subtle change
    carries through. Returns a transparent PNG (cached by source mtime)."""
    src = os.path.join(IMG, "dude.jpg")
    if not os.path.isfile(src):
        return tinted(src)
    try:
        st = os.stat(src)
        key = hashlib.sha1(("badge|%d|%d" % (st.st_size, int(st.st_mtime))).encode()).hexdigest()
        os.makedirs(BADGE_CACHE, exist_ok=True)
        dst = os.path.join(BADGE_CACHE, key + ".png")
        if os.path.isfile(dst):
            return dst
        S = 900
        c = S // 2
        im = Image.open(tinted(src)).convert("RGB")
        w0, h0 = im.size
        m = min(w0, h0)
        im = im.crop(((w0 - m) // 2, (h0 - m) // 2,
                      (w0 + m) // 2, (h0 + m) // 2)).resize((S, S), Image.LANCZOS)
        R_out, band = c - 8, 96
        R_pic = R_out - band
        badge = Image.new("RGBA", (S, S), (0, 0, 0, 0))
        bd = ImageDraw.Draw(badge)
        ink = (26, 26, 26, 255)
        # parchment ring band carrying the name
        bd.ellipse([c - R_out, c - R_out, c + R_out, c + R_out], fill=PARCHMENT + (255,))
        pmask = Image.new("L", (S, S), 0)
        ImageDraw.Draw(pmask).ellipse([c - R_pic, c - R_pic, c + R_pic, c + R_pic], fill=255)
        badge.paste(im, (0, 0), pmask)
        bd = ImageDraw.Draw(badge)
        bd.ellipse([c - R_out, c - R_out, c + R_out, c + R_out], outline=ink, width=9)
        bd.ellipse([c - R_pic, c - R_pic, c + R_pic, c + R_pic], outline=ink, width=5)
        # DUDE arced along the bottom of the ring, letters standing on the arc
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf", 84)
        name = "DUDE"
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
        return tinted(src)


# Aged-parchment page backgrounds. Each page gets its own unique sheet,
# generated with PIL and composited BEHIND the content, so stains are always
# background, never over text. Seeded by date: rebuilds are stable, and no
# two pages (or editions) ever share the same marks. Stains stay sparse —
# zero to two coffee rings in the whole scroll (Clay, 2026-09-29).
PARCHMENT_BG = (232, 201, 140)
PARCH_CACHE = os.path.join(BASE, ".cache", "parchment")
PARCH_W, PARCH_H = 1275, 1650  # 8.5x11in at 150dpi
PARCH_VERSION = "v10"  # v10: folio rules drawn in the parchment — a printed rule under the running header and above the footer on pages 2+ (Clay 2026-10-03; WeasyPrint margin boxes are shrink-to-fit and can't span full width); v9: rounded corners (radius 56, Clay 2026-10-02 — the pointy corners looked weird); v8: corner pinning against triangular flaps; v7: deeper deckled waves (max_depth 55); v6: warm amber sheet, faint creases, from his reference image; v5: varied hand-torn edges (Clay 2026-10-01); v4: rougher torn edges, darker at the edges


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
    boundary. v5 (Clay, 2026-10-01): the v4 uniform noise made endless
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
    """Alpha mask for scorched/deckled old-parchment edges (v9, Clay,
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
    behind a picture (Clay, 2026-10-02)."""
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
    # scorched/deckled old-parchment edges (Clay, 2026-10-02; was torn
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
        # folio rules (Clay, 2026-10-03): a printed rule under the running
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
    paper, crossing pictures and print, never behind them (Clay, 2026-10-02).
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
    # (Clay, 2026-10-06 — a coffee ring plus an ale ring reads as two cup-rings).
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
        # never behind them (Clay, 2026-10-02).
        st = plan.get(i)
        if st:
            ov = stain_overlay(date_str, i, tuple(st))
            page.insert_image(page.rect, filename=ov, overlay=True)
    tmp = pdf_path + ".aged"
    doc.save(tmp, garbage=4, deflate=True)
    doc.close()
    os.replace(tmp, pdf_path)


TEMPLATE = Template("""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>The Payson Morning Scroll — $dateline</title>
<style>
  @page { size: Letter; margin: 0.62in 0.5in 0.60in 0.5in;
    @top-left { content: "The Payson Morning Scroll"; font-variant: small-caps; font-weight: bold; letter-spacing: 1px; font-size: 8.5pt; color: #3a2c1c; vertical-align: bottom; padding-bottom: 5px; }
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
  .masthead { text-align: center; border-bottom: 4px double #1a1a1a; padding-bottom: 5px; }
  .masthead .nameplate {
    font-weight: 900; font-size: 40pt; letter-spacing: 2px;
    margin: 0; line-height: 1.05; font-variant: small-caps;
  }
  .masthead .dedication {
    font-variant: small-caps; letter-spacing: 2px; font-size: 10.5pt;
    margin: 4px 0 0 0;
  }
  .masthead .motto { font-style: italic; font-size: 9.5pt; margin: 2px 0 0 0; }
  .masthead .publisher { font-variant: small-caps; letter-spacing: 2px; font-size: 9.5pt; font-weight: bold; margin: 3px 0 0 0; }
  .dateline {
    font-size: 8.5pt; font-variant: small-caps; letter-spacing: 0.5px;
    border-bottom: 1px solid #1a1a1a; padding: 4px 2px; margin-bottom: 8px;
    text-align: center; word-spacing: 6px;
  }
  .dateline .sec { white-space: nowrap; }
  .weather {
    border: 1.5px solid #1a1a1a; padding: 5px 10px; margin-bottom: 10px;
    font-size: 9pt; display: table; width: 100%; box-sizing: border-box;
  }
  .weather .wimg { display: table-cell; width: 1.45in; vertical-align: top; padding-right: 12px; }
  .weather .wimg img { width: 100%; display: block; border: 1px solid #1a1a1a; }
  .weather .wcap { font-size: 7pt; font-style: italic; color: #444; text-align: center; padding-top: 2px; }
  .weather .wbody { display: table-cell; vertical-align: middle; text-align: center; }
  .weather .wbody > div { margin: 2px 0; }
  .weather .wtitle { font-weight: 900; font-variant: small-caps; letter-spacing: 2px; font-size: 11pt; }
  .weather .wnow { font-size: 24pt; font-weight: 900; line-height: 1; }
  .weather .wcond { font-size: 11pt; font-weight: bold; }
  .weather .wdet { font-size: 9pt; color: #333; }
  .weather .wheard { font-size: 8pt; font-style: italic; color: #333; margin-top: 3px; }
  .weather .wquote { display: table-cell; width: 2.0in; vertical-align: middle;
    font-size: 8pt; font-style: italic; color: #333; line-height: 1.25;
    border-left: 1px solid #999; padding-left: 10px; }
  .weather .wqhead { font-size: 8.5pt; font-weight: 900; font-style: normal;
    font-variant: small-caps; letter-spacing: 1px; color: #1a1a1a;
    margin-bottom: 3px; }
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
  .bylinestack { display: flex; flex-direction: column; align-items: center; }
  .bylinestack .byline { margin: 3px 0 0 0; border: none; padding: 0; text-align: center; }
  .bylinebadge { width: 1.05in; height: 1.05in; }
  figure { margin: 0 0 8px 0; }
  figure img { width: 100%; display: block; border: 1px solid #1a1a1a; }
  figcaption { font-size: 8pt; font-style: italic; color: #444; padding-top: 3px; }
  .hero { margin-bottom: 8px; max-width: 6.0in; margin-left: auto; margin-right: auto; }
  .hero img { width: 100%; height: auto; }
  p.lead { font-size: 11.5pt; text-align: justify; hyphens: auto; margin: 0 0 10px 0; }
  p.lead::first-letter { font-size: 15pt; font-weight: 900; }
  ul.eventlist { list-style: none; margin: 0; padding: 0; border-top: 2.5px solid #1a1a1a; }
  ul.eventlist li { position: relative; font-size: 10pt; line-height: 1.4;
    padding: 4px 0 4px 20px; border-bottom: 1px solid #999; }
  ul.eventlist li::before { content: "\\2022"; position: absolute; left: 4px; top: 6px; font-size: 12pt; }
  /* Days Ahead flow (Clay, 2026-10-01): a day's item may break BETWEEN its
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
  /* Gap-filler engraving (Clay, 2026-10-01): an optional floated figure at the
     top of The Days Ahead, closely related to what's on that page — fresh
     every edition, fun and light. Text wraps around it. */
  .wfig { float: right; width: 2.2in; margin: 2px 0 6px 10px; break-inside: avoid; }
  /* Blank-space plates (Clay, 2026-10-01): old-timey pictures, local art, and
     views of the town used to fill page/column gaps — never story filler. */
  .plateitem { break-inside: avoid; padding-left: 0 !important; }
  .plateitem::before { content: "" !important; }
  .plateitem figure { margin: 4px 0 2px 0; }
  .plateitem img { width: 100%; height: 1.5in; object-fit: cover; object-position: 50% 82%; display: block; border: 1px solid #1a1a1a; }
  .wideplate { margin-top: 8px; break-inside: avoid; }
  .wideplate img { width: 100%; height: 1.6in; object-fit: cover; display: block; border: 1px solid #1a1a1a; }
  .wideplate figcaption { font-size: 7.5pt; font-style: italic; color: #444; padding-top: 2px; }
  .closingplate { margin: 4px auto 0 auto; width: 5.4in; break-inside: avoid; }
  .closingplate img { width: 100%; height: 0.34in; object-fit: cover; display: block; border: 1px solid #1a1a1a; }
  .closingplate figcaption { font-size: 7.5pt; font-style: italic; color: #444; padding-top: 2px; text-align: center; }
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
  .weather .wmoons { display: table-cell; width: 1.75in; vertical-align: middle;
    text-align: center; border-left: 1px solid #999; padding-left: 10px; }
  .weather .wmhead { font-size: 8pt; font-weight: 900; font-variant: small-caps;
    letter-spacing: 1px; margin-bottom: 2px; }
  .weather .wmoonrow { white-space: nowrap; }
  .weather .wmoon { display: inline-block; vertical-align: middle; width: 42px; margin: 0 2px; }
  .weather .wmoon.tonight { width: 54px; }
  .weather .wmoon img { width: 100%; display: block; }
  .weather .wmoon figcaption { font-size: 6.5pt; line-height: 1.2; color: #444; }
  .weather .wmtrend { font-size: 6.5pt; font-style: italic; color: #555; margin-top: 1px; }
  .weather .wmkey { font-size: 7pt; margin-top: 2px; }
  .weather .wmkey2 { font-size: 6pt; font-style: italic; color: #555; line-height: 1.25; }
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
  a { color: #1a1a1a; text-decoration: underline; }
</style>
</head>
<body>

<div class="masthead">
  <p class="nameplate">The Payson Morning Scroll</p>
  <p class="dedication">Made Exclusively for the Mogollon&rsquo;s Hearth Guests</p>
  <p class="motto">&ldquo;All the news worth knowing before the mead hall opens.&rdquo;</p>
  <p class="publisher">The Greybeards of High Hrothgar &mdash; Publisher &amp; Proprietor</p>
</div>
<div class="dateline"><span class="sec">Payson, Arizona</span> &middot; <span class="sec">$dateline</span> &middot; <span class="sec">Morning Edition &mdash; Vol. $volume, No. $edition</span> &middot; <span class="sec">Price: One Septim</span></div>

<div class="weather">
  <div class="wimg">
    <img src="$weather_img" alt="The Hearth's chicken in today's weather">
    <div class="wcap">$weather_caption</div>
  </div>
  <div class="wbody">
    <div class="wtitle">Skies O&rsquo;er the Hold</div>
    <div class="wnow">$high&deg; / $low&deg;</div>
    <div class="wcond">$conditions</div>
    <div class="wdet">Sunrise $sunrise &nbsp;&middot;&nbsp; Sunset $sunset</div>
    <div class="wdet">Tomorrow &mdash; $tomorrow_label</div>
  </div>
  $weather_overheard
  $mooncol
</div>

<div class="headrow">
  <div class="headtxt">
    <p class="kicker">Around the Holds &middot; The Week Ahead</p>
    <h1 class="headline">$headline</h1>
  </div>
  <div class="bylinestack">
    <img class="bylinebadge" src="$dude_img" alt="The Dude, Bard of the Morning Scroll">
    <p class="byline">Payson, Ariz.</p>
  </div>
</div>
<figure class="hero">
  <img src="$hero_img" alt="Front page engraving">
  <figcaption>$hero_caption</figcaption>
</figure>
<div class="story">
  <p class="lead">$lead</p>
  <h3 class="evhead">Happening in the Holds Today</h3>
  <ul class="eventlist">
    $events_today
  </ul>
  <h3 class="evhead">The Days Ahead</h3>
  $days_ahead_figure
  <ul class="eventlist">
    $events_week
  </ul>
</div>

$featured_box
<div class="lower">
  <div class="box">
    <h2>Quests of the Hearth</h2>
    <div class="body">
      <figure class="qfig"><img src="$quest_img" alt="Workshop, engraving"><figcaption>$quest_caption</figcaption></figure>
      <p><b>Quests awaiting:</b></p>
      <ul>
        $tasks
      </ul>
      $due_soon
      <div class="clear"></div>
    </div>
  </div>
  $council_box
  $lower_plate
</div>

<div class="box merchant">
  <h2>Merchant of the Hold</h2>
  <div class="body">
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
    <p class="taletitle">$tale_title</p>
    <table class="mcols"><tr>
      <td class="mcol mphoto"><figure style="margin:0"><img src="$tale_image" alt="$tale_image_alt"><figcaption>$tale_image_cap</figcaption></figure></td>
      <td class="mcol">$tale_text</td>
    </tr></table>
  </div>
</div>

<div class="colophon">
  Printed with pride in Payson, in the shadow of the Rim &middot; Set in hot metal by Dude, Bard of the Morning Scroll &middot; May your $weekday be free of $beast, Clay.
  <br><a class="contact-btn" href="$contact_href">Ask the Hearth &#9993;</a>
</div>
$closing_plate

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
            '<figure style="margin:0 0 8px 0"><img src="file://%s" alt="%s">'
            "<figcaption>%s</figcaption></figure>"
            % (tinted(p), esc(m.get(key + "_alt", dalt)),
               esc(m.get(key + "_cap", dcap))))
    return "".join(figs)


def main():
    with open(sys.argv[1], encoding="utf-8") as f:
        d = json.load(f)

    # Skyrim calendar (Clay, 2026-09-29): the old Tamrielic reckoning. Months
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
        # "May your Tirdas be free of wolves, Clay."
        if not d.get("weekday"):
            d["weekday"] = _sky_day
        # The masthead dateline flies the Skyrim reckoning first, with the
        # lowlanders' date alongside so the facts stay plain:
        # "Tirdas, the 29th of Hearthfire (Tuesday, September 29, 2026)".
        if d.get("dateline"):
            d["dateline"] = "%s, the %s of %s (%s)" % (
                _sky_day, _ordinal(_sky.day),
                SKYRIM_MONTHS[_sky.month - 1], d["dateline"])
        # Running-head date for the page headers on pages 2+ (Clay asked for
        # headers and footers, 2026-10-01): the short Skyrim reckoning with
        # the lowlanders' date alongside, one line: "1st of Frostfall (Oct 1, 2026)".
        d["folio_date"] = "%s of %s (%s %d, %d)" % (
            _ordinal(_sky.day), SKYRIM_MONTHS[_sky.month - 1],
            _sky.strftime("%b"), _sky.day, _sky.year)
    elif not d.get("weekday"):
        d["weekday"] = ""

    # Colophon beast: rotate the blessing's menace daily (Clay, 2026-09-29) —
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

    ed_year = int(str(d["date"])[:4])          # volume = YYMM of the edition date (Clay 2026-10-03)
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
            return '<img class="holdbanner" src="file://%s">' % tinted(p)
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
            '    <p class="taletitle">%s</p>\n'
            '    <table class="mcols"><tr>\n'
            '      <td class="mcol mphoto"><figure style="margin:0"><img src="%s" alt="%s"><figcaption>%s</figcaption></figure></td>\n'
            '      <td class="mcol">%s</td>\n'
            '    </tr></table>\n'
            '  </div>\n'
            '</div>\n'
        ) % (
            esc(r.get("title", "Word from Afar")),
            "file://" + tinted(r.get("image", os.path.join(IMG, "rim.jpg"))),
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
        ) % ("file://" + tinted(os.path.join(IMG, "townhall.jpg")), council_html)
    else:
        council_box = ""

    # Featured spread (Clay, 2026-09-29): big once-a-year events get a bigger
    # box with what/where/when, admission, and a "why go" line. Absent (or
    # empty title) skips the box entirely.
    f = d.get("featured")
    if f and str(f.get("title", "")).strip():
        f_paras = [p.strip() for p in str(f.get("text", "")).split("\n\n") if p.strip()]
        f_text = "".join("<p>%s</p>" % esc(p) for p in f_paras)
        featured_box = (
            '<div class="box featured">\n'
            '  <h2>%s</h2>\n'
            '  <div class="body">\n'
            '    <p class="mname">%s</p>\n'
            '    <figure class="ffig"><img src="%s" alt="%s"><figcaption>%s</figcaption></figure>\n'
            '    %s\n'
            '    <p class="mvisit">%s</p>\n'
            '    <p class="mwhy"><b>Why go:</b> %s</p>\n'
            '    <div class="clear"></div>\n'
            '  </div>\n'
            '</div>\n'
        ) % (
            esc(f.get("kicker", "A Special Spread")),
            esc(f.get("title", "")),
            "file://" + tinted(f.get("image", os.path.join(IMG, "rim.jpg"))),
            esc(f.get("image_alt", "A grand doings in the Hold")),
            esc(f.get("image_cap", "Not to be missed.")),
            f_text,
            esc(f.get("details", "")),
            esc(f.get("why", "")),
        )
    else:
        featured_box = ""

    # Blank-space plates (Clay, 2026-10-01): optional old-timey pictures that
    # fill gaps a page would otherwise leave blank — a column plate under
    # today's happenings, a wide local view after the quest board, and a
    # closing skyline strip under the colophon. Pictures, not story filler.
    def _plate(field, cls):
        p = d.get(field) or {}
        if not p.get("image"):
            return ""
        return ('<figure class="%s"><img src="file://%s" alt="%s">'
                '<figcaption>%s</figcaption></figure>') % (
            cls, tinted(p["image"]),
            esc(p.get("image_alt", "An engraving")),
            esc(p.get("image_cap", "")))
    today_plate = _plate("today_plate", "platefig")
    if today_plate:
        events_today += '\n  <li class="plateitem">' + today_plate + "</li>"
    lower_plate = _plate("lower_plate", "wideplate")
    closing_plate = _plate("closing_plate", "closingplate")

    # "Send word to Clay" button (Clay, 2026-10-03): mailto his address with
    # the edition's date in the subject, so he knows which Scroll the guest
    # is writing about.
    from urllib.parse import quote as _quote
    _contact_subject = "The Payson Morning Scroll"
    if _sky is not None:
        _contact_subject += " \u2014 %s %d, %d" % (_sky.strftime("%B"), _sky.day, _sky.year)

    # The Moon's Reckoning (Clay, 2026-10-04): the fourth section of the
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
        _pname = _mname if (_mlabel == "Tonight" or _mname != _tonight_name) else ""
        _cap = esc(_mlabel) + ("<br />" + esc(_pname) if _pname else "")
        _moonfigs.append(
            '<figure class="wmoon %s"><img src="file://%s" alt="The moon, %s" />'
            '<figcaption>%s</figcaption></figure>'
            % (_cls, tinted(_mpath), esc(_mname), _cap))
    if _sky is not None:
        _reckon = "%s of %s = %s %d" % (_ordinal(_sky.day), SKYRIM_MONTHS[_sky.month - 1],
                                       _sky.strftime("%B"), _sky.day)
    else:
        _reckon = ""
    mooncol = (
        '<div class="wmoons">'
        '<div class="wmhead">The Moon&rsquo;s Reckoning</div>'
        '<div class="wmoonrow">' + "".join(_moonfigs) + '</div>'
        '<div class="wmtrend">%s</div>'
        '<div class="wmkey">%s</div>'
        '<div class="wmkey2">Months run one-for-one all year<br />Sundas=Sun &hellip; Loredas=Sat</div>'
        '</div>'
    ) % (esc(_trend), esc(_reckon)) if _moonfigs else ""

    subs = {
        "contact_href": "mailto:%s?subject=%s" % (CONTACT_EMAIL, _quote(_contact_subject)),
        "mooncol": mooncol,
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
        "headline": esc(d["headline"]),
        "lead": esc(d["lead"]),
        "events_today": events_today,
        "events_week": events_week,
        "tasks": tasks,
        "due_soon": due_soon,
        "council_box": council_box,  # pre-built safe HTML fragment ("" skips the box)
        "lower_plate": lower_plate,  # wide local-view plate after the quest board ("" skips)
        "closing_plate": closing_plate,  # skyline strip under the colophon ("" skips)
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
        "tale_image": "file://" + tinted(t.get("image", os.path.join(IMG, "rim.jpg"))),
        "tale_image_alt": esc(t.get("image_alt", "A creature of the Hold, up to mischief")),
        "tale_image_cap": esc(t.get("image_cap", "Spotted in the Hold.")),
        "rimstories_html": rimstories_html,        "quest_caption": esc(d.get("quest_caption", "The workshop, where the Hearth takes shape.")),
        "dude_img": "file://" + dude_badge(),
        "hero_img": "file://" + tinted(d.get("hero_image", os.path.join(IMG, "rim.jpg"))),
        "weather_img": "file://" + tinted(d.get("weather_image", os.path.join(IMG, "rim.jpg"))),
        "hero_caption": esc(d.get("hero_caption", "Daybreak over the Mogollon Rim, as seen by our staff engraver.")),
        "weather_caption": esc(d.get("weather_caption", "The Hearth\u2019s chicken, out enjoying the weather.")),
        "weather_overheard": ('<div class="wquote"><div class="wqhead">' + esc(d.get("weather_overheard_title", "Overheard Last Night")) + '</div><div>' + esc(d.get("weather_overheard", "")) + '</div></div>') if d.get("weather_overheard") else "",
        "days_ahead_figure": ('<figure class="wfig"><img src="file://' + tinted(d["days_ahead_figure"]["image"]) +
            '" alt="' + esc(d["days_ahead_figure"].get("image_alt", "An engraving")) +
            '"><figcaption>' + esc(d["days_ahead_figure"].get("image_cap", "")) + '</figcaption></figure>')
            if d.get("days_ahead_figure") else "",
        "quest_img": "file://" + tinted(d.get("quest_image", os.path.join(IMG, "workshop.jpg"))),
        "townhall_img": "file://" + tinted(os.path.join(IMG, "townhall.jpg")),
    }
    page = TEMPLATE.substitute(subs)

    os.makedirs(OUTDIR, exist_ok=True)
    out = os.path.join(OUTDIR, "payson-morning-scroll-%s.pdf" % d["date"])
    from weasyprint import HTML
    HTML(string=page, base_url=BASE).write_pdf(out)
    apply_parchment_backgrounds(out, d["date"])
    print(out)


if __name__ == "__main__":
    main()
