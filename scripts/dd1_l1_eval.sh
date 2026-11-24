#!/bin/bash
# dev-d1 Level-1 diagnosis evaluation: L0 then G0 on the six frozen cases, then the controls. One attempt per run; halts on the first failure.
# Same run ids, same binding (AxForge glm-5.3-flash, dev-d1): finished cases are kept, the first failure stops it. One attempt per invocation; never loops.
cd "$(dirname "$0")/../backend" || exit 9
PY=.venv/Scripts/python.exe
OUT=../results/development
run() {  # cond runid cases...
  COND=$1; RID=$2; shift 2
  REM=$($PY -m traceforge.evaluation.usage_report | grep '"remaining_to_ceiling"' | head -1 | tr -dc '0-9')
  echo "start $RID remaining=$REM $(date +%H:%M:%S)"
  [ "${REM:-0}" -lt 400000 ] && { echo "STOP budget $REM"; exit 3; }
  $PY -m traceforge.evaluation.runner --manifest ../datasets/manifests/dev.json --condition $COND --run-id $RID --split dev --case-ids "$@" --provider axforge --model glm-5.3-flash --real --evidence-dir ../runs/evidence --out $OUT --workers 1 --axforge-billing-verified --pipeline v5 --diagnose-only > ../runs/logs/${RID}.log 2>&1
  N=$(ls $OUT/$RID/records 2>/dev/null | wc -l); echo "  done $RID records=$N/$#"
  [ "$N" -lt "$#" ] && { echo "STOP incomplete $RID"; exit 4; }
}
L1="shop_api-096 shop_api-182 shop_api-014 shop_api-067 shop_api-058 shop_api-085"
CT="shop_api-004 shop_api-001"
run L0 dev-axforge-L0-dd1-l1 $L1
run G0 dev-axforge-G0-dd1-l1 $L1
run L0 dev-axforge-L0-dd1-ctrl $CT
run G0 dev-axforge-G0-dd1-ctrl $CT
echo ALLDONE
