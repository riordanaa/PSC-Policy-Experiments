# Test — RL experiment scripts (original thesis harness)

Entry points for training/evaluating the DRL (A2C + MAB) pipeline: `sim_test_config.py`
(config-driven training), `smoke_test.py` (quick validation), `evaluate_drl.py` (DRL vs
base-stock), `study_*.py` + `transfer_learning_runner.py` (Studies 1–6), and
`drl_simulation_profile_config.py` (builds the simulation from `config.py` — also reused by the
deterministic studies' runners).

See `documentation/studies.md` for the full study matrix and the root `README.md` Quick Start for
commands. Scripts insert the repo root and `Test/` onto `sys.path` — run them from the project
root (or `Test/`), and keep that pattern when adding scripts.
