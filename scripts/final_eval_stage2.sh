#!/bin/bash
# FINAL EVALUATION (RC1, frozen test-split selection, AxForge glm-5.3-flash): ONE replicate stage per invocation.
# Usage: bash scripts/final_eval.sh K [CASES_FILE]   (K = replicate index 0, 1, 2; CASES_FILE = JSON with a "cases" subset of the
# frozen selection, e.g. results/final/selection-rep2.json for the reduced replicate 2)
# Order: L0 (diagnosis + patch loop, F0) -> G0 -> freeze the two diagnosis runs -> L1 and G1 (patch stage from the
# SHARED diagnosis of L0/G0, feedback ON). Halts at the first failure (provider error, 429, budget, refusal); never
# retries, loops, or switches provider. Re-run the same stage only as a deliberate next step: finished cases are kept.
K=${1:?usage: final_eval.sh REPLICATE_INDEX}
cd "$(dirname "$0")/../backend" || exit 9
PY=.venv/Scripts/python.exe
OUT=../results/final
SEL=../results/final/selection-stage2.json
FPFILE=../results/final/rc1-fingerprint.txt
FP=$(cat $FPFILE)
CASES_FILE=${2:-$SEL}
CASES=$($PY -c "import json;print(' '.join(json.load(open('$CASES_FILE'))['cases']))")
N=$(echo $CASES | wc -w)
rem() { $PY -m traceforge.evaluation.usage_report | $PY -c "import json,sys;print(json.load(sys.stdin)['axforge_combined']['remaining_to_ceiling'])"; }
COMMON="--manifest ../datasets/manifests/test.json --split test --case-ids $CASES --provider axforge --model glm-5.3-flash --real --evidence-dir ../runs/evidence --out $OUT --workers 1 --axforge-key 2 --axforge-billing-verified --pipeline v5 --final-rc1 --selection $SEL --rc-fingerprint $FP --replicates 1 --replicate-start $K"
recs() { ls $OUT/$1/records 2>/dev/null | grep -c "\.r$K\.json"; }
stage() {  # cond extra-args...
  C=$1; shift; RID=final-axforge-$C
  R=$(rem); echo "start $RID rep=$K remaining=$R $(date +%H:%M:%S)"
  [ "${R:-0}" -lt 60000 ] && { echo "STOP allowance: remaining $R"; exit 3; }
  $PY -m traceforge.evaluation.runner --condition $C --run-id $RID $COMMON "$@" > ../runs/logs/$RID.stage2.rep$K.log 2>&1
  M=$(recs $RID); echo "  done $RID rep=$K records=$M/$N remaining=$(rem)"
  [ "$M" -lt "$N" ] && { echo "STOP incomplete $RID rep=$K (see ../runs/logs/$RID.stage2.rep$K.log)"; exit 4; }
}
$PY -m traceforge.evaluation.fingerprint_check $FPFILE || { echo "STOP code fingerprint changed"; exit 5; }
stage L0
stage G0
FZ=$OUT/frozen-stage2-rep$K.json
if [ -f $FZ ]; then $PY -m traceforge.evaluation.freeze_manifest verify $FZ || exit 5
else $PY -m traceforge.evaluation.freeze_manifest build --out $FZ --dir $OUT/final-axforge-L0 --dir $OUT/final-axforge-G0 || exit 5; fi
stage L1 --patch-from $OUT/final-axforge-L0 --frozen-manifest $FZ --share-diagnosis
stage G1 --patch-from $OUT/final-axforge-G0 --frozen-manifest $FZ --share-diagnosis
echo "REPLICATE $K DONE remaining=$(rem)"
