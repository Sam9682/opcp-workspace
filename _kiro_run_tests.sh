#!/usr/bin/env bash
# Run each test file separately with a shell timeout so a hanging file
# does not block the whole suite. Collect per-file outcomes.
cd ~/workspace/forgejo/ai-shai-web-interface || exit 1

SUMMARY=_kiro_test_summary.txt
: > "$SUMMARY"

TOTAL_PASS=0
TOTAL_FAIL=0
TOTAL_SKIP=0
TOTAL_ERR=0
HANG_FILES=()
FAIL_FILES=()

for f in tests/test_*.py; do
  # skip files with no test_ functions quickly? just run.
  OUT=$(timeout 120 python3 -m pytest "$f" -p no:cacheprovider -q --no-header 2>&1)
  CODE=$?
  # last summary line
  LINE=$(echo "$OUT" | grep -E '(passed|failed|error|skipped|no tests ran)' | tail -1)
  if [ $CODE -eq 124 ]; then
    echo "HANG(timeout 120s): $f" | tee -a "$SUMMARY"
    HANG_FILES+=("$f")
    continue
  fi
  # parse counts
  P=$(echo "$LINE" | grep -oE '[0-9]+ passed' | grep -oE '[0-9]+'); P=${P:-0}
  Fl=$(echo "$LINE" | grep -oE '[0-9]+ failed' | grep -oE '[0-9]+'); Fl=${Fl:-0}
  S=$(echo "$LINE" | grep -oE '[0-9]+ skipped' | grep -oE '[0-9]+'); S=${S:-0}
  E=$(echo "$LINE" | grep -oE '[0-9]+ error' | grep -oE '[0-9]+'); E=${E:-0}
  TOTAL_PASS=$((TOTAL_PASS+P))
  TOTAL_FAIL=$((TOTAL_FAIL+Fl))
  TOTAL_SKIP=$((TOTAL_SKIP+S))
  TOTAL_ERR=$((TOTAL_ERR+E))
  echo "$(basename $f): $LINE" | tee -a "$SUMMARY"
  if [ "$Fl" != "0" ] || [ "$E" != "0" ]; then
    FAIL_FILES+=("$f")
    echo "----- FAILURES in $f -----" >> "$SUMMARY"
    echo "$OUT" | grep -E 'FAILED|ERROR' >> "$SUMMARY"
  fi
done

echo "" | tee -a "$SUMMARY"
echo "==================== TOTALS ====================" | tee -a "$SUMMARY"
echo "passed=$TOTAL_PASS failed=$TOTAL_FAIL skipped=$TOTAL_SKIP errored=$TOTAL_ERR" | tee -a "$SUMMARY"
echo "hang_files=${HANG_FILES[*]}" | tee -a "$SUMMARY"
echo "fail_files=${FAIL_FILES[*]}" | tee -a "$SUMMARY"
echo "DONE_RUNNER"
