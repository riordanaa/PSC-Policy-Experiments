# Thesis Chapter 3 — Summary (for cross-session recall)

> Source: `C:\Users\aidan\Downloads\PhDThesis_Zohreh.pdf`, Chapter 3, **pp. 48–97**
> (Chapter 4 = MAB adaptive reward shaping starts p. 98.)
> The thesis PDF is **not** in the repo. Extract text with PyMuPDF (`fitz`) if needed — `pdftoppm`/poppler is not on PATH, so the Read tool can't render the PDF directly.
>
> **Why this file exists:** Chapter 3 defines reward components r1–r6 (Eqs. 3.10–3.15) that the two reward reports audit (`reward_report.tex` and `Reward_shaping_report-1.pdf`). This summary lets me reason about the thesis intent without re-extracting the PDF every session.

## Title
"A Deep Reinforcement Learning Aided Inventory Control Approach for Managing Drug Shortages: Impact of Information Sharing"

## 3.1 Introduction
- Drug shortages: frequent, costly, >50% of causes unreported.
- Framed as inventory management in a **3-echelon PSC**: Manufacturer (MN) → Distributor (DS) → Health Center (HC) → patients (urgent/non-urgent).
- **DSs are the DRL agents** (most complex mid-echelon decision-makers). MNs/HCs are rule-based.
- Central thesis lever: **information sharing / transparency** improves resilience.

## 3.2 Literature Review
- Drug-shortage causes; value of information sharing (no / partial / full).
- RL primer: value-based, policy-based, actor-critic; A2C derived as on-policy AC w/ advantage.
- DRL-for-inventory studies categorized by info-sharing level (Table 3.1). This work = only one combining GRU-A2C + order **and** allocation + disruptions + non-deterministic lead time + 6-component shaped reward.

## 3.3 Problem Formulation & Methodology (core)
- **3.3.1 Supply chain model.** Agent profit = revenue from allocation − (holding + backlog cost) (Eq. 3.6). Cost weights: **10w backlog, 1w holding, 5w allocation profit.** Lead time estimated **dynamically** from observed delivery rates (Algorithm 1) to dampen bullwhip.
- **3.3.2 POMDP.** Per-echelon observation vectors → global state. Fixed **m-step history window** (m ≈ avg estimated lead time × review period). Continuous actions: order qty (scaled w/ safety-stock buffer, Eq. 3.7) + allocation to HCs (Eq. 3.8).
- **3.3.3 Reward shaping.** `R = Σ wᵢ·rᵢ` (Eq. 3.9). Six components:
  - **r1 (Eq. 3.10)** HC backlog balance = ω₁·r4,HC1 + ω₂·r4,HC2 (delegates to r4 form per HC).
  - **r2 (Eq. 3.11)** order fulfillment within tolerance ε: `sign(ε − |Σ AO − Σ D|)`.
  - **r3 (Eq. 3.12)** DS inventory within ±2σ of up-to-level.
  - **r4 (Eq. 3.13)** DS backlog balance — **the algebraically broken one.** Printed term `|sign(ΔB_{j+1}−ΔB_j) − sign(ΔB_j−ΔB_{j+1})|` is structurally 2 (or 0), pinning the 2nd sign at −1 ⇒ r4 ∈ {−3,−2,−1}. The PDF report proves the equation itself (not just code) is the bug; code is faithful to the printed eq. Confirmed: p. 70 prints the duplicated/negated sign term exactly as the report quotes.
  - **r5 (Eq. 3.14)** order-action stability `sign(1 − |β₁|)`, β₁ = OLS slope of last m order actions.
  - **r6 (Eq. 3.15)** MN prod/demand alignment: +1 only if **every** window period has MP/D ∈ [L,U], else −1.
- **3.3.4 Improved A2C.** GRU + attention in actor & critic (Algorithm 2, Fig 3.6). Adaptive LR `α·exp(−β_α|δ|)` and exploration `ε·exp(β_ε|δ|)`, both driven by TD error δ.
- **3.3.5 Transfer learning.** Pre-train one disruption regime, fine-tune others.

## 3.4 Computational Study
- **3.4.1 Setup.** 2×2×2 net; **500 episodes × 300 periods, first 60 warm-up, 10 trials.** Hyperparams = **Table 3.5**: GRU width 128, dropout 0.3, actor 2 FC / critic 3 FC @128, Adam, γ=0.95, actor & critic LR 0.01, grad clip 1.0, β_ε=5e-3, β_α=5e-2. MN1 disrupted; HC1 splits by trust, HC2 equally. **Disruption strength 0.95** all durations (Table 3.3). Pre-train 100 episodes under full sharing as initial solution.
- **3.4.2** Optimal history m scales with disruption length (**m=8 for long**); trust sensitivity δ best 0.025–0.1.
- **3.4.3** GRU-A2C vs base stock (Table 3.9): base stock slightly better with no disruption; **GRU-A2C wins under moderate/long disruptions**, lower & more stable lead times.
- **3.4.4** Transfer learning: long-disruption training generalizes to long; multi-short improves responsiveness.
- **3.4.5 Information sharing (headline).** No/partial sharing → **two DRL DSs beat single DRL DS**; full sharing → **single DRL DS1 gives highest PSC profit.** Text attributes behaviors to specific reward components: **r3** lets inventory drift within ±2σ enabling over-order; adding **r6** (upstream/full) suppresses over-ordering.

## 3.5 Sensitivity Analysis
- ↑ weight of **r1** → less HC backlog but costly over-ordering (Fig 3.22).
- ↑ weight of **r6** → DS1 more conservative, shifts orders to DS2 (Fig 3.23).
- Motivates **Chapter 4's MAB** adaptive reward weighting.

## 3.6 Conclusion
- Multi-DRL beats single-DRL on profit in most sharing scenarios; single-DRL DS1 wins under full sharing.
- Reward-weight tuning is critical → Chapter 4 MAB.
- Future work: real-world data, simultaneous multi-agent disruptions, human-in-the-loop, meta-learning, regulatory teacher policies.

## ⚠️ Key tension with the reward audit (most important discussion point)
Sections 3.4.5 and 3.5 credit **r1, r3, r6** with actively steering policy ("r3 permits inventory to fluctuate… granting flexibility," "adding r6 prevents the over-order policy"). But the audit reports show **r3 and r6 are saturated constants** and **r1/r4 are stuck in {−3,−2,−1}**. So the thesis's behavioral narrative conflicts with the empirical finding that these components emit near-constant signal. This is the central thing to raise with Zohreh.

## Related files in repo
- `reward_report.tex` — first reward diagnostic (frames r1/r4 as a code bug).
- `Reward_shaping_report-1.pdf` (in Downloads) — polished audit; correctly reframes r1/r4 as a **thesis Eq. 3.13** flaw, adds robustness check (3,000 samples / 10 seeds) + MAB down-selection prediction.
- `r5_test_results/r5_findings.md` — narrow r5-only findings (header text "200 episodes / 5 seeds" is stale; real run = 500 episodes / 10 seeds).
- `run_r5_diagnostic.py` — the experiment driver (`apply_config_overrides()` = MAB off, proxy off, 0.95 disruption, full info sharing).
- `documentation/drl-and-reward.md` — repo's own reward deep-dive.
