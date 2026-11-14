#!/usr/bin/env python3
"""Morning Scroll: build_edition_page.py

Builds one edition's WEB PAGE — the reading road (the admin's
ruling, 2026-10-26: the Scroll is read as a web page; a PDF, when
wanted, is the reader's own Chrome print of the page).

The page is the same paper from the same source: build_paper's
render_page() over editions/DATE/edition.json, with build_paper's
web road set (WEB_MODE) so each part's listen line — standing at
the top of its part, as in the paper — links to that part's own
recording with target="_blank" rel="noopener": the recording opens
in a new window, the paper stays open, and closing the recording's
window leaves the paper standing. The listen gate is the paper's
own, unchanged: a part's line prints only when that part's
recording stands on its record at the recorded size — no standing
recording, no line, never a dead link. Quests of the Hearth is a
work list, not a story, and carries no line, as in the paper.

The pictures are the paper's own, copied out under images/ with
content-named files (build_paper remembers them on the web road).

The screen sheet injected before </head> (a viewport line and one
style block) only sets how the page sits on a screen: a parchment
sheet at the paper's own width on a darker ground, and on narrow
screens a one-column flow. No word of the paper changes, and
nothing is hidden at any width.

The page also carries the story player (2026-11-10), in the
Scroll's own pop-up form (the admin's order, 2026-11-10): the same
black bar that stands on My Daily Review and the AI community
report — one rounded black bar, all seven buttons in one row,
plain white shapes with the plain word under each — but it does
NOT stand on the page while a guest is only reading. Each story
keeps its own listen line, and the moment a guest taps one, the
player starts at that story and the bar pops up floating, pinned
to the TOP RIGHT of the screen, where it stays in reach while the
page scrolls. Pressing Stop, or the last story ending, hides the
bar again and returns the page to plain reading. The bar plays
the edition's parts in page order from the page's own listen
lines, with the "Story N of M" line, the story's title, and the
time line travelling with it. A part whose recording does not
stand has no listen line and so no track; fewer than two tracks,
no player — the listen lines then open their recordings in a new
window, as the paper's road above describes.

The page also carries the maps corner (2026-11-11, the admin's
order): a standing link on page one, in the masthead's right flank
— upper right, under the nameplate and clear of the weather box —
to the World of Nirn atlas, the maps ChatGPT keeps for Mogollon's
Hearth, published at the hearth build page's maps/ address. It is
set into every edition this build makes, in the paper's own small
bordered style, and its words are plain: "World of Nirn — the maps".

The page also loads the guest-tablet checker (guest-tablet-check.js,
one script line before the closing body tag, 2026-10-31): links the
paper's build marked as leaning on a login (build_paper's
_mark_login_links; facebook.com is the proven wall) show as plain
words on Clay's guest Fire tablet — singled out by the setup mark in
its browser — and stand live on every other device.

Usage:
  venv/bin/python build_edition_page.py DATE [--json PATH] [--out-dir DIR]

Writes OUT_DIR/edition-DATE.html and OUT_DIR/images/<pictures>;
prints one "WROTE <name>" line per file (names relative to
OUT_DIR), then a listen-link count. Defaults: the edition JSON at
editions/DATE/edition.json, OUT_DIR at publish-upload/.
"""
import argparse
import html
import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import build_paper


# --- Shared error program (standards wiring step A, 2026-10-21) -------------
# The one shared error program is ~/workspace/batch/shared_error.py.
# Errors this program reports go there, and the standard processing —
# write the error down in full in the dated error record, open an
# ERROR line in the completion pile, hand back STOP — happens in that
# one program, never in code copied here. This block is only the
# call: locate the program, pass the error in, branch on what comes
# back. If the shared error program cannot be loaded or cannot
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
                    # fails to load is treated the same as one that
                    # cannot be found: fall back, never raise at
                    # startup.
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


_STEP = "start"


def fail(message, kind="check_failed"):
    """One failure path: print the ERROR line, hand the error to the
    one shared error program, and exit on the STOP it hands back."""
    print(f"ERROR: {message}")
    result = _report_to_shared_error(_STEP, message, kind=kind)
    sys.exit(result["exit_code"] if result else 1)


