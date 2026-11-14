import pathlib, re, sys
src = pathlib.Path.home()/"workspace/stewards-ledger/editions/stewards-ledger-2026-11-10.html"
out = pathlib.Path.home()/"workspace/stewards-ledger/editions/stewards-ledger-2026-11-11.html"
html = src.read_text()

def rep(old, new, required=True):
    global html
    if old not in html:
        if required: raise SystemExit(f"MISSING: {old[:120]}")
        return
    html = html.replace(old, new, 1)

rep("<title>The Steward's Ledger — Edition 30 — November 10, 2026</title>",
    "<title>The Steward's Ledger — Edition 31 — November 11, 2026</title>")
rep('<div class="pubdate">Published: November 10, 2026</div>',
    '<div class="pubdate">Published: November 11, 2026</div>')
rep('Edition 30 — Tuesday, November 10, 2026<br/>Published: November 10, 2026',
    'Edition 31 — Wednesday, November 11, 2026<br/>Published: November 11, 2026')

# Edition note: replace whole block
note_new = """<div class="edition-note">
    <b>Today in the Ledger:</b> Day-after check: the Payson Town Council held its regular meeting yesterday, Tuesday, November 10, 2026, at 4:00 PM, in the Town Council Chambers, Town Hall, 303 N Beeline Hwy, Payson, AZ 85541. In today's check (November 11), the town's Granicus listing carries the November 10 meeting as its newest archived meeting, with its agenda posted and a video of 53 minutes; no minutes for the November 10 meeting are listed yet. The full day-after section stands below. Materials update: the minutes of the October 28, 2026 Town Council meeting are now posted in the town's Granicus listing, and the minutes of the October 14, 2026 meeting are also listed there; both are documented in the October 28 section below, including the Town Manager's report recorded in the October 28 minutes. Day-before notice: no meeting of the bodies the Ledger covers is scheduled for tomorrow, Thursday, November 12, 2026, so no new day-before notice is due in this edition — the next day-before notices, for the Tuesday, November 17 county meeting and the Thursday, November 19 meetings, fall due in the November 16 and November 18 editions. No other new materials were found today (November 11): the October 5 Planning &amp; Zoning Commission meeting still carries its agenda only, with no minutes, and its upcoming listing still shows Monday, December 7, 2026 only; the final approved minutes of the October 6 Payson Board of Adjustment meeting are not yet posted (its draft minutes stand as documented); and no recording, minutes, or follow-up post has appeared for the October 22 Payson Police Department Community Update Meeting. The county's meeting system still lists the November 3 regular meeting as its newest past meeting and shows no upcoming events. The Houston Mesa Fire District agendas page is unchanged, no Water Wheel Fire &amp; Medical District minutes newer than June 25, 2026 were found, and the Tonto National Forest projects page showed no new Payson-area public meeting or comment period. All sections carry forward with their own last-update dates, except the November 10 and October 28 Town Council sections, the watching list, and the upcoming list, which update today.</div>"""
html = re.sub(r'<div class="edition-note">.*?</div>', note_new, html, count=1, flags=re.S)

# Global check-date updates in carried sections
html = html.replace("In today's check (November 10)", "In today's check (November 11)")
html = html.replace("in today's check (November 10)", "in today's check (November 11)")
html = html.replace("today's follow-up check (November 10)", "today's follow-up check (November 11)")
html = html.replace("re-checked today (November 10)", "re-checked today (November 11)")
html = html.replace("(November 10), the CrimeWatch page was re-opened", "(November 11), the CrimeWatch page was re-opened")
html = html.replace("no follow-up post, recording, or minutes for the October 22 meeting had been published there.", "no follow-up post, recording, or minutes for the October 22 meeting had been published there.")

