# archive — historical artifacts moved out of the repo root (2026-07-02)

Nothing here is referenced by live code. Moved during the root cleanup to reduce clutter.

- `training_runs/` — 22 `training_1_<pid>/` directories from the May-2026 RL training era
  (actor/critic checkpoints and run outputs). **Local-only, never git-tracked** (contents were
  always gitignored); moved from the repo root where new RL runs still create fresh
  `training_1_<pid>/` dirs at runtime.
- `r5_test_results_training.log` — training log from the May-2026 r5 reward-diagnostic runs
  (pairs with the committed `r5_test_results*/` output folders at the root).
