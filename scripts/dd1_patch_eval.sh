#!/bin/bash
# dev-d1 Level-1 PATCH stage (F0: no feedback), from the frozen saved diagnoses. L0 then G0 as two separate runs.
# One attempt per invocation: halts at the first failure (provider error, 429, budget); never loops or switches provider.
cd "$(dirname "$0")/../backend" || exit 9
PY=.venv/Scripts/python.exe
OUT=../results/development
FROZEN=../results/development/dd1-l1-frozen-manifest.json
$PY -m traceforge.evaluation.freeze_manifest verify $FROZEN || { echo "STOP frozen diagnosis runs changed"; exit 5; }
CASES="shop_api-096 shop_api-182 shop_api-014 shop_api-067 shop_api-058 shop_api-085"
run() {  # cond
  COND=$1; RID=dev-axforge-$COND-dd1-patch; SRC=$OUT/dev-axforge-$COND-dd1-l1
  REM=$($PY -m traceforge.evaluation.usage_report | grep '"remaining_to_ceiling"' | head -1 | tr -dc '0-9')
  echo "start $RID remaining=$REM $(date +%H:%M:%S)"
  [ "${REM:-0}" -lt 700000 ] && { echo "STOP budget $REM"; exit 3; }
  $PY -m traceforge.evaluation.runner --manifest ../datasets/manifests/dev.json --condition $COND --run-id $RID --split dev --case-ids $CASES --provider axforge --model glm-5.3-flash --real --evidence-dir ../runs/evidence --out $OUT --workers 1 --axforge-billing-verified --pipeline v5 --patch-from $SRC --frozen-manifest $FROZEN > ../runs/logs/$RID.log 2>&1
  N=$(ls $OUT/$RID/records 2>/dev/null | wc -l); echo "  done $RID records=$N/6"
  [ "$N" -lt 6 ] && { echo "STOP incomplete $RID"; exit 4; }
}
run L0
run G0
echo ALLDONE
