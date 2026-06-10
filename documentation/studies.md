# Studies & experiment runners

The paper/thesis behind this repo is structured as six studies plus a core DRL-vs-baseline evaluation. All scripts live in `Test/`, share a common argument style, and accept `--fast` for a quick low-episode/short-horizon run.

## Common arguments

Most study scripts accept:

- `--episodes N` — training episodes (default varies; `--fast` shrinks it).
- `--periods N` — periods per episode (default 300).
- `--seeds 42,123,256` — comma-separated seeds for multi-seed statistical runs (single-seed scripts use `--seed`).
- `--fast` — smoke-sized run for sanity checking.

Results are written under `Test/checkpoints/` (gitignored) along with config snapshots, seed metadata, and learning curves.

## The studies

| # | Script | What it compares |
|---|--------|------------------|
| Core | `evaluate_drl.py` / `drl_evaluation.py` | DRL distributors vs base-stock baseline on the profit metric during a long disruption. The headline claim. |
| 1 | `study_gru_vs_dense.py` | `DRL_LAYER_TYPE` = GRU vs Dense under identical config; prints a side-by-side table (profit, backlog, learning curve). |
| 2 | `study_state_space.py` | State-space sensitivity — DS observing minimal / partial / full metric subsets (`INFO_SHARING_SCENARIO`). |
| 3 | `study_mab_ablation.py` | Full 8-arm UCB-P bandit reward weighting vs a single fixed equal-weight arm. |
| 4 | `transfer_learning_runner.py --phase train\|finetune` | Train on one disruption scenario, fine-tune on another; compares against training from scratch. |
| 5 | `transfer_learning_runner.py --phase sweep` | Sensitivity sweeps over `--sweep-param` (`info_sharing`, `disruption_length`, topology). |
| 6 | `study_scalability.py` | 2×2×2 vs 4×4×4 topology — does the approach scale. |

## Examples

```bash
# Core evaluation
python Test/evaluate_drl.py --episodes 80 --periods 300

# Study 1, multi-seed
python Test/study_gru_vs_dense.py --episodes 80 --seeds 42,123,256

# Study 4: train long, then fine-tune on short
python Test/transfer_learning_runner.py --phase train --scenario long_disruption \
    --episodes 80 --periods 300 --checkpoint-dir checkpoints/study4_train_long --seed 42
python Test/transfer_learning_runner.py --phase finetune --scenario short_disruption \
    --source-checkpoint checkpoints/study4_train_long \
    --episodes 27 --checkpoint-dir checkpoints/study4_finetune_short --seed 42

# Study 5: info-sharing sweep
python Test/transfer_learning_runner.py --phase sweep --sweep-param info_sharing --episodes 80
```

## Batch runners (bash)

These are Unix shell scripts; on Windows run the underlying `python` commands directly (each script is a short, readable list of them).

| Script | Runs |
|--------|------|
| `run_all_studies.sh` | All studies + core eval, sequentially. Env vars: `EPISODES`, `PERIODS`, `SEEDS`, `QUICK=1`. |
| `run_parallel.sh` | Launches batches A/B/C concurrently. |
| `run_batch_A.sh` | Study 1 + Study 3 + core eval. |
| `run_batch_B.sh` | Study 2 + Study 4 + Study 5. |
| `run_batch_C.sh` | Study 6. |

```bash
EPISODES=80 PERIODS=300 SEEDS="42,123,256" ./run_all_studies.sh
QUICK=1 nohup ./run_parallel.sh &> run_parallel.log &     # parallel, backgrounded
```

`QUICK=1` shrinks to ~50 episodes / 200 periods for a fast pass.

## Reproducibility per run

Each run saves, into its output directory:

- `config_snapshot.json` — every public `config.py` constant at run time.
- `run_seed.json` — the seed actually applied vs the module default.
- `learning_curve.json` — per-episode metrics.
- Model checkpoints (actor/critic weights, normalizer, training state).

To exactly reproduce a run, load its snapshot with `config.load_config_from_snapshot(path)` before building the simulation.