# The screen sheet. Injected into the rendered page before </head>,
# after the paper's own styles, so these lines win where they speak
# and stay silent everywhere else. Layout only — no content rule,
# nothing hidden at any width.
SCREEN_SHEET = """
<style>
/* The web page's screen sheet (2026-10-26): how the paper sits on a
   screen — a parchment sheet at the paper's own width on a darker
   ground; on narrow screens the sheet fills the screen and the
   story's two columns flow as one. The paper's own styles above lay
   out its parts; nothing here changes a word or hides a part. */
html { background: #a08c62; }
body { max-width: 8.5in; margin: 20px auto; padding: 0.32in 0.5in 0.55in;
       background: #f2e6c2; box-shadow: 0 2px 18px rgba(40,28,8,.5); }
img { max-width: 100%; }
/* The By the Hours strip: Chrome lays the hour cells a touch wider
   than the print engine does, and the wind number printed beside
   the windsock rides over the weather box's edge. On screen it
   stands under the windsock instead — where the paper's own design
   note puts it — inside the cell at every width. */
.wxpics .wxmph { display: block; margin: 1px 0 0 0; }
@media (max-width: 700px) {
  body { margin: 0; padding: 10px 12px 22px; }
  .masthead .nameplate { font-size: 20pt; letter-spacing: 1px; }
  h1.headline { font-size: 21pt; }
  .story { column-count: 1; }
  .frontpic, .wfig, .box .ffig, .box .qfig { float: none; width: 100%;
    margin: 2px 0 8px 0; }
  .headrow { flex-direction: column; }
  .mcols td { display: block; width: auto; padding: 0 0 6px 0; }
  .mcols td.mtext2 { border-left: none; padding-left: 0; }
  /* The By the Hours strip on a narrow screen: each hour's words
     and pictures stand side by side as two table cells, and the
     picture cell cannot shrink below its pictures — in Chrome the
     pictures paint over the next hour's degrees and run past the
     sheet's edge. Stack them instead: the words over the pictures,
     inside each hour's own quarter of the strip. */
  .wxmain { display: block; }
  .wxwords { display: block; }
  .wxpics { display: block; width: auto; padding-left: 0; text-align: center; }
  .wxrow1 { display: block; }
  .weather .wimg, .weather .wbody, .weather .wquote, .weather .wmoons {
    display: block; width: auto; border-left: none; padding-left: 0;
    margin: 6px 0 0 0; }
  .weather .wimg img { margin: 0 auto 3px auto; }
}
</style>
"""


# --- The story player (the admin's order, 2026-11-10) -----------------
# The same player bar that stands on My Daily Review and the AI
# community report, in the admin's own picture: ONE black rounded
# bar, all seven buttons in one row inside it, each a plain white
# SVG shape with its plain word in small white text under the shape.
# The track list is the edition's own listen lines, in page order —
# a part's line stands only when its recording stands (the paper's
# own listen gate above), so the player never carries a dead track.
# The "Story N of M" line with the story's title, and the time
# line, travel with the bar.
# The Scroll's own form (the admin's order, 2026-11-10): the bar
# does NOT stand on the page while a guest is only reading. Its
# block stands hidden in the page; the moment a guest taps a
# story's listen line, the player starts at that story and the bar
# pops up floating, pinned to the TOP RIGHT of the screen, where
# it stays in reach while the page scrolls. Pressing Stop, or the
# last story ending, hides the bar again. Fewer than two parts
# with recordings -> no player, the page stands as built (the
# per-part listen lines are the fallback).

