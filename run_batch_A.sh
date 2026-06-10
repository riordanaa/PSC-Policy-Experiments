#!/usr/bin/env bash
# Batch A: Study 1 (GRU vs Dense) + Study 3 (MAB ablation) + Core eval

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

echo "[Batch A] Study 1: GRU vs Dense  ($(date))"
if $PY study_gru_vs_dense.py --episodes "$EPISODES" --periods "$PERIODS" --seeds "$SEEDS"; then
    echo "[Batch A] Study 1 PASSED  ($(date))"
else
    echo "[Batch A] *** Study 1 FAILED (exit $?) ***  ($(date))"
    FAIL=1
fi

echo "[Batch A] Study 3: MAB ablation  ($(date))"
if $PY study_mab_ablation.py --episodes "$EPISODES" --periods "$PERIODS" --seeds "$SEEDS"; then
    echo "[Batch A] Study 3 PASSED  ($(date))"
else
    echo "[Batch A] *** Study 3 FAILED (exit $?) ***  ($(date))"
    FAIL=1
fi

echo "[Batch A] Core eval: DRL vs baseline  ($(date))"
if $PY evaluate_drl.py --episodes "$EPISODES" --periods "$PERIODS"; then
    echo "[Batch A] Core eval PASSED  ($(date))"
else
    echo "[Batch A] *** Core eval FAILED (exit $?) ***  ($(date))"
    FAIL=1
fi

if [ $FAIL -eq 0 ]; then
    echo "[Batch A] ALL PASSED  ($(date))"
else
    echo "[Batch A] *** SOME STUDIES FAILED ***  ($(date))"
fi
exit $FAIL