# --- October 28 section updates ---
rep('<div class="meta">Payson Town Council — Wednesday, October 28, 2026, 4:00 PM · Town Council Chambers, Town Hall, 303 N Beeline Hwy, Payson, AZ 85541</div>\n    <div class="secupdate">Last update: October 29, 2026</div>',
    '<div class="meta">Payson Town Council — Wednesday, October 28, 2026, 4:00 PM · Town Council Chambers, Town Hall, 303 N Beeline Hwy, Payson, AZ 85541</div>\n    <div class="secupdate">Last update: November 11, 2026</div>')

old_oct28_p1_start = "<p><b>Day-after check.</b> The Payson Town Council held its regular meeting on Wednesday, October 28, 2026"
# Replace the first paragraph of Oct28 section via regex up to its closing </p> after the YouTube sentence
pattern = re.compile(r"<p><b>Day-after check\.</b> The Payson Town Council held its regular meeting on Wednesday, October 28, 2026.*?No written transcript of the meeting was posted in today's check\.</p>", re.S)
new_oct28 = """<p><b>Materials update — minutes now posted.</b> The Payson Town Council held its regular meeting on Wednesday, October 28, 2026, at 4:00 PM, in the Town Council Chambers, Town Hall, 303 N Beeline Hwy, Payson, AZ 85541. In today's check (November 11), the town's Granicus listing carries the October 28 meeting with its agenda posted, a video of 2 hours, 1 minute, and its minutes now posted; the minutes of the October 14, 2026 meeting are also listed in Granicus. No written transcript of the October 28 meeting was posted. On the Town's official YouTube channel, two recordings titled "Town Council Proclamations 10.28.26" are posted: one of 2 hours, 1 minute, 32 seconds, matching the Granicus video's length, and one of 9 minutes, 16 seconds.</p>
    <p>From the posted minutes: Mayor Stephen Otto called the meeting to order at approximately 4:00 PM, with all seven Council members present. The consent agenda was approved 7-0, including approval of the regular meeting minutes of September 9, 2026, and October 14, 2026, and the Fiscal Year 2026-2027 Pension Funding Policy. Town Manager Darren Coldwell reported on the sale of bonds to pay outstanding PSPRS debt; he also reported on the fall employee potluck and pumpkin contest and recognized Code Enforcement Officer Tiffany Brown-Cocroft as Employee of the Year. The second public hearing on Ordinance No. 2026-109 (Item F.1) was postponed to a later date, 6-1, after an executive session under Item H.4. The first public hearing on Ordinance No. 2026-110 (Item F.2) took no action, as it was the first hearing. The Waste Collection agreement for Fiscal Year 2027 (Item H.1) was awarded to Waste Management of Arizona in the amount of $63,827.30 per year, 7-0. Item H.2 was removed from the agenda at the Town Manager's request, to be addressed at a future meeting. On Item H.3, the Council reached consensus that no changes to the emergency clause policy were necessary. On Item H.4, the Town Attorney noted that no action was needed. Mayor Otto adjourned the meeting at approximately 5:47 PM.</p>"""
html2, n = pattern.subn(new_oct28, html, count=1)
if n != 1: raise SystemExit("Oct28 paragraph pattern not found")
html = html2

# Oct28 docs: minutes lines
rep('<span class="missing">Minutes (October 28): not yet published.</span><br/>',
    '<span class="have">Minutes (October 28):</span> <a href="https://payson.granicus.com/MinutesViewer.php?view_id=17&amp;clip_id=2883">Minutes for Payson Town Council - Regular - October 28, 2026 (Granicus)</a><br/>')
rep('<span class="missing">Minutes (October 14): not yet listed</span> in the Granicus listing in today\'s check (November 11); a minutes document for that meeting was included in the October 28 agenda packet for approval (see above).',
    '<span class="have">Minutes (October 14):</span> <a href="https://payson.granicus.com/MinutesViewer.php?view_id=17&amp;clip_id=2882">Minutes for Payson Town Council - Regular - October 14, 2026 (Granicus)</a>')
