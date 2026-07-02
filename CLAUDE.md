# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A Deep Reinforcement Learning framework for ordering/allocation decisions in a multi-echelon pharmaceutical supply chain under disruptions. Distributor agents are controlled by an Advantage Actor-Critic (A2C) model with Multi-Armed Bandit (MAB) adaptive reward shaping; manufacturers and health centers use rule-based policies. Topology is configurable (default 2×2×2 MN×DS×HC, supports N×N×N).

This is a research codebase backing a thesis/paper. Most work happens through experiment scripts in `Test/` and the central `config.py`; there is no installable package or service.

## Commands

All Python commands run from the **project root** unless noted. The shell scripts (`run_*.sh`) are bash and assume a Unix VM; on Windows run the individual `python` commands they contain (per-study commands below work cross-platform). Most scripts also accept `--fast` for a quick low-episode run.

```bash
pip install -r requirements.txt          # install deps (Python 3.10+, TensorFlow 2.11+)

# Tests (unittest, not pytest — though `pytest` discovers them too)
python test_pipeline.py                  # full A2C + env + pipeline suite (root)
python -m unittest simulator.test_agent  # a single simulator test module
python test_pipeline.py TestActorDense   # a single test case

# Quick end-to-end validation (~2 episodes)
python Test/smoke_test.py

# Config-driven training (edit config.py first)
python Test/sim_test_config.py

# DRL vs base-stock baseline (the main claim)
python Test/evaluate_drl.py --episodes 80 --periods 300

# Individual studies (see documentation/studies.md for the full matrix)
python Test/study_gru_vs_dense.py --episodes 80 --periods 300 --seeds 42,123,256
python Test/study_state_space.py --episodes 80 --periods 300
python Test/study_mab_ablation.py --episodes 80 --periods 300
python Test/study_scalability.py --episodes 80 --periods 300
python Test/transfer_learning_runner.py --phase train --scenario long_disruption --episodes 80

# Run everything (bash; QUICK=1 shrinks episodes/periods)
EPISODES=80 PERIODS=300 SEEDS="42,123,256" ./run_all_studies.sh
QUICK=1 nohup ./run_parallel.sh &> run_parallel.log &
```

There is no lint/format config; match surrounding style.

## Architecture (the parts that span files)

**`config.py` is the single source of truth.** Topology, demand, costs, disruptions, DRL hyperparameters, MAB arms, and the state-observation schema are all module-level constants here. Scripts mutate these constants in place to set up an experiment (e.g. `build_simulation()` in `Test/sim_test_config.py` temporarily overrides `TOTAL_EPISODES`/`TOTAL_PERIODS` and restores them). Changing topology means editing `N_MN`/`N_DS`/`N_HC` **and** the explicit `MN_DS_LINKS`/`DS_HC_LINKS` link lists — the `get_ds_connected_*` / `get_num_actions_for_ds` helpers derive everything else (including per-agent action dimension) from those links.

**Two layers, glued by the decision maker.** The `simulator/` package is a generic discrete-time supply-chain engine that knows nothing about RL. `SimulationRunner.next_cycle()` (`simulator/simulation_runner.py`) advances one period: update patients → agents → network → exogenous disruptions → make decisions → apply decisions. Decisions are produced by `PerAgentDecisionMaker`, which dispatches to one decision maker per agent. The RL coupling lives entirely in `DRLDSDecisionMaker` (`simulator/decision_maker.py`): it owns a `DsWorld`, builds the state matrix from the live agent metrics each period, asks the world for actions, and applies them via `allocate_drl`. Manufacturers/health centers use `Simple*DecisionMaker` (base-stock / trust-or-equal split).

**`ds_world.py` is the RL environment + training loop**, one instance per DRL distributor. It wraps an `a2c_Model` (from `model_a2c.py`), maintains the sliding observation window (`DRL_HISTORY_SIZE`, default 8), a `RunningNormalizer` (Welford online normalization, persisted as `*_normalizer.npz`), the `UCBPBandit` for reward-weight selection, and the adaptive learning-rate / exploration logic. The reward is 6 components (HC backlog trend, order fulfillment, inventory stability, DS backlog, action stability, MN alignment) combined with the MAB-selected weight vector from `MAB_REWARD_ARMS`.

