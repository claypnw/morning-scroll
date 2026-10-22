# Rule log design — Clay's design, 2026-10-18

BUILD STATE: Scroll chain built 2026-10-18 — writer ~/workspace/batch/rulelog.py; run_chain.sh rewired (marks from verify.py's VERDICT/MIRROR lines; retry reopens the FAILED log; CHAIN DONE gated on the tally). Tested: pass, forced fail, retry-after-fail, no-run-log paths. Critical review: SEND BACK (5 defects) → fixed → SEND BACK (1 defect) → fixed → PASS (2026-10-18). Live for the Oct 19 run. Remaining batches (ledger, yard, gilded, billing, health, hearth) follow the same pattern next.

Purpose: consistency that does not depend on Dude remembering the rules. Each job run keeps a log of start/finish marks per instruction; a final checksum proves the run covered every instruction; a zero sends the run back to that step.

1. Every instruction in the job is numbered. Each one gets two marks in the log: started, then finished.
2. Started is always 1 when the step begins. Finished is 1 when the step completed and passed its check — 0 when it did not.
3. The log shows the pair for each step — 1,1 or 1,0 — with what the step checked, so any reader can see exactly which step stands at zero.
4. At the end, the checksum: number of instructions = number started = number finished at 1. All three equal, the run is complete. Not equal, it is not.
5. If a retry is needed, there is a retry process for that. Follow the process.
6. Whether a retry means redoing that one step, resuming from it, or restarting the job is judged by what the step does — a step that stands alone is redone alone; a step that depends on earlier ones takes the run back to where it has to start.
7. The report Clay gets quotes the tally: 10 started, 10 completed — or names the step at zero and what was done about it.
8. Log lifespan (Clay, 2026-10-18): a successful run's log is kept a day or two, then dropped — no history is kept. A failed run's log is NOT deleted until the failure is resolved.
9. Names and library (Clay, 2026-10-18): the file is a RULE LOG — one per batch. All rule logs live in ONE library folder: ~/workspace/batch/rule-logs/. Standard name: <batch>-rule-log-<YYYY-MM-DD>-<HHMMSS>.txt — date AND time (run start, Arizona), so every run's file is unique even on repeat runs. A failed run's file: <batch>-rule-log-FAILED-<YYYY-MM-DD>-<HHMMSS>.txt, kept in the library until resolved. Batches: scroll, ledger, yard, gilded, billing, health, hearth.

Notes from the discussion:
- Clay's rule (2026-10-18): never restate another process's rules inside a design — refer to the process, so a change there does not force a change here.
- SCOPE (Clay, 2026-10-18): this design covers ALL batch processing, not just the Scroll. The seven as of 2026-10-18: (1) Morning Scroll chain, (2) Gilded Pages verify, (3) yard sales verify, (4) Steward's Ledger verify, (5) GitHub billing report, (6) health pull, (7) Hearth publish check.
- MORNING LIST (Clay, 2026-10-18 — piece 4 settled): the morning briefing carries the seven as a numbered list, one line each, status in plain words — "completed" or "had an error — needs your attention" — so problems surface that morning and are worked from there.
- Settled (Clay, 2026-10-18): (1) each job's rule sheet is its existing numbered instructions — no new writing; (2) FAILURE STEPS (following the two-attempt rule): 1) the step is marked 1,0 in the log, with what it checked; 2) the step is retried once; 3) retry passes — the run goes on and the checksum can close; 4) retry fails — STOP, no third attempt, the run does not count as complete; 5) Clay is told plainly in the morning list ("had an error — needs your attention") with what can't be done and why — AND with a proposed way to resolve it: the steps that would make the failure go away, as options for him to continue; 6) the failed run's log is kept until the failure is resolved.
