# Documentation

Deep-dive docs for the DRL pharmaceutical supply-chain simulator. Start with the root `README.md` for the user-facing overview and `CLAUDE.md` for the working-with-code summary. These files cover the internals.

| File | Covers |
|------|--------|
| [architecture.md](architecture.md) | How the pieces fit: config → simulator engine → decision makers → DRL environment, and the per-period cycle. |
| [configuration.md](configuration.md) | Every section of `config.py`: topology, demand, costs, disruptions, hyperparameters, state schema, helpers. |
| [drl-and-reward.md](drl-and-reward.md) | A2C model (Dense/GRU), the 6 reward components, the UCB-P MAB, adaptive LR/exploration, normalization, checkpoints. |
| [simulator.md](simulator.md) | The `simulator/` package: agents, network, decision makers, demand/lead-time, disruptions. |
| [studies.md](studies.md) | The six paper studies + core evaluation, their scripts, arguments, and the batch runners. |
| [plotting-and-diagnostics.md](plotting-and-diagnostics.md) | The `gen_*`/`generate_plots`/`regen_plots` scripts, the r5 diagnostic, and committed result directories. |

> These docs describe the code as of the current tree. When you change behavior, update the relevant file here too — especially `configuration.md` (constants drift) and `drl-and-reward.md` (reward formulas).