**`model_a2c.py`** builds Actor and Critic in either `Dense` or `GRU` mode (set by `DRL_LAYER_TYPE`). Both branch on `layer_type` inside `create_model()`; the GRU path uses a `TimeDistributed` Dense → GRU → FC stack with an attention layer, and a reduced effective LR (`DRL_GRU_LR_FACTOR`). Keras float dtype is forced to `float64` globally.

**State observation is info-sharing dependent.** `config.build_state_config()` returns the per-agent metric dict based on `INFO_SHARING_SCENARIO` (`full` / `partial` / `none`). This changes the state dimension, so checkpoints are only compatible across runs with matching topology **and** info-sharing scenario.

### Gotchas

- **Duplicate/legacy modules exist.** `simulator/disruption.py` (used) vs `simulator/distruption.py` (misspelled legacy); `simulator/lead_time_estimator_new.py` (imported) vs `lead_time_estimator.py`; `psychsim_decision_maker.py` is unused. Check imports before assuming a file is live — prefer the one actually imported in `decision_maker.py` / `drl_simulation_profile_config.py`.
- **`sys.path` hacking is the norm.** Test/script files insert the repo root and `Test/` onto `sys.path` so `import config` and `from sim_test_config import ...` resolve. Keep the same pattern when adding scripts; running from the wrong directory breaks imports.
- Checkpoints (`*.weights.h5`, `*_normalizer.npz`, `training_state.json`) and result CSVs are gitignored. The `r5_test_results*/` dirs are committed experiment outputs/diagnostics — treat as data, not code. Historical `training_1_<pid>/` checkpoint dirs (never tracked) were moved to `archive/training_runs/`; new RL runs still create fresh ones at the root.
- Every study/report folder has a `README.md` index (root `README.md` has the map + ranked study index); `value_decomposition_study/report/README.md` ranks the reports.

## Reproducibility

`config.set_global_seeds(seed)` seeds random/numpy/tensorflow. Experiment runs save `config_snapshot.json`, `run_seed.json`, and per-episode learning curves; `config.load_config_from_snapshot()` restores a prior run's parameters. Default seed is `RANDOM_SEED = 42`.

## Further documentation

See `documentation/` for deep dives: `architecture.md`, `configuration.md`, `drl-and-reward.md`, `studies.md`, `simulator.md`, and `plotting-and-diagnostics.md`.

## Experiment campaigns (2026) — where the evidence lives

### ⭐ Read first: advisor meetings + the capacity report (they set the direction)

The research direction is set by Aidan's advisor/lab/collaborator **meetings**, not inferred from
the code. Their transcripts, summaries, and a catalog live in `meeting_transcripts/` (gitignored,
local-only).
**⚠️ NEVER commit or push `meeting_transcripts/` or `r5_test_results/memory/` (do not `git add -f`
or un-ignore them) — this GitHub repo is PUBLIC and those folders hold confidential
meeting/collaborator content. Keep them local even if told to "commit everything"; for a remote
backup use a PRIVATE repo/gist, never this repo.**
**Start every session by reading `meeting_transcripts/README.md`** (the catalog + read priority),
then the meeting **summaries** (always) and the **full transcripts of the most recent meetings** —
they hold the current research direction and next steps, and supersede the completed
capacity/lead-time/severity thread below.

**READ the capacity report:** `value_decomposition_study/report/robustness_report.pdf` (markdown
twin `value_decomposition_study/MEETING_NOTE.md`) — the rerouting/shed robustness study Ergun
endorsed as the headline (the capacity-conditional misaligned-incentive finding). It is the anchor
the meetings react to; read it before extending the work. The ranked index of all reports (which is
canonical, which superseded) is `value_decomposition_study/report/README.md`.

**Local memory index:** `r5_test_results/memory/MEMORY.md` (gitignored) — the read-first list of
memory files (cross-chat findings, paper summaries, working-style feedback, pending queue). After a
context compaction, read it along with the meeting catalog above.

