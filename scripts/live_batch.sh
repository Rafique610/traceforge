#!/usr/bin/env bash
# Live batch of BugsInPy (or lab) investigations through the real Investigate path, self-checking:
# pauses 15 min on a provider error and stops after 3 tries (no model tokens spent on supervision).
# Usage (from the repo root): bash scripts/live_batch.sh <delay_seconds> "2 3 4 ..."   (fastapi bug numbers)
# Lines starting with ALERT or DONE are the ones worth checking. Logs: runs/validation/bugsinpy/
set -u
DELAY=${1:-3600}
S="$(cd "$(dirname "$0")" && pwd)"
cd "$S/../backend" || exit 2
OUT=../runs/validation/bugsinpy
LEDGER=../runs/beatapi_usage.jsonl
mkdir -p "$OUT"
echo "WAIT starting in ${DELAY}s at $(date -d "+${DELAY} seconds" +%H:%M 2>/dev/null)"
sleep "$DELAY"
echo "case,rep,try,final_state,cause_class,last_reason,outcome,started,ended,calls,max_out_tokens" > "$OUT/summary.csv"

run_one() {  # $1 case, $2 rep, $3 try -> sets REASON
  local c=$1 rep=$2 try=$3 t L N0 st oc calls mx
  t=$(date +%H:%M); N0=$(wc -l < "$LEDGER")
  L=$OUT/bugsinpy-fastapi-$c-r$rep-t$try.log
  PYTHONUNBUFFERED=1 MANIFEST="$S/../datasets/manifests/bugsinpy.json" REAL_MODEL=1 TRACEFORGE_LLM_PROVIDER=beatapi TRACEFORGE_LLM_MODEL=glm-5.3-flash-free \
    timeout 2700 .venv/Scripts/python.exe "$S/live_investigate.py" "bugsinpy-fastapi-$c" > "$L" 2>&1
  st=$(grep -m1 "final state" "$L" | sed 's/final state: //; s/ | cause: /,/')
  REASON=$(grep -o '"reason": "[^"]*"' "$L" | tail -1 | cut -d'"' -f4)
  oc=$(grep -o '"outcome": "[^"]*"' "$L" | tail -1 | cut -d'"' -f4)
  calls=$(( $(wc -l < "$LEDGER") - N0 ))
  mx=0; [ "$calls" -gt 0 ] && mx=$(tail -n "$calls" "$LEDGER" | grep -o '"output_tokens": [0-9]*' | awk '{print $2}' | sort -n | tail -1)
  echo "$c,$rep,$try,${st:-ERROR,},$REASON,$oc,$t,$(date +%H:%M),$calls,$mx" >> "$OUT/summary.csv"
  echo "RUN bugsinpy-fastapi-$c r$rep t$try: ${st:-ERROR} | ${REASON:-ok} | ${oc:-} | calls=$calls max_out=$mx"
}

CASES=${2:-"2 3 4 5 6 7 8 9 10 11 12 13 14 15"}
for rep in 1; do
  for c in $CASES; do
    free_kb=$(df -k /c | tail -1 | awk '{print $4}')
    if [ "$free_kb" -lt 2000000 ]; then echo "ALERT disk C: below 2 GB, stopping"; exit 3; fi
    try=1
    while :; do
      run_one "$c" "$rep" "$try"
      case "$REASON" in
        provider_error*|"")
          if [ -z "$REASON" ] && grep -q "final state" "$OUT/bugsinpy-fastapi-$c-r$rep-t$try.log"; then break; fi
          if [ "$try" -ge 3 ]; then echo "ALERT provider still failing after 3 tries on bugsinpy-fastapi-$c (${REASON:-no result}); stopping"; exit 4; fi
          echo "PAUSE provider problem (${REASON:-no result}); waiting 15 min before retrying bugsinpy-fastapi-$c"
          sleep 900; try=$((try + 1)) ;;
        *) break ;;
      esac
    done
  done
done
echo "DONE all runs finished; summary in $OUT/summary.csv"