# Oct28 second paragraph mentions Oct14 minutes listing - update its opening sentence if present
html = html.replace("In today's check (November 11), the Granicus listing for October 14 still carries the agenda only — no minutes are listed in that meeting's minutes cell. The October 28 agenda packet, under consent Item B.1 above, included a document titled \"Minutes for Payson Town Council - Regular - October 14, 2026.pdf\" for approval at the October 28 meeting.",
                    "The October 28 agenda packet, under consent Item B.1 above, included a document titled \"Minutes for Payson Town Council - Regular - October 14, 2026.pdf\" for approval at the October 28 meeting, and the October 28 minutes record that approval (see above).")
html = html.replace("That next meeting is held today, Tuesday, November 10, 2026, at 4:00 PM, and is documented in its own section below. ", "That meeting was held on Tuesday, November 10, 2026, and its day-after check is documented in its own section below. ")
# Oct28 gap line
html = html.replace('<p class="gap">Next regular meeting: today, Tuesday, November 10, 2026, 4:00 PM, Town Council Chambers (see its own section above). The Ledger will check for the October 28 minutes as they are published.</p>',
                    '<p class="gap">The October 28 minutes are now posted and documented above. The next meeting, held Tuesday, November 10, 2026, is documented in its own section below.</p>')

# --- Replace Nov 10 "Gathers Today" block with day-after block ---
start_marker = '<h3>The Council Gathers Today</h3>'
i = html.find(start_marker)
if i < 0: raise SystemExit("Nov10 block not found")
block_start = html.rfind('<div class="meeting">', 0, i)
# next meeting block after this one is County Nov 3
j = html.find('<h3>The County in Regular Session</h3>')
block_end = html.rfind('<div class="meeting">', 0, j)
new_block = """<div class="meeting">
    <h3>The Council Has Met</h3>
    <div class="meta">Payson Town Council — Tuesday, November 10, 2026, 4:00 PM · Town Council Chambers, Town Hall, 303 N Beeline Hwy, Payson, AZ 85541</div>
    <div class="secupdate">Last update: November 11, 2026</div>
    <p><b>Day-after check.</b> The Payson Town Council held its regular meeting yesterday, Tuesday, November 10, 2026, at 4:00 PM, in the Town Council Chambers, Town Hall, 303 N Beeline Hwy, Payson, AZ 85541. In today's check (November 11), the town's Granicus listing carries the November 10 meeting as its newest archived meeting, with its agenda posted and a video of 53 minutes; no minutes for the November 10 meeting are listed in that listing. A recording titled "Town Council Meeting: November 10, 2026" is posted on YouTube, described there as a recording of the Town Council meeting originally held on November 10, 2026. No written transcript of the meeting was posted in today's check. The day-before notice for this meeting ran in Edition 29 (November 9, 2026), and the meeting-day report ran in Edition 30.</p>
    <p>From the published amended agenda, as displayed in the town's Granicus listing in today's check (November 11), the meeting took up: approval of the meeting minutes for the regular Council meeting of October 28, 2026; Resolution No. 2026-046, authorizing the Town of Payson to participate in the proposed class action settlements in the Aqueous Film-Forming Foams (AFFF) Products Liability Litigation relating to Per- and Polyfluoroalkyl Substances (PFAS) contamination of drinking water — the agenda caption names Amerex Corporation, Archroma U.S., Inc., Carrier Global Corporation, and Nation Ford Chemical Company; approval of a Bridging Agreement between the Town of Payson and RingCentral Telecommunications, using the Sourcewell Cooperative Purchase Agreement, for the Town's Integrated Unified Communications-as-a-Service (UCaaS) Phone System; and a Council Decision Request to authorize Darren Coldwell, Town Manager, to submit the Participation Form for the Town to participate in the Opioid Settlement Agreements releasing all claims against Albertsons (consent agenda, Items B.1 through B.4); a current events presentation by the Town Manager, Mayor, and/or Council Members (Item C); a second public hearing on Ordinance No. 2026-110, amending Payson Town Code Title III (Administration), Chapter 34 (Magistrate Court), Section 34.02(C) (Magistrate Court personnel and manner of appointment) (Item F.1); Resolution No. 2026-045, appointing the Honorable Donald Garvin as Town Magistrate and authorizing the Town Manager to execute a Professional Services Agreement with him to provide Magistrate Services (Item F.2); Resolution No. 2026-047, approving a Memorandum of Understanding between the Town of Payson and the Payson Lions Club for the donation and delivery of a concession stand at Rumsey Park (Item F.3); Resolution No. 2026-048, approving Amendment No. One to the Intergovernmental Agreement (ADOT CAR No. IGA 25-0011438-I) between the Town of Payson and the State of Arizona, Department of Transportation, for scoping a wildfire evacuation route crossing the Tonto National Forest and along the south side of the Payson Event Center (Item F.4); a Water Utility Department Update by Water Utility Director Tanner Henry, added to the agenda on November 9, 2026, at 1:35 p.m. (Item H.1); and approval of the 2027 Regular Council Meeting Schedule, requested by Tracie Bailey, Town Clerk (Item H.2). The agenda as displayed states that Items H.3 through H.6 — appointments to fill vacancies on the Town boards and commissions, including the Board of Adjustment, the Building Advisory Board, and the Parks and Recreation Commission — were removed from the agenda on November 5, 2026, at 8:10 a.m. The agenda listed no items under Hearings and Appeals, Unfinished Business, or Miscellaneous. Per the agenda, Pastor Ardo Kario of Payson Church of the Nazarene was to give the invocation.</p>
    <p class="docs">
      <span class="have">Agenda (November 10, amended):</span> <a href="https://payson.granicus.com/AgendaViewer.php?view_id=17&amp;clip_id=2884">November 10 agenda listing (Granicus)</a> · <a href="https://granicus_production_attachments.s3.amazonaws.com/payson/4628c38bbdd81d7d93786ac50ee171ed0.pdf">November 10, 2026 amended agenda (PDF, Granicus)</a><br/>
      <span class="have">Video (November 10, Granicus):</span> <a href="https://payson.granicus.com/player/clip/2884?view_id=17&amp;redirect=true">Payson Town Council - Regular, November 10, 2026 (Granicus player, indexed by agenda item)</a><br/>
      <span class="have">Recording (November 10, YouTube):</span> <a href="https://www.youtube.com/watch?v=Ttuvw4NJr-w">"Town Council Meeting: November 10, 2026" (YouTube)</a><br/>
      <span class="have">Granicus listing:</span> <a href="https://payson.granicus.com/ViewPublisher.php?view_id=17">Payson Town Council meetings listing (Granicus)</a><br/>
      <span class="have">Meetings page:</span> <a href="https://www.paysonaz.gov/government/town-council/town-council-meetings-and-agendas">Town Council Meetings and Agendas — Town of Payson</a><br/>
      <span class="missing">Minutes (November 10): not yet published</span> in today's check (November 11).
    </p>
    <div class="vguide">
      <b>Viewing guide — November 10</b>
      The Granicus recording is indexed by agenda item: its player lists the meeting's items in order — Call to Order, Invocation, Pledge of Allegiance, Roll Call, Call to the Public, Consent Agenda, Current Events Presentation, Ceremonial; Announcements; Presentations; Introductions, Hearings and Appeals, Resolutions and Ordinances (Items F.1 through F.4), Unfinished Business, New Business (Item H.1, Water Utility Department Update, and Item H.2, the 2027 Council meeting schedule), and Miscellaneous — and each item can be selected in the player. No written transcript was posted and the recording carries no clock-time chapter markers in today's check, so a guide with clock times cannot be printed yet. The Ledger will add one — each agenda item mapped to its minute in the recording — when the recording has been indexed with times.
    </div>
    <p class="gap">The Ledger will check for the November 10 minutes as they are published.</p>
  </div>

  """