PLAYER_SHEET = """
<style>
/* The story player (2026-11-10, the Scroll's pop-up form): the
   block stands hidden while a guest is only reading; on a Listen
   tap it pops up as one black rounded panel floating at the TOP
   RIGHT of the screen — all seven buttons in one row inside it,
   white shapes and words, the "Story N of M" line with the title
   and the time line under the buttons — and hides again on Stop
   or at the last story's end. The panel is capped at the screen's
   width so it stands fully on screen and tappable at phone width
   as well as desktop width. */
#scroll-player { display: none; }
#scroll-player.wp-open { display: block; position: fixed;
  top: 10px; right: 10px; z-index: 9999;
  width: min(430px, calc(100vw - 20px));
  background: #111; border-radius: 22px;
  padding: 12px 14px 10px; text-align: center;
  box-shadow: 0 6px 28px rgba(0,0,0,.55); }
.whole-player .wp-bar { display: flex; flex-wrap: nowrap;
  align-items: flex-start; background: #111; border-radius: 60px;
  padding: 0; }
.whole-player .wp-bar .wp-btn { flex: 1 1 0; width: auto; min-width: 0;
  min-height: 0; margin: 0; padding: 3px 1px; background: transparent;
  border: none; border-radius: 16px; color: #fff; cursor: pointer;
  font-family: Arial, Helvetica, sans-serif; line-height: 1.25; }
.whole-player .wp-bar .wp-btn:active { background: #333; }
.whole-player .wp-bar .wp-btn .sym { display: block; line-height: 0; }
.whole-player .wp-bar .wp-btn .sym svg { width: 32px; height: 32px; }
.whole-player .wp-bar .wp-btn .word { display: block; font-size: 11px;
  font-weight: 400; margin-top: 3px; color: #fff; }
.whole-player #now-playing { font-weight: 700; margin: 10px 0 0;
  font-size: 15.5px; color: #fff; }
.whole-player .wp-time { margin: 2px 0 0; font-size: 14px;
  color: #ccc; font-variant-numeric: tabular-nums; }
@media (max-width: 480px) {
  #scroll-player.wp-open { top: 6px; right: 6px;
    width: calc(100vw - 12px); border-radius: 18px;
    padding: 10px 8px 8px; }
  .whole-player .wp-bar .wp-btn .sym svg { width: 26px; height: 26px; }
  .whole-player .wp-bar .wp-btn .word { font-size: 9.5px; }
  .whole-player #now-playing { font-size: 14px; }
}
</style>
"""


def _svg(inner):
    return ('<svg viewBox="0 0 48 48" aria-hidden="true" '
            f'focusable="false">{inner}</svg>')


_W = 'fill="#fff"'
ICON_BEGIN = _svg(
    f'<rect x="5" y="11" width="5" height="26" {_W}/>'
    f'<polygon points="25,11 10,24 25,37" {_W}/>'
    f'<polygon points="41,11 26,24 41,37" {_W}/>')
ICON_BACK = _svg(
    f'<polygon points="23,7 9,20 23,33" {_W}/>'
    f'<polygon points="40,7 26,20 40,33" {_W}/>'
    f'<text x="24" y="45" font-size="11" font-weight="bold" '
    f'font-family="Arial, Helvetica, sans-serif" '
    f'text-anchor="middle" {_W}>10</text>')
ICON_PLAY = _svg(f'<polygon points="17,10 38,24 17,38" {_W}/>')
ICON_PAUSE = _svg(
    f'<rect x="15" y="11" width="6.5" height="26" {_W}/>'
    f'<rect x="26.5" y="11" width="6.5" height="26" {_W}/>')
ICON_FWD = _svg(
    f'<polygon points="8,7 22,20 8,33" {_W}/>'
    f'<polygon points="25,7 39,20 25,33" {_W}/>'
    f'<text x="24" y="45" font-size="11" font-weight="bold" '
    f'font-family="Arial, Helvetica, sans-serif" '
    f'text-anchor="middle" {_W}>10</text>')
ICON_NEXT = _svg(
    f'<polygon points="7,11 22,24 7,37" {_W}/>'
    f'<polygon points="23,11 38,24 23,37" {_W}/>'
    f'<rect x="39" y="11" width="5" height="26" {_W}/>')
ICON_STOP = _svg(f'<rect x="12" y="12" width="24" height="24" {_W}/>')

