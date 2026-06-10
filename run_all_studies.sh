#!/usr/bin/env bash
# ===========================================================================
# Master script: run all studies sequentially on a cloud VM.
#
# Usage:
#   chmod +x run_all_studies.sh
#   nohup ./run_all_studies.sh &> run_all.log &
#
# For full results use:
#   EPISODES=100 PERIODS=300 SEEDS="42,123,256" ./run_all_studies.sh
#
# For a quick sanity check:
#   QUICK=1 ./run_all_studies.sh
# ===========================================================================
set -e

EPISODES="${EPISODES:-80}"
PERIODS="${PERIODS:-300}"
SEEDS="${SEEDS:-42}"

if [ "${QUICK}" = "1" ]; then
    EPISODES=50
    PERIODS=200
fi

echo "============================================================"
echo "  RUNNING ALL PAPER STUDIES"
echo "  Episodes=$EPISODES  Periods=$PERIODS  Seeds=$SEEDS"
echo "  Started: $(date)"
echo "============================================================"

cd "$(dirname "$0")/Test"

echo ""
echo ">>> Study 1: GRU vs Dense"
echo "============================================================"
python study_gru_vs_dense.py --episodes "$EPISODES" --periods "$PERIODS" --seeds "$SEEDS"

echo ""
echo ">>> Study 2: State-space sensitivity"
echo "============================================================"
python study_state_space.py --episodes "$EPISODES" --periods "$PERIODS" --seeds "$SEEDS"

echo ""
echo ">>> Study 3: MAB ablation (fixed vs adaptive reward)"
echo "============================================================"
python study_mab_ablation.py --episodes "$EPISODES" --periods "$PERIODS" --seeds "$SEEDS"

echo ""
echo ">>> Study 4: Transfer learning (train on long, fine-tune on short)"
echo "============================================================"
python transfer_learning_runner.py \
    --phase train --scenario long_disruption \
    --episodes "$EPISODES" --periods "$PERIODS" \
    --checkpoint-dir checkpoints/study4_train_long --seed "${SEEDS%%,*}"

python transfer_learning_runner.py \
    --phase finetune --scenario short_disruption \
    --source-checkpoint checkpoints/study4_train_long \
    --episodes $((EPISODES / 3)) --periods "$PERIODS" \
    --checkpoint-dir checkpoints/study4_finetune_short --seed "${SEEDS%%,*}"

python transfer_learning_runner.py \
    --phase train --scenario short_disruption \
    --episodes "$EPISODES" --periods "$PERIODS" \
    --checkpoint-dir checkpoints/study4_scratch_short --seed "${SEEDS%%,*}"

echo ""
echo ">>> Study 5: Information sharing sweep"
echo "============================================================"
python transfer_learning_runner.py \
    --phase sweep --sweep-param info_sharing \
    --episodes "$EPISODES" --periods "$PERIODS" --seed "${SEEDS%%,*}"

echo ""
echo ">>> Study 6: Scalability (2x2x2 vs 4x4x4)"
echo "============================================================"
python study_scalability.py --episodes "$EPISODES" --periods "$PERIODS" --seeds "$SEEDS"

echo ""
echo ">>> Core evaluation: DRL vs baseline (main claim)"
echo "============================================================"
python evaluate_drl.py --episodes "$EPISODES" --periods "$PERIODS"

echo ""
echo "============================================================"
echo "  ALL STUDIES COMPLETE"
echo "  Finished: $(date)"
echo "  Results in Test/checkpoints/"
echo "============================================================"