html = html[:block_start] + new_block + html[block_end:]

# County Nov3 gap / check phrases already updated; ensure its "In today's check" updated (done globally)
# Watching block replace
watch_pattern = re.compile(r'(<h2 class="section">The Ledger Keeps Watching</h2>\s*<div class="meeting">\s*<div class="secupdate">Last update: )November 10, 2026(</div>\s*<p>).*?(</p>)', re.S)
new_watch = r"""\g<1>November 11, 2026\g<2>Still being tracked: the minutes of the November 10 Town Council meeting; any recording, minutes, or follow-up posting for the October 22 Police Department Community Update Meeting; any minutes or action summary for the October 6 Supervisors meeting; the October 5 Planning &amp; Zoning minutes and a timestamped viewing guide for its recording; whether a November Planning &amp; Zoning meeting is scheduled, since the Granicus upcoming listing still shows December 7 only; the final approved minutes of the October 6 Payson Board of Adjustment meeting (its draft minutes record that the motion to approve variance V26-002 failed 3-1); and confirmation of the Water Wheel October meeting. Each will be documented the day it appears.\g<3>"""
html, n = watch_pattern.subn(new_watch, html, count=1)
if n != 1: raise SystemExit("watching pattern not found")

# Upcoming block replace
up_pattern = re.compile(r'(<h2 class="section">Upcoming</h2>\s*<div class="meeting">\s*<div class="secupdate">Last update: )November 10, 2026(</div>).*?(</div>\s*<footer>)', re.S)
new_up = r"""\g<1>November 11, 2026\g<2>
    <p><b>Tuesday, November 17, 10:00 AM</b> — Gila County Board of Supervisors, regular meeting, Gila County Courthouse, Board of Supervisors' Hearing Room, 1400 E Ash St, Globe (televised to Payson, 707 S Colcord Rd), per the Board's 2026 meeting calendar. The day-before notice is due in the November 16 edition.</p>
    <p><b>Thursday, November 19, 3:00 PM</b> — Payson Town Council, special session, Town Council Chambers, Town Hall, 303 N Beeline Hwy, per the Town's boards and commissions schedule page. <a href="https://www.paysonaz.gov/government/town-council/boards-commissions-committees/meetings-and-agendas/-sortn-EDate/-sortd-asc/-folder-90">Boards, Commissions &amp; Committees Meetings and Agendas — Town of Payson (2026 schedule listing)</a> The day-before notice is due in the November 18 edition.</p>
    <p><b>Thursday, November 19, 5:00 PM</b> — Houston Mesa Fire District board, Fire Station in Mesa del Caballo. The day-before notice is due in the November 18 edition.</p>
    <p><b>Tuesday, November 24, 10:00 AM</b> — Gila County Board of Supervisors, work session, per the Board's 2026 meeting calendar.</p>
    <p><b>Monday, December 7, 3:00 PM</b> — Planning &amp; Zoning Commission, regular session, Town Council Chambers. This is the only upcoming meeting shown in the Granicus listing in today's check (November 11); no November meeting is listed there.</p>
  \g<3>"""
html, n = up_pattern.subn(new_up, html, count=1)
if n != 1: raise SystemExit("upcoming pattern not found")

rep("The Steward's Ledger — Edition 30, November 10, 2026.<br/>",
    "The Steward's Ledger — Edition 31, November 11, 2026.<br/>")
rep("Every link above was seen against its official source during research on October 12 – November 10, 2026. Nothing invented.<br/>",
    "Every link above was seen against its official source during research on October 12 – November 11, 2026. Nothing invented.<br/>")

# Banned-name scan placeholder check: ensure no leftover 'November 10, 2026</div>' secupdate for Nov10 block etc.
out.write_text(html)
print("written", out, len(html))
print("Edition 31 count", html.count("Edition 31"))
