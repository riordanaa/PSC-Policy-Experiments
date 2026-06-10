# Thesis Chapter 4 — Summary (for cross-session recall)

> Source: `C:\Users\aidan\Downloads\PhDThesis_Zohreh.pdf`, Chapter 4, **pp. 98–132** (Ch5 conclusion pp. 133–138).
> Extract with PyMuPDF (`fitz`); poppler/`pdftoppm` not on PATH. Companion: [thesis-chapter3-summary.md](thesis-chapter3-summary.md).
>
> **Why this matters now:** Ch4 is the **MAB / adaptive reward-weighting** chapter. The 8-arm set (Table 4.1) is exactly the config our research partner ran; our diagnostic run used MAB OFF (arm 1 only), which the thesis shows underperforms. The bandit also *learns to down-weight r5*, confirming our independent finding that the order-stability reward hampers disruption response.

## Title
"Adaptive Reward Shaping to Enhance Deep Reinforcement Learning for Inventory Control in Pharmaceutical Supply Chain"

## Core idea
Builds directly on Ch3. The shaped reward `R = Σ wᵢ·rᵢ` (Eq. 3.9) used **fixed** weights; Ch4 makes the weights **adaptive during training** via a Multi-Armed Bandit, so the agent re-prioritizes reward components as PSC conditions change (normal vs disruption). Motivated by Ch3's sensitivity analysis showing reward-weight tuning is critical.

## Method (4.3)
- **Algorithm: UCB-P** = Upper Confidence Bound with Predefined arms + **Change-Point Detection (CPD)**, based on M-UCB (Cao et al. 2019). Chosen because PSC reward is **non-stationary** (disruptions shift which components matter); UCB-P resets/adapts fast.
- Each **arm** = a fixed weight vector `[w₁..w₆]` over the six reward components. Reward for arm a at time t: `R_{a,t} = Σ w_{a,i}·r_{i,t}` (Eq. 4.1).
- **CPD (Eq. 4.6):** compare mean reward of an arm's most recent `w/2` selections vs the previous `w/2`; if `|diff| > b`, declare a change → reset `τ=t`, `n_a=0` for all arms (discard stale history, restart learning). Applied once an arm has ≥ w selections.
- **Algorithm 3:** round-robin init (`a ← (t−τ) mod ⌈K/γ⌉`), then UCB selection (`mean + sqrt(2 log(t−τ)/n_a)`); run the GRU-A2C episode under the chosen arm; compute reward; run CPD.
- **MAB hyperparameters (long disruption):** window `w=8`, threshold `b=5.0` (empirically tuned), decay `γ=0.5`. GRU-A2C hyperparameters unchanged from Table 3.5.

## The 8 arms (Table 4.1) — IMPORTANT, this is the partner's setup
| Arm | Emphasis | Weights |
|---|---|---|
| 1 | Equal (baseline) | [1,1,1,1,1,1] |
| 2 | r1 ↑ HC backlog balance | [2w,w,w,w,w,w] |
| 3 | r2 ↑ DS order fulfillment | [w,2w,w,w,w,w] |
| 4 | r3 ↑ DS inventory stability | [w,w,2w,w,w,w] |
| 5 | r4 ↑ DS backlog balance | [w,w,w,2w,w,w] |
| 6 | r5 ↑ DS order-action stability | [w,w,w,w,2w,w] |
| 7 | r6 ↑ MN demand alignment | [w,w,w,w,w,2w] |
| 8 | r5 **halved** (less order-stability) | [w,w,w,w,0.5w,w] |

Arm 8 exists explicitly to *de-emphasize r5* so the agent can explore a broader range of ordering policies / be more responsive to supply shocks.

## Results (4.4)
- **MAB reward weights generally OUTPERFORM fixed weights** across all info-sharing scenarios (Tables 4.2 vs 4.3). MAB reduces HC backlog vs fixed.
- **Two DRL DSs with MAB > single DRL DS.** Best cumulative profit: two DRL DSs + MAB + downstream info sharing.
- **Arm-selection findings (Figs 4.5, 4.8, 4.9):** most-selected arms are DS **backlog balance (r4)** and **inventory stability (r3)**; **arm 8 (halve r5) is consistently among the top** — i.e. the bandit *learns to suppress the order-action-stability reward*. Pure r5-emphasis (arm 6) and r2-emphasis (arm 3) are rarely chosen.
- **Phase-dependent re-prioritization (Figs 4.6, 4.10):** during disruption the model up-weights **MN demand alignment (r6, arm 7)** (upstream/full sharing) and DS backlog balance; DS2 raises orders during/after disruption to **compensate** for the disrupted DS1. This phase-adaptive weighting is the whole point.
- Single DRL DS over-orders (picks arm 2, HC backlog) → higher MN backlog, lower profit; multi-DRL + MAB stays balanced.

## Transfer learning (4.4.2)
- MAB reward model **generalizes better than fixed weights**, especially moderate→long disruptions (Table 4.5).
- **Effectiveness is more sensitive to the info-sharing scenario than to disruption length** — recurring thesis conclusion.

## Conclusion (4.5)
MAB (UCB-P) reward-weight adaptation improves adaptability, resilience, and PSC profit (esp. partial/full info sharing), reduces HC backlog vs fixed, and lets agents dynamically prioritize per disruption phase. Future work: scalability / simultaneous MN disruptions, **dynamic arm creation/deletion**, MAB hyperparameter sensitivity, human-in-the-loop, other domains (e.g. food SC).

---

## Chapter 5 (Conclusion) — PSC takeaways only
(Ch5 also covers Ch2 child-wasting/ML — omitted as not PSC-relevant. The PSC parts recap Ch3+Ch4:)
- **GRU-A2C > plain A2C > base-stock** under moderate/long disruptions; dynamic lead-time estimation is key; trust sensitivity 0.025–0.1 is the sweet spot.
- Info-sharing dominates: **downstream sharing** best for HC shortages (trust-based order splitting is a feedback signal); **full sharing + single DRL DS1** gives highest profit; both-DS-DRL under full sharing learn slightly **under-order** policies to avoid violating r6 (MN alignment).
- **Fixed reward weights are sub-optimal → MAB needed.** MAB > fixed across scenarios; full info + MAB = highest profit + best balance; downstream info prevents post-disruption over-ordering; the non-disrupted DS2 learns **compensatory behavior that persists past the disruption**.
- DRL agents "maintain stability **within the constraints of the DRL reward function**" — i.e. behavior is bounded by how the reward is shaped (consistent with our audit: a stability-biased reward yields conservative ordering).

**Connections to our work:** (1) The thesis's headline performance result *requires* the MAB — running fixed equal weights (our diagnostic config) is the thesis's weakest variant, reinforcing [[setup-not-rewards-caused-failure]]. (2) The bandit independently learns to down-weight r5, matching our finding that r5 penalizes the disruption response. See [[thesis-chapter3]], [[fixed-reward-experiment]], [[profit-proxy-not-in-thesis]].