PLAYER_JS_TEMPLATE = """(function () {
  var TRACKS = __PLAYLIST__;
  var audio = document.getElementById('edition-audio');
  var nowEl = document.getElementById('now-playing');
  var timeEl = document.getElementById('time-line');
  var player = document.getElementById('scroll-player');
  var idx = 0, done = false;
  function showPlayer() { player.classList.add('wp-open'); }
  function hidePlayer() { player.classList.remove('wp-open'); }
  function fmt(s) {
    if (!isFinite(s) || s < 0) s = 0;
    s = Math.floor(s);
    return Math.floor(s / 60) + ':' + ('0' + (s % 60)).slice(-2);
  }
  function showLine() {
    if (done) {
      nowEl.textContent = 'All ' + TRACKS.length + ' stories are done';
    } else {
      nowEl.textContent = 'Story ' + (idx + 1) + ' of ' + TRACKS.length + ' \\u2014 ' + TRACKS[idx].title;
    }
    timeEl.textContent = fmt(audio.currentTime) + ' of ' + fmt(audio.duration);
    if ('mediaSession' in navigator) {
      try {
        navigator.mediaSession.metadata = new MediaMetadata({ title: TRACKS[idx].title, artist: 'Payson Morning Scroll' });
      } catch (e) {}
    }
  }
  function load(i, autoplay) {
    idx = i; done = false;
    audio.src = TRACKS[i].href;
    audio.load();
    showLine();
    if (autoplay) { audio.play(); }
  }
  function goBegin() {
    if (done) { load(0, false); return; }
    if (audio.currentTime <= 5 && idx > 0) {
      load(idx - 1, !audio.paused);
    } else {
      audio.currentTime = 0; showLine();
    }
  }
  function goNext() {
    if (done) { load(0, true); return; }
    if (idx < TRACKS.length - 1) { load(idx + 1, true); }
  }
  document.getElementById('btn-play').addEventListener('click', function () {
    if (done) { load(0, true); return; }
    audio.play();
  });
  document.getElementById('btn-pause').addEventListener('click', function () {
    audio.pause();
  });
  document.getElementById('btn-stop').addEventListener('click', function () {
    audio.pause(); load(0, false); hidePlayer();
  });
  document.getElementById('btn-begin').addEventListener('click', goBegin);
  document.getElementById('btn-back').addEventListener('click', function () {
    audio.currentTime = Math.max(0, audio.currentTime - 10); showLine();
  });
  document.getElementById('btn-fwd').addEventListener('click', function () {
    var d = audio.duration;
    if (isFinite(d) && audio.currentTime + 10 >= d) {
      if (idx < TRACKS.length - 1) { load(idx + 1, !audio.paused); }
      else { audio.currentTime = d; }
    } else {
      audio.currentTime = Math.min(d || 0, audio.currentTime + 10);
    }
    showLine();
  });
  document.getElementById('btn-next').addEventListener('click', goNext);
  audio.addEventListener('timeupdate', showLine);
  audio.addEventListener('loadedmetadata', showLine);
  audio.addEventListener('ended', function () {
    if (idx < TRACKS.length - 1) { load(idx + 1, true); }
    else { done = true; showLine(); hidePlayer(); }
  });
  // The pop-up's door (2026-11-10): the page's own listen lines.
  // A tap on a story's "Listen to this story" line starts the
  // player at that story and pops the bar up, instead of opening
  // the recording in a new window. The wiring waits for the whole
  // page: this script stands above the stories, so at its first
  // run the listen lines below it are not in the page yet.
  function wireListenLinks() {
    TRACKS.forEach(function (track, i) {
      var links = document.querySelectorAll('a');
      for (var k = 0; k < links.length; k++) {
        if (links[k].getAttribute('href') === track.href ||
            links[k].href === track.href) {
          links[k].addEventListener('click', function (e) {
            e.preventDefault();
            showPlayer();
            load(i, true);
          });
        }
      }
    });
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', wireListenLinks);
  } else {
    wireListenLinks();
  }
  if ('mediaSession' in navigator) {
    try {
      navigator.mediaSession.setActionHandler('nexttrack', goNext);
      navigator.mediaSession.setActionHandler('previoustrack', goBegin);
    } catch (e) { /* older browser: buttons still work */ }
  }
  load(0, false);
})();
"""

LISTEN_RE = re.compile(
    r'<a href="(https://(?:claypnw\.github\.io/morning-scroll|'
    r'morning-scroll-53x\.pages\.dev)/audio/'
    r'[^"]+\.mp3)"[^>]*>Listen to this story</a>')
HEADING_RE = re.compile(r'<h[123][^>]*>(.*?)</h[123]>', re.S)


# --- The maps corner (the admin's order, 2026-11-11) ------------------
# A standing link to the World of Nirn atlas — the maps ChatGPT
# keeps for Mogollon's Hearth — floated in the masthead's right
# flank on page one: upper right, under the nameplate, clear of
# the weather box below. Styled as one of the paper's own small
# bordered pieces (the listen lines' border and ground). The block
# is set right after the nameplate, so the dedication, motto, and
# publisher lines — all short and centered — flow beside it and
# the box stands inside the masthead, above its double rule.
MAPS_URL = "https://claypnw.github.io/mogollon-s-hearth-build-page/maps/"

