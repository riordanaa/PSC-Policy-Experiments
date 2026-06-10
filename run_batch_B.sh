#!/usr/bin/env bash
# Batch B: Study 2 (State-space) + Study 4 (Transfer) + Study 5 (Info sharing)

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

echo "[Batch B] Study 2: State-space sensitivity  ($(date))"
if $PY study_state_space.py --episodes "$EPISODES" --periods "$PERIODS" --seeds "$SEEDS"; then
    echo "[Batch B] Study 2 PASSED  ($(date))"
else
    echo "[Batch B] *** Study 2 FAILED (exit $?) ***  ($(date))"
    FAIL=1
fi

echo "[Batch B] Study 4 Phase 1: Train on long disruption  ($(date))"
if $PY transfer_learning_runner.py \
    --phase train --scenario long_disruption \
    --episodes "$EPISODES" --periods "$PERIODS" \
    --checkpoint-dir checkpoints/study4_train_long --seed "${SEEDS%%,*}"; then
    echo "[Batch B] Study 4 Phase 1 PASSED  ($(date))"
else
    echo "[Batch B] *** Study 4 Phase 1 FAILED (exit $?) ***  ($(date))"
    FAIL=1
fi

echo "[Batch B] Study 4 Phase 2: Fine-tune on short disruption  ($(date))"
if $PY transfer_learning_runner.py \
    --phase finetune --scenario short_disruption \
    --source-checkpoint checkpoints/study4_train_long \
    --episodes $((EPISODES / 3)) --periods "$PERIODS" \
    --checkpoint-dir checkpoints/study4_finetune_short --seed "${SEEDS%%,*}"; then
    echo "[Batch B] Study 4 Phase 2 PASSED  ($(date))"
else
    echo "[Batch B] *** Study 4 Phase 2 FAILED (exit $?) ***  ($(date))"
    FAIL=1
fi

echo "[Batch B] Study 4 Phase 3: Train from scratch on short  ($(date))"
if $PY transfer_learning_runner.py \
    --phase train --scenario short_disruption \
    --episodes "$EPISODES" --periods "$PERIODS" \
    --checkpoint-dir checkpoints/study4_scratch_short --seed "${SEEDS%%,*}"; then
    echo "[Batch B] Study 4 Phase 3 PASSED  ($(date))"
else
    echo "[Batch B] *** Study 4 Phase 3 FAILED (exit $?) ***  ($(date))"
    FAIL=1
fi

echo "[Batch B] Study 5: Info sharing sweep  ($(date))"
if $PY transfer_learning_runner.py \
    --phase sweep --sweep-param info_sharing \
    --episodes "$EPISODES" --periods "$PERIODS" --seed "${SEEDS%%,*}"; then
    echo "[Batch B] Study 5 PASSED  ($(date))"
else
    echo "[Batch B] *** Study 5 FAILED (exit $?) ***  ($(date))"
    FAIL=1
fi

if [ $FAIL -eq 0 ]; then
    echo "[Batch B] ALL PASSED  ($(date))"
else
    echo "[Batch B] *** SOME STUDIES FAILED ***  ($(date))"
fi
exit $FAIL
