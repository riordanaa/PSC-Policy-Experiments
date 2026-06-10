# Plotting & diagnostics

Figure-generation scripts (repo root) and the committed result directories. Most read existing eval CSVs and write PNG+PDF — they do **not** re-run training unless noted. All use the non-interactive `matplotlib` `Agg` backend.

## The r5 diagnostic

`run_r5_diagnostic.py` is a self-contained experiment investigating whether reward component **R5** (`sign(1 − |β₁|)`, order-action stability) is a false-positive signal that rewards stability when the agent should be reacting to a disruption.

Setup it forces: MAB **off** (single equal-weight arm), profit proxy **off**, a moderate disruption, ~200 training episodes, then 5 eval episodes with per-period logging. It writes into `r5_test_results/`:

- `experiment_config.json` — the forced config.
- `episode_<seed>_DS<i>_r5log.csv` — per-period log of all 6 rewards **and their input variables** (β₁, order action, backlogs, demand/delivered, inventory band counts, MN production/demand ratio…). This rich schema is produced by the `r5_log` block in `ds_world.step_reward`.
- `r5_statistics.csv`, `r5_findings.md` — analysis + written conclusion.
- `r5_diagnostic.png/.pdf`.

**Finding (see `r5_test_results/r5_findings.md`):** R5 fires +1 ~100% of the time pre/during/post disruption and β₁ barely changes during disruption — R5 does not discriminate good from bad states. This motivates arm 8 in `MAB_REWARD_ARMS` (down-weighting R5).

`regen_plots.py` regenerates the r5 figures from the existing CSVs without re-running the eval (it reuses `run_r5_diagnostic.apply_config_overrides()` and the saved logs).

## Figure generators (read CSVs in `r5_test_results/`)

| Script | Output |
|--------|--------|
| `gen_deadzone.py` | `r5_deadzone.*` — distribution of β₁ vs the ±1 threshold (the "dead zone" where `sign(1−|β₁|)` is positive). |
| `gen_reward_components.py` | `reward_components.*` — 6-panel time series of r1–r6 averaged across eval seeds with ±1 SE bands. |
| `gen_reward_components_single.py` | `reward_components_seed42.*` — same panels for a single seed (shows the discrete {−1,0,+1} jumps). |
| `gen_reward_components_v2.py` | `reward_components_v2.*` — median-across-seeds step plots + per-phase value histograms (pre/during/post). |
| `gen_reward_inputs.py` | `r1_inputs.* … r6_inputs.*` — raw input variables feeding each reward (HC backlog trends; demand vs delivered; inventory band; DS backlog; MN production vs demand ratio). r5 is skipped (covered by the diagnostic). |
| `generate_plots.py` | Reward-comparison plots from a results folder (`results_2_drl_base_5` by default — edit the `output_folders` list). |

Phase boundaries used in these plots match the default disruption: warmup ends 60, disruption 110–157.

## Committed result directories (data, not code)

- `r5_test_results/` and `r5_test_results_dense_partial_05/` — full diagnostic outputs: per-episode CSVs, checkpoints at `ep50…ep500`, training curves, and all the figures above. Treat as experiment artifacts.
- `training_1_<seed>/` — saved actor/critic weights from training runs (`DS 1`, `DS 2`).
- `r5_test_results_training.log` — a captured training log.

Note `.gitignore` excludes `*.csv`, `*.h5`, `*.weights.h5`, `*.xlsx`, and various result/checkpoint paths — so freshly generated outputs are normally untracked. The committed directories above are intentional snapshots of past runs.

## Generating figures cleanly

```bash
# Re-run the r5 experiment end to end (trains; slow)
python run_r5_diagnostic.py

# Regenerate r5 figures from existing CSVs (fast, no training)
python regen_plots.py

# Individual figure sets from existing CSVs
python gen_reward_components.py
python gen_reward_inputs.py
python gen_deadzone.py
```