MAPS_CORNER = (
    '\n  <div class="mapscorner">'
    f'<a href="{MAPS_URL}">World of Nirn &mdash; the maps</a></div>')

MAPS_SHEET = """
<style>
/* The maps corner (2026-11-11): the standing atlas link in the
   masthead's right flank. The box is sized to stand inside the
   masthead, beside the dedication lines and above the double
   rule; on a narrow screen it narrows with the sheet. */
.mapscorner { float: right; width: 1.55in; margin: 1px 0 2px 10px;
  border: 1.5px solid #7a5c2e; border-radius: 6px; background: #e7d3a3;
  padding: 4px 6px 5px; text-align: center; }
.mapscorner a { display: block; color: #3a2a12; text-decoration: none;
  font-size: 10pt; font-weight: bold; line-height: 1.25; }
@media (max-width: 700px) {
  .mapscorner { width: 1.3in; }
  .mapscorner a { font-size: 9pt; }
}
</style>
"""


def _btn(btn_id, icon, word):
    return (f'    <button class="wp-btn" id="{btn_id}" type="button">'
            f'<span class="sym">{icon}</span>'
            f'<span class="word">{word}</span></button>\n')


def scroll_tracks(page):
    """The edition's tracks from the page's own listen lines, in page
    order; each track's title is its part's nearest heading above the
    line. A listen line stands only for a part whose recording stands
    (the paper's listen gate), so every track here is a live one."""
    tracks = []
    for m in LISTEN_RE.finditer(page):
        heads = HEADING_RE.findall(page[:m.start()])
        title = ""
        if heads:
            title = re.sub(r"<[^>]+>", "", heads[-1])
            title = " ".join(html.unescape(title).split())
        tracks.append({"title": title or "Story", "href": m.group(1)})
    return tracks


def scroll_player_block(tracks):
    script = PLAYER_JS_TEMPLATE.replace(
        "__PLAYLIST__", json.dumps(tracks, indent=2))
    first_line = (f'Story 1 of {len(tracks)} \u2014 '
                  f'{html.escape(tracks[0]["title"])}')
    return (
        '\n  <div class="listen whole-player" id="scroll-player">\n'
        '    <div class="wp-bar">\n'
        + _btn('btn-begin', ICON_BEGIN, 'Start of story or story before')
        + _btn('btn-back', ICON_BACK, 'Back 10 seconds')
        + _btn('btn-play', ICON_PLAY, 'Play')
        + _btn('btn-pause', ICON_PAUSE, 'Pause')
        + _btn('btn-fwd', ICON_FWD, 'Forward 10 seconds')
        + _btn('btn-next', ICON_NEXT, 'Next story')
        + _btn('btn-stop', ICON_STOP, 'Stop')
        + '    </div>\n'
        f'    <p id="now-playing">{first_line}</p>\n'
        '    <p class="wp-time" id="time-line">0:00 of 0:00</p>\n'
        '    <audio id="edition-audio" preload="metadata"></audio>\n'
        f'<script>\n{script}</script>\n'
        '  </div>')


