#!/bin/bash
# Morning Scroll publish chain driver (thin shell over the batch programs).
#
# Usage:
#   run_chain.sh DATE           Build + manifest + bundle check, then stop
#                               at the GATE: the upload itself is the
#                               browser task (runbook Step 6).
#   run_chain.sh DATE --force   Same, forwarding --force to
#                               build_and_manifest.py: a deliberate rebuild
#                               of an already-published date (a rehearsal,
#                               or a corrected edition). The flag may come
#                               before or after the date. The driver itself
#                               records the forced run in the rule log.
#   run_chain.sh --finish DATE [extra verify.py args]
#                               After the browser upload has completed:
#                               verify the live site (checksum compare,
#                               ~15-minute retry span for Pages lag) and
#                               refresh the backup mirror on PASS.
#
# No AI judgment inside; each step is a batch program in this directory.
#
# Rule log (Clay's design, 2026-10-18 — RULE-LOG-DESIGN.md): every run keeps
# a rule log in ~/workspace/batch/rule-logs/ via ~/workspace/batch/rulelog.py.
# Steps: 1 build_and_manifest, 2 publish (bundle check), 3 verify live,
# 4 mirror refresh. The run-phase writes steps 1-2 and stops at the gate;
# --finish appends steps 3-4 to the same file and closes the tally. Marks
# are decided by what each program printed: step 3 by verify.py's VERDICT
# line, step 4 by its MIRROR line — never by exit code alone, never by a
# default. Any step at 0, or a tally that does not close, renames the file
# to *-rule-log-FAILED-* — kept until the failure is resolved. A --finish
# retry reopens that FAILED log when steps 1-2 stand at DONE 1, so the
# retry continues the same run's record and can complete it.
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
PYTHON="$ROOT_DIR/venv/bin/python"
RULELOG="python3 $HOME/workspace/batch/rulelog.py"
TOTAL_STEPS=4

if [[ "${1:-}" == "--finish" ]]; then
  DATE="${2:?usage: run_chain.sh --finish DATE}"
  shift 2
  LOG_FILE=$($RULELOG latest scroll "$DATE")
  if [[ "$LOG_FILE" == "NONE" ]]; then
    LOG_FILE=$($RULELOG reopen scroll "$DATE")
  fi
  if [[ "$LOG_FILE" == "NONE" ]]; then
    LOG_FILE=$($RULELOG begin scroll "$DATE" $TOTAL_STEPS)
    $RULELOG start --file "$LOG_FILE" 1 build_and_manifest
    $RULELOG fail --file "$LOG_FILE" 1 build_and_manifest "no run-phase rule log found for $DATE"
    $RULELOG start --file "$LOG_FILE" 2 publish_bundle_check
    $RULELOG fail --file "$LOG_FILE" 2 publish_bundle_check "no run-phase rule log found for $DATE"
  fi
  VERIFY_OUT="$(mktemp)"
  $RULELOG start --file "$LOG_FILE" 3 verify_live
  $RULELOG start --file "$LOG_FILE" 4 mirror_refresh
  "$PYTHON" "$SCRIPT_DIR/verify.py" "$DATE" --mirror "$@" | tee "$VERIFY_OUT"
  rc=${PIPESTATUS[0]}
  VERDICT_LINE=$(grep -E '^VERDICT:' "$VERIFY_OUT" | tail -1)
  MIRROR_LINE=$(grep -E '^MIRROR:' "$VERIFY_OUT" | tail -1)
  rm -f "$VERIFY_OUT"
  STEP3_OK=0; STEP4_OK=0
  if [[ "$VERDICT_LINE" == "VERDICT: PASS" ]]; then
    STEP3_OK=1
    $RULELOG ok --file "$LOG_FILE" 3 verify_live "$VERDICT_LINE"
  else
    $RULELOG fail --file "$LOG_FILE" 3 verify_live "${VERDICT_LINE:-no VERDICT line in verify output (verify.py exited $rc)}"
  fi
  if [[ "$MIRROR_LINE" == MIRROR:\ PASS* ]]; then
    STEP4_OK=1
    $RULELOG ok --file "$LOG_FILE" 4 mirror_refresh "$MIRROR_LINE"
  else
    $RULELOG fail --file "$LOG_FILE" 4 mirror_refresh "${MIRROR_LINE:-no MIRROR line in verify output}"
  fi
  if $RULELOG close --file "$LOG_FILE"; then
    echo "CHAIN DONE: $DATE verified live (checksums match the manifest) and the backup mirror is refreshed."
    exit 0
  fi
  echo "CHAIN FAIL: the $DATE run did not complete (see the rule log in ~/workspace/batch/rule-logs/ and the verify log in batch/logs/)."
  if [[ $STEP3_OK -eq 0 ]]; then
    echo "NEXT STEP: wait for GitHub Pages to finish (it can lag 5-15 minutes), then re-run: run_chain.sh --finish $DATE"
    echo "If it still fails, check in the repo that the upload landed on branch main, and re-upload ONLY the files the verify log marks FAIL."
  elif [[ $STEP4_OK -eq 0 ]]; then
    echo "NEXT STEP: the live site verified PASS; only the backup-mirror refresh failed. Re-run: run_chain.sh --finish $DATE"
  else
    echo "NEXT STEP: the live site verified PASS and the mirror refreshed, but the run phase has no completed rule log for $DATE — steps 1-2 stand at zero. Re-run: run_chain.sh $DATE, then run_chain.sh --finish $DATE"
  fi
  exit 1
