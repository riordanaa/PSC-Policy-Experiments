#!/usr/bin/env bash
# Batch C: Study 6 (Scalability 2x2x2 vs 4x4x4)

EPISODES="${EPISODES:-80}"
PERIODS="${PERIODS:-300}"
SEEDS="${SEEDS:-42}"

if [ "${QUICK}" = "1" ]; then
    EPISODES=50
    PERIODS=200
fi

cd "$(dirname "$0")/Test"
PY="${PYTHON:-$(command -v python3 || command -v python)}"
FAIL=0

echo "[Batch C] Study 6: Scalability  ($(date))"
if $PY study_scalability.py --episodes "$EPISODES" --periods "$PERIODS" --seeds "$SEEDS"; then
    echo "[Batch C] Study 6 PASSED  ($(date))"
else
    echo "[Batch C] *** Study 6 FAILED (exit $?) ***  ($(date))"
    FAIL=1
fi

if [ $FAIL -eq 0 ]; then
    echo "[Batch C] ALL PASSED  ($(date))"
else
    echo "[Batch C] *** SOME STUDIES FAILED ***  ($(date))"
fi
exit $FAIL