def main():
    global _STEP
    parser = argparse.ArgumentParser(
        description="Build one edition's web page (the reading road).")
    parser.add_argument("date", help="Edition date, YYYY-MM-DD")
    parser.add_argument("--json", default=None,
                        help="Edition JSON (default: editions/DATE/edition.json)")
    parser.add_argument("--out-dir", default=None,
                        help="Where the page and its pictures are written "
                             "(default: publish-upload/)")
    args = parser.parse_args()
    date_str = args.date

    _STEP = "read edition JSON"
    json_path = (Path(args.json).expanduser() if args.json
                 else ROOT / "editions" / date_str / "edition.json")
    if not json_path.is_file():
        fail(f"missing edition JSON {json_path}", kind="foreseen")
    try:
        d = json.loads(json_path.read_text(encoding="utf-8"))
    except Exception as exc:
        fail(f"edition JSON {json_path} did not read: {exc}", kind="foreseen")
    if d.get("date") != date_str:
        fail(f"edition JSON date {d.get('date')!r} does not match {date_str!r}")
    out_dir = (Path(args.out_dir).expanduser() if args.out_dir
               else ROOT / "publish-upload")
    print(f"input: {json_path}")

    _STEP = "render the edition page"
    build_paper.WEB_MODE = True
    build_paper.WEB_IMAGES.clear()
    try:
        page = build_paper.render_page(d)
    except SystemExit:
        raise
    except Exception as exc:
        fail(f"the edition page did not render: {exc}", kind="foreseen")

    _STEP = "screen sheet"
    if '<meta charset="utf-8">' not in page or "</head>" not in page:
        fail("the rendered page lacks the anchors the screen sheet "
             "attaches to (charset line / </head>)")
    page = page.replace(
        '<meta charset="utf-8">',
        '<meta charset="utf-8">\n<meta name="viewport" '
        'content="width=device-width, initial-scale=1">', 1)
    page = page.replace("</head>", SCREEN_SHEET + "</head>", 1)

    # The story player (2026-11-10): the edition's listen lines, in
    # page order, become the player's track list. Its block is set
    # under the dateline but stands hidden — the Scroll's pop-up
    # form: it shows only while a guest is listening, floating at
    # the top right of the screen (see PLAYER_SHEET). Fewer than
    # two tracks: no player, and the per-part listen lines carry
    # the edition.
    _STEP = "story player"
    tracks = scroll_tracks(page)
    if len(tracks) >= 2:
        anchor = re.search(r'<div class="dateline">.*?</div>', page, re.S)
        if not anchor or '<div' in anchor.group(0)[len('<div class="dateline">'):]:
            fail("the rendered page lacks the dateline the story "
                 "player attaches under")
        page = (page[:anchor.end()] + scroll_player_block(tracks)
                + page[anchor.end():])
        page = page.replace("</head>", PLAYER_SHEET + "</head>", 1)
        print(f"story player: {len(tracks)} tracks")
    else:
        print(f"story player: none ({len(tracks)} track(s) — the "
              f"per-part listen lines carry the edition)")

    # The maps corner (2026-11-11, the admin's order): the standing
    # atlas link, set into the masthead's right flank — the block
    # goes in right after the nameplate, before the dedication
    # line, so it floats beside the dedication, motto, and
    # publisher lines on page one. Its sheet rides with the page.
    _STEP = "maps corner"
    dedication = '<p class="dedication">'
    if page.count(dedication) != 1:
        fail("the rendered page lacks the dedication line the maps "
             "corner attaches above")
    page = page.replace(dedication, MAPS_CORNER + "\n  " + dedication, 1)
    page = page.replace("</head>", MAPS_SHEET + "</head>", 1)
    print("maps corner: standing link set (World of Nirn — the maps)")

    # Guest-tablet checker (2026-10-31): the paper's login-walled links
    # are marked at build time in build_paper (_mark_login_links). This
    # one script line, set before the closing body tag, loads the checker
    # that reads the guest tablet's setup mark and turns marked links
    # into plain words on that tablet only; everywhere else it changes
    # nothing. The checker file stands on the Scroll's own site, beside
    # the edition pages.
    _STEP = "guest-tablet checker"
    if "</body>" not in page:
        fail("the rendered page lacks the </body> the guest-tablet "
             "checker script attaches to")
    page = page.replace(
        "</body>",
        '<script src="guest-tablet-check.js"></script>\n</body>', 1)

    _STEP = "write the page and its pictures"
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for name, src in sorted(build_paper.WEB_IMAGES.items()):
        dest = out_dir / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dest)
        written.append(name)
        print(f"WROTE {name} ({dest.stat().st_size} bytes)")
    page_name = f"edition-{date_str}.html"
    page_path = out_dir / page_name
    page_path.write_text(page, encoding="utf-8")
    written.append(page_name)
    print(f"WROTE {page_name} ({page_path.stat().st_size} bytes)")

    listen_count = page.count("Listen to this story")
    print(f"listen links on the page: {listen_count}")
    print(f"edition page built for {date_str}: {len(written)} files")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except BaseException as exc:
        # Catch-all: an error this program did not foresee goes to
        # the one shared error program, then the program stops as it
        # would have — the traceback still prints.
        _report_to_shared_error(_STEP, exc, kind="unforeseen")
        raise