elif [[ -n "${1:-}" ]]; then
  # Run mode: one DATE plus an optional --force, in either position.
  DATE=""
  FORCE=0
  for arg in "$@"; do
    case "$arg" in
      --force) FORCE=1 ;;
      -*)
        echo "usage: run_chain.sh DATE [--force] | run_chain.sh --finish DATE" >&2
        exit 2
        ;;
      *)
        if [[ -z "$DATE" ]]; then
          DATE="$arg"
        else
          echo "usage: run_chain.sh DATE [--force] | run_chain.sh --finish DATE" >&2
          exit 2
        fi
        ;;
    esac
  done
  if [[ -z "$DATE" ]]; then
    echo "usage: run_chain.sh DATE [--force] | run_chain.sh --finish DATE" >&2
    exit 2
  fi
  LOG_FILE=$($RULELOG begin scroll "$DATE" $TOTAL_STEPS)
  if [[ $FORCE -eq 1 ]]; then
    $RULELOG note --file "$LOG_FILE" "Forced run: --force given to the driver — deliberate rebuild of $DATE; the already-published guard is bypassed on purpose. (Recorded by the driver from its own arguments.)"
  fi
  # Gate item 99: batch record check at the head of the run phase, before step 1 (build).
  if ! "$PYTHON" "$SCRIPT_DIR/chain_gate.py" 99 "$DATE" --rule-log "$LOG_FILE"; then
    $RULELOG note --file "$LOG_FILE" "Gate item 99 STOP: batch record check did not pass; the build did not run."
    $RULELOG close --file "$LOG_FILE" || true
    echo "CHAIN FAIL: gate item 99 stopped the run for $DATE before step 1 (build)."
    exit 1
  fi
  $RULELOG start --file "$LOG_FILE" 1 build_and_manifest
  BUILD_ARGS=("$DATE")
  if [[ $FORCE -eq 1 ]]; then
    BUILD_ARGS+=(--force)
  fi
  BUILD_OUT="$(mktemp)"
  "$PYTHON" "$SCRIPT_DIR/build_and_manifest.py" "${BUILD_ARGS[@]}" 2>&1 | tee "$BUILD_OUT"
  build_rc=${PIPESTATUS[0]}
  if [[ $build_rc -ne 0 ]]; then
    REFUSAL=""
    if [[ $FORCE -eq 1 ]]; then
      REFUSAL=$(grep 'REFUSED:' "$BUILD_OUT" | tail -1)
      if [[ -n "$REFUSAL" ]]; then
        $RULELOG fail --file "$LOG_FILE" 1 build_and_manifest "build_and_manifest.py --force failed for $DATE: $REFUSAL"
      else
        $RULELOG fail --file "$LOG_FILE" 1 build_and_manifest "build_and_manifest.py --force failed for $DATE (see its output above)"
      fi
    else
      $RULELOG fail --file "$LOG_FILE" 1 build_and_manifest "build_and_manifest.py failed for $DATE (see its output above)"
    fi
    rm -f "$BUILD_OUT"
    $RULELOG close --file "$LOG_FILE" || true
    echo "CHAIN FAIL: build/manifest step failed for $DATE."
    if [[ -n "$REFUSAL" ]]; then
      echo "NEXT STEP: the forced rebuild stopped at the archive step — $DATE is already in the archive index, and the chain will not add it twice. For a rehearsal, nothing more is needed. For a real corrected edition, the existing archive entry has to be removed first, as its own deliberate step, then re-run: run_chain.sh $DATE --force"
    fi
    exit 1
  fi
  rm -f "$BUILD_OUT"
  $RULELOG ok --file "$LOG_FILE" 1 build_and_manifest "build_and_manifest.py exit 0; manifest-$DATE.txt written"
  $RULELOG start --file "$LOG_FILE" 2 publish_bundle_check
  # Gate item 106: sign-off check at the head of the publish step, before publish.py runs.
  if ! "$PYTHON" "$SCRIPT_DIR/chain_gate.py" 106 "$DATE" --rule-log "$LOG_FILE"; then
    $RULELOG fail --file "$LOG_FILE" 2 publish_bundle_check "gate item 106 stop: no recorded sign-off for $DATE (batch/logs/sign-off-$DATE.txt)"
    $RULELOG close --file "$LOG_FILE" || true
    echo "CHAIN FAIL: gate item 106 stopped the publish step for $DATE — no recorded sign-off, no publish."
    exit 1
  fi
  if ! "$PYTHON" "$SCRIPT_DIR/publish.py" "$DATE"; then
    $RULELOG fail --file "$LOG_FILE" 2 publish_bundle_check "publish.py bundle check failed for $DATE (see its output above)"
    $RULELOG close --file "$LOG_FILE" || true
    echo "CHAIN FAIL: publish bundle check failed for $DATE."
    exit 1
  fi
  $RULELOG ok --file "$LOG_FILE" 2 publish_bundle_check "publish.py exit 0; bundle matches the manifest, no extras"
  # Gate item 105: publish runbook steps check, right after publish.py succeeds and before the chain declares the gate reached.
  if ! "$PYTHON" "$SCRIPT_DIR/chain_gate.py" 105 "$DATE" --rule-log "$LOG_FILE"; then
    $RULELOG fail --file "$LOG_FILE" 2 publish_bundle_check "gate item 105 stop: publish runbook steps not all done in order for $DATE"
    $RULELOG close --file "$LOG_FILE" || true
    echo "CHAIN FAIL: gate item 105 stopped the run for $DATE after the bundle check passed."
    exit 1
  fi
  $RULELOG note --file "$LOG_FILE" "GATE reached: steps 1-2 done; tally closes at --finish (steps 3-4)."
  echo "RULE LOG OPEN: $LOG_FILE (2 of $TOTAL_STEPS steps; closes at --finish)"
  echo "GATE: upload the files listed above via the browser task (runbook Step 6), then run: run_chain.sh --finish $DATE"
else
  echo "usage: run_chain.sh DATE [--force] | run_chain.sh --finish DATE" >&2
  exit 2
fi
