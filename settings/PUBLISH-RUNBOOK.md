# Morning Scroll — Daily Publish Runbook

**Purpose:** The exact steps to publish a Morning Scroll edition to the public
archive. Follow this every time. Do not rely on memory. Do not improvise the
order. Clay taps **Publish** once — that is the only authorization needed.

**Canonical site:** https://claypnw.github.io/morning-scroll/
**Repo:** `claypnw/morning-scroll` (branch `main`, files at root)
**Backup mirror:** `~/workspace/BACKUP-github-websites-only/morning-scroll/`
(must match GitHub byte-for-byte after every publish — Clay's rule)

**Standing rules that apply every publish:**
- Clay is never the copy editor. Never ask him to proofread.
- Corrections/rebuilds touch only the current day's edition. Old editions stay as printed.
- Check the current edition's links before publishing; fix dead ones. Old Scrolls are never re-audited.
- Any real person's name or private-looking address in an event: flag to Clay FIRST (tappable options: include as-is / replacement text / drop). Never redact or include silently.
- After two failed attempts at any step: stop, say plainly why it can't be done. No third, fourth, fifth tries.

---

## Step 1 — Stage the edition

```bash
~/workspace/morning-post/venv/bin/python \
  ~/workspace/morning-post/prep_publish.py YYYY-MM-DD
```

This writes to `~/workspace/morning-post/publish-staging/YYYY-MM-DD/`:
- `scroll-YYYY-MM-DD-page-N.png` (alpha PNGs, 1836×2376)
- `edition-meta.json`
- `search-text.txt`
- `payson-morning-scroll-YYYY-MM-DD.pdf` (copy for hosting)

## Step 2 — Prepare upload files

Copy from `publish-staging/YYYY-MM-DD/` to `publish-upload/`, renaming the
page PNGs with a SHA-1 content hash (matches the Oct 4 convention):

```
scroll-YYYY-MM-DD-page-N-r1-<sha1[:8]>.png
```

Compute with: `sha1sum <file> | cut -c1-8`

Upload set for each edition = **7 files**:
1. `index.html` (updated — see Step 3)
2. `scroll-search-index.json` (updated — see Step 4)
3. `payson-morning-scroll-YYYY-MM-DD.pdf`
4. `scroll-YYYY-MM-DD-page-1-r1-<hash>.png`
5. `scroll-YYYY-MM-DD-page-2-r1-<hash>.png`
6. `scroll-YYYY-MM-DD-page-3-r1-<hash>.png`
7. `scroll-YYYY-MM-DD-page-4-r1-<hash>.png`

(Page count varies by edition — adjust the PNG list. Never JPEG: torn edges
need PNG alpha or the fray bakes to white.)

## Step 3 — Update index.html (in publish-upload/)

Make ALL of these edits to the local copy before uploading:

1. **Issue list:** Add the new issue ABOVE the previous newest, with date,
   headline, greeting, and links to the PDF + reader.
2. **Reader section:** Add a new reader block with the 4 page-image filenames
   (exact hashed names from Step 2).
3. **Date slider:** Extend the end date through the new edition date.
4. **JavaScript edition map:** Add the new date entry. **INSPECT the inserted
   entry afterward** — a malformed map entry here broke nothing visibly on
   Oct 5 but was flagged as a risk. Validate with `node -c` or equivalent.
5. **Cache buster:** Bump the search-index fetch query string:
   `scroll-search-index.json?v=YYYYMMDD` (use the new date, no dashes).
   Without this, a stale CDN/browser cache leaves the search box disabled —
   verified the hard way on the Oct 4 publish.

## Step 4 — Update scroll-search-index.json (in publish-upload/)

Prepend the new edition entry. Schema keys (exact):
- `date`, `headline`, `greeting`, `text`, `vol`, `no`

`text` = full edition text from `search-text.txt` in the staging folder.
`vol` = YYMM of the edition date (e.g. `2610`), `no` = zero-padded day
(e.g. `05`).

## Step 5 — Validate locally BEFORE uploading

Open the local `publish-upload/index.html` in a browser and confirm:
- [ ] New edition is newest in the list
- [ ] All page images open (filenames match actual files on disk)
- [ ] PDF link works
- [ ] Search loads (no disabled search box)
- [ ] Searching a distinctive term from the new edition returns it first
- [ ] Date slider spans the full range through the new date

## Step 6 — Push to GitHub

**Auth method (confirmed 2026-10-05):** Browser task with Clay's GitHub session.
The browser stays signed in via saved session state — no sign-in or 2FA was
needed on Oct 5. Spawn a `browser.spawn_task` to
`https://github.com/claypnw/morning-scroll`, pass the 7 files via the `files`
parameter, and have it:
- Upload the 2 updated files via "Add file" > "Upload files" (overwrites
  same-named files — same result as the Edit flow)
- Upload the 5 new files via "Add file" > "Upload files"
- Commit directly to `main` (two commits: one for the updated files, one for
  the new files — or a single commit; either is fine)

**Do NOT ask Clay for credentials.** The saved login works. Asking again
after he called it out on Oct 5 is a trust hit.

Commit message: `Publish <Mon DD, YYYY> edition (Vol. YYMM, No. DD)`

## Step 7 — Verify the live site

After the push completes:
1. Open https://claypnw.github.io/morning-scroll/ in a **signed-out** browser
   session (never relay an unverified "it's live" claim).
2. Confirm the new edition is newest, pages open, search works.
3. Check the reader in **mobile emulation** (Android Chrome has no inline PDF
   viewer — the page-image reader is the phone path; never claim a builder's
   "verified on mobile" without reproducing it yourself).

## Step 8 — Refresh the backup mirror

Copy the final uploaded files to
`~/workspace/BACKUP-github-websites-only/morning-scroll/` so the mirror
matches GitHub byte-for-byte. If index.html or the search index was corrected
after the first backup copy, re-copy. Verify with `diff -r` or checksums.

## Step 9 — Report to Clay

Plain summary with the clickable public link:
https://claypnw.github.io/morning-scroll/

Say what published (edition date, Vol/No, headline). No technical narration.

---

## Failure handling

| Failure | Action |
|---|---|
| prep_publish.py errors | Read the traceback, fix the input (usually edition.json), re-run. |
| Browser task can't sign in | Report to Clay what happened (2FA? locked?). Do NOT ask for his password in chat — use the secure flow only if he offers. |
| GitHub web upload fails mid-way | Check which files landed (repo file list), upload only the missing ones. Never re-upload everything blindly. |
| Live site doesn't show the edition after 5 min | GitHub Pages can lag. Wait, re-check. If still missing after 15 min, inspect the repo — the push may have missed `main`. |
| Second failed attempt at any step | STOP. Tell Clay plainly what can't be done and why. No third attempt. |

---

*Created 2026-10-05 at Clay's request: "do you have steps you perform on a daily
basis — if you don't, create them so you don't have to 'remember'."*
*Auth method confirmed via browser task 2026-10-05 (task completed without
re-asking for credentials).*