A series of deterministic policy studies was run on this simulator (no RL). **Do not treat
their findings as settled facts — treat them as claims with evidence, and check status
before citing:** the index is the one-page scorecard in
`consolidated_report/consolidated_findings.pdf` (claims with established/corrected/open/
retracted status codes and a superseded-claims do-not-cite list). Per-claim evidence:
hypothesis cards in `value_decomposition_study/hypotheses/H1–H10.md` (each with method,
numbers, and verdict), `value_decomposition_study/LEDGER.md` (everything tried/kept/
discarded with reasons), `STATUS.md` (chronology incl. discarded batches), and raw
per-period CSVs under each study's `results/` (local, gitignored). Earlier campaigns
(`routing_study/`, `understanding_study/`, the reward-audit reports) are archived audit
trail — several of their headline numbers were later superseded.

**Latest (June 2026): the robustness reports** (advisor-facing, in `value_decomposition_study/report/`;
treat findings as evidence-backed claims, re-verify load-bearing numbers):
- **`robustness_report.pdf` — the rerouting/shed robustness study (the key recent report).**
  Stress-tests the two headline findings — rerouting fixes most of the disruption; the disrupted
  distributor DS1 benefits from "shed" (deprioritizing the trust hospital HC1 so it reroutes to
  the healthy chain) — against healthy-chain (MN2) capacity, trust-sensitivity δ, and precise
  recovery-metric definitions. Headline: shed is a *capacity-conditional misaligned incentive* —
  it helps DS1 (backlog avoidance; the customer returns) but at scarce MN2 capacity becomes a
  system disaster that also harms the rerouting hospital (the rerouted load is amplified on the
  healthy chain, not relocated). Harness: `exp_robustness.py` (gated bit-exact), plus
  `analyze_robustness.py`, `make_robustness_figures.py`; `MEETING_NOTE.md` is the markdown twin,
  `robustness_prereg.md` the pre-registration.
- **`lead_time_severity_report.pdf`** — sweeps lead time and disruption severity over the same
  capacity grid. In a base-stock world longer lead time does NOT worsen cost (the order-up-to
  buffer auto-scales and absorbs the shock; the collapse even mildens), but lost patients jump
  ~2.5× past lead time ~5; the shed/flip phenomenon is *gated by severity* (inert below ~65–80%
  cut, activating at 80%). Harness: `exp_leadtime.py`, `analyze_leadtime.py`.
Both gate on bit-exact reproduction of the prior capacity sweep before any number is reported.
Cross-chat findings summary: `r5_test_results/memory/robustness-leadtime-2026-06.md`.

**Harness conventions these studies established (reuse, don't reinvent):**
- Runner/policies: `routing_study/run_ladder.py` (build/run/log; `hc_factory`/`ds_factory`
  injection, `post_build` wiring), `value_decomposition_study/run_vds.py` (named policies,
  regimes incl. saturated/recurring/none), `gates_vds.py` (verification gates).
- Gates before any reported number: bit-exact baseline reproduction (library AND CLI
  paths — CLI argparse defaults once silently contaminated a whole screen), determinism,
  demand conservation, cross-seed variance.
- Seed discipline: tuning seeds 1–10 (any parameter choice), reporting seeds 11–30 (all
  reported numbers), never mixed. Dual cost accounting (full vs excluding MN-backlog
  bookkeeping) on cost claims.

### Simulator facts found during the studies (code-level, verified — affect ANY experiment)

- `NormalDistPatientModel.__init__` calls `np.random.seed(0)` (`simulator/patient_model.py`),
  defeating `set_global_seeds` — re-seed AFTER constructing the sim or all "multi-seed"
  normal-demand runs are one demand path (study runners do this; gate 6 guards it).
- `config.HC_TRUST_DELTA` is dead — the trust EMA delta is hard-coded at
  `simulator/agent.py` (`HealthCenter.reset`, 0.1). Set `hc.delta` on the agent instead.
- Order decisions with amount ≤ 1 are silently dropped (`simulation_runner.py`,
  `apply_order_decision`) — tiny "probe" orders deadlock policies that bootstrap from
  observed deliveries.
- HC/DS `on_order` entries never time out; deliveries that exceed the on-order ledger
  raise in `receive_delivery` — never delete on-order entries, use accounting-only
  adjustments.
- `SimulationRunner.next_cycle` increments `now` FIRST — after the k-th call the cycle
  just processed time k; read history at `sim.now`, not the loop index.
- Manufacturer production responds to orders up to `num_active_lines × line_capacity`
  (400/period at defaults): orders are the production signal; agent history older than
  `AGENT_HISTORY_PRESERVE_TIME` (60) is purged, so collect metrics inside the period loop.
