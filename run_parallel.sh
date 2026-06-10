#!/usr/bin/env bash
# ===========================================================================
# Launch all 3 batches in parallel, wait for all to finish.
# Each batch continues even if a study inside it fails (logs the failure).
# This script waits for ALL batches and prints a final summary.
#
# Usage:
#   chmod +x run_parallel.sh run_batch_A.sh run_batch_B.sh run_batch_C.sh
#   QUICK=1 nohup ./run_parallel.sh &> run_parallel.log &
#
# For full runs:
#   EPISODES=80 PERIODS=300 SEEDS="42,123,256" nohup ./run_parallel.sh &> run_parallel.log &
# ===========================================================================

export PYTHONUNBUFFERED=1
PYTHON="${PYTHON:-$(command -v python3 || command -v python)}"
export PYTHON
export EPISODES="${EPISODES:-80}"
export PERIODS="${PERIODS:-300}"
export SEEDS="${SEEDS:-42}"
export QUICK="${QUICK:-0}"

if [ "${QUICK}" = "1" ]; then
    export EPISODES=50
    export PERIODS=200
fi

echo "============================================================"
echo "  PARALLEL STUDY RUNNER"
echo "  Episodes=$EPISODES  Periods=$PERIODS  Seeds=$SEEDS  Quick=$QUICK"
echo "  Started: $(date)"
echo "============================================================"

DIR="$(cd "$(dirname "$0")" && pwd)"

"$DIR/run_batch_A.sh" &> "$DIR/batch_A.log" &
PID_A=$!
echo "  Batch A started (PID $PID_A): Study 1 + 3 + Core eval"

"$DIR/run_batch_B.sh" &> "$DIR/batch_B.log" &
PID_B=$!
echo "  Batch B started (PID $PID_B): Study 2 + 4 + 5"

"$DIR/run_batch_C.sh" &> "$DIR/batch_C.log" &
PID_C=$!
echo "  Batch C started (PID $PID_C): Study 6"

echo ""
echo "  Monitoring... (Ctrl+C safe, processes continue)"
echo "  Logs: batch_A.log  batch_B.log  batch_C.log"
echo ""

FAIL=0

wait $PID_A
STATUS_A=$?
if [ $STATUS_A -eq 0 ]; then
    echo "  Batch A FINISHED OK  ($(date))"
else
    echo "  *** Batch A FAILED (exit $STATUS_A) — check batch_A.log ***  ($(date))"
    FAIL=1
fi

wait $PID_B
STATUS_B=$?
if [ $STATUS_B -eq 0 ]; then
    echo "  Batch B FINISHED OK  ($(date))"
else
    echo "  *** Batch B FAILED (exit $STATUS_B) — check batch_B.log ***  ($(date))"
    FAIL=1
fi

wait $PID_C
STATUS_C=$?
if [ $STATUS_C -eq 0 ]; then
    echo "  Batch C FINISHED OK  ($(date))"
else
    echo "  *** Batch C FAILED (exit $STATUS_C) — check batch_C.log ***  ($(date))"
    FAIL=1
fi

echo ""
echo "============================================================"
echo "  FINAL SUMMARY"
echo "============================================================"
echo "  Batch A (Study 1+3+Core): $([ $STATUS_A -eq 0 ] && echo 'PASSED' || echo 'FAILED')"
echo "  Batch B (Study 2+4+5):    $([ $STATUS_B -eq 0 ] && echo 'PASSED' || echo 'FAILED')"
echo "  Batch C (Study 6):        $([ $STATUS_C -eq 0 ] && echo 'PASSED' || echo 'FAILED')"
echo ""

if [ $FAIL -eq 0 ]; then
    echo "  ALL BATCHES COMPLETE — results in Test/checkpoints/"
else
    echo "  *** SOME BATCHES FAILED ***"
    echo "  Check failed batch logs for Python tracebacks:"
    echo "    grep -n 'FAILED\|Error\|Traceback' batch_A.log batch_B.log batch_C.log"
fi
echo "  Finished: $(date)"
echo "============================================================"

exit $FAIL
