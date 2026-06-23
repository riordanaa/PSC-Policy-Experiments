# Meeting note — robustness of the rerouting / shed findings

Three experiments hitting Ergun's meeting priorities, on the existing simulator. All numbers
from reporting seeds 11–30, slack regime (MN1 disrupted 95% for periods 110–157), urgent0
unless noted. Anchor (MN2 capacity 400/period, δ=0.1) reproduces the existing baseline and shed
results **bit-exactly** before any sweep. Data: `results/robustness/`; pre-registration:
`robustness_prereg.md`; code: `exp_robustness.py` (+ gate), `analyze_robustness.py`.

Topology: MN1→DS1 (disrupted chain), MN2→DS2 (healthy). HC1 = trust-based, HC2 = captive
("equally"). "Shed" = DS1 deprioritizes HC1, pushing it to reroute to the healthy chain.

---

## 1. Capacity stress test — THE decisive result (Ergun's #1 push)

Lowering the healthy manufacturer's (MN2) capacity from abundant (400/period) toward realistic
(no spare). MN2's own nominal demand is ~120; when HC1 reroutes it must serve ~180–240.

| MN2 cap | shed HC1/HC2 (during) | base HC1/HC2 | DS1 own profit Δ | **System** profit Δ | HC1 returns? |
|--------:|:---:|:---:|---:|---:|:---:|
| 400 | 0.92 / 0.78 | 0.90 / 0.72 | **+261,628** | **+637,970** | yes (0.500) |
| 240 | 0.92 / 0.78 | 0.90 / 0.72 | +261,485 | +636,508 | yes (0.500) |
| 180 | 0.87 / 0.73 | 0.88 / 0.71 | +259,655 | **−154,815** | yes (0.500) |
| 140 | 0.75 / 0.67 | 0.78 / 0.65 | +225,078 | **−5,406,275** | yes (0.496) |
| 120 | **0.64** / 0.67 | **0.69** / 0.62 | +180,277 | **−4,088,803** | yes (0.498) |

**On the fill metric** (HC1 = trust/rerouting, HC2 = captive): HC2 is consistently worse than
HC1 — the aggregate hid this — and at cap 120 they invert (HC1 0.64 < HC2 0.67, HC1 having fled
onto the congested chain). "Fill" = demand served *within* the disruption window; under urgent0
the rest is **deferred, not lost** (whole-episode fill = 1.000 for both HCs down to cap 140 — the
cost is *delay*, captured by backlog / recovery-time / the §4 within-W coverage), and only at cap
120 does the system fail to clear by period 300 (episode fill ≈ 0.96). Under urgent20 the urgent
fraction would instead be lost.

**The finding flips at MN2 capacity ≈ 180–240 — exactly where MN2 can no longer cover its own
demand plus HC1's rerouted surge.** Two things happen at once:
- **Rerouting stops fixing it, then back-fires:** as capacity falls HC1's during-fill drops
  0.92→0.87→0.64 (cap 400→180→120); below ~180 shed makes HC1 *worse* than the natural reroute,
  until at the extreme HC1 falls below the captive HC2 — fleeing onto a congested chain no longer helps.
- **Shed becomes a SYSTEM DISASTER while staying privately rational for DS1.** This is the headline.
  DS1's *own* profit stays positive throughout (+262k→+180k — it always sheds its backlog), but
  the *system* delta flips from +638k to **−5.4M**. The per-agent backlog at cap 140 shows why:

  | (during+post backlog cost) | DS1 | DS2 | MN2 | HC1 |
  |---|---:|---:|---:|---:|
  | baseline | 1,288k | 599k | 797k | 455k |
  | shed | **1,057k** ↓ | **3,031k** ↑5× | **3,429k** ↑4× | **1,095k** ↑2× |

  Shed lets DS1 dump HC1's backlog onto a capacity-starved healthy chain, where it explodes 4–5×
  and HC1 itself ends up **worse served**. The disrupted distributor's private incentive to shed
  **diverges from system welfare precisely when the healthy chain lacks spare capacity.**

**Plain English:** "Tell the hospital to go elsewhere" is a clean win *only when the other supplier
has room.* When it doesn't — the real generic-drug regime — the move still helps the disrupted
distributor on paper but wrecks the system and hurts the very hospital that rerouted. Ergun's
instinct that the capacity default was load-bearing is correct, and it converts our earlier
"shed is win-win" into a capacity-conditional, misaligned-incentive finding with direct policy
relevance. Floor guard passed: at cap 120 the no-disruption fill is 1.001, so this is real
congestion, not MN2 failing to meet baseline.

---

## 2. δ (trust-sensitivity) sweep — the Doroudi connection (Ergun's #2)

Our sim hard-codes δ=0.1; Doroudi's instability is at δ=0.5. Swept δ at full MN2 capacity.

| δ | shed DS1 profit Δ | HC1 oscillation (std) | HC1 returns? (late-post share) | trust@250 |
|----:|---:|:---:|:---:|:---:|
| 0.05 | +156,481 | 0.092 | 0.498 | 0.960 |
| 0.10 | +261,628 | 0.178 | 0.500 | 0.982 |
| 0.20 | +329,368 | 0.079 | 0.500 | 0.983 |
| 0.35 | +363,156 | 0.165 | 0.500 | 0.988 |
| 0.50 | +379,644 | 0.134 | 0.500 | 0.990 |

**Honest negative result:** the Doroudi trust-oscillation collapse does **not** reproduce from δ
alone in our simulator. HC1 returns cleanly to 0.500 at *every* δ including 0.5; oscillation shows
no monotonic trend; shed's benefit simply *grows* with δ (faster trust departure → DS1 sheds more
backlog sooner). So **our δ=0.1 results are δ-robust, not a low-δ artifact.**

Why no collapse: Doroudi's instability needs the Theory-of-Mind agents (the disrupted DS actively
*reasoning* about and deprioritizing the oscillating customer) and/or a healthy chain that can't
absorb the reroute. Our rule-based sim has neither in this sweep. Note the capacity sweep (§1)
*does* produce a collapse — but a different one (capacity congestion / backlog dumping), not
trust oscillation. **Untested follow-up:** δ × low-capacity *combined* is the cell where the
Doroudi mechanism is most likely to appear; neither sweep alone triggered it.

---

## 3. Metric definitions (Ergun's #3 — "where the contribution lives")

Proposed precise definitions, demonstrated on the anchor:
- **Disruption-END** (per seed) = `157 + ttr_ds1`, where `ttr_ds1` = first period DS1 backlog
  stays ≤110% of its pre-disruption mean for 5 consecutive periods (already in `metrics.py`).
  Anchor: baseline END ≈ 175 (ttr 18), shed END ≈ 171 (ttr 14) — shed recovers ~4 periods faster.
- **Overshoot / glut** = DS1 inventory area over [END, END+20] above pre-disruption nominal.
  Anchor: baseline 686, shed 1,497 (shed over-orders more into recovery). Paired with the
  shortage side, `aub_ds1_during_post` (baseline 131k, shed 104k).
- **Coverage:** same-period fill (W=0) is reported throughout as `fill_agg`. Exact within-W
  (e.g. 2-week) coverage needs an order **place-time the CSV does not log** — flagged as a
  one-line logging gap to close if exact coverage is wanted; proxy meanwhile =
  cumulative-served(t+W)/cumulative-demand(t).

---

## 4. Two trust-based hospitals (your idea — existing rung-b data, no new runs)

The thesis uses 1-trust + 1-captive; rung-b makes both HCs trust-based (no captive anchor).

| | DS1 episode profit | during fill-dispersion (HC1−HC2) | HC1 oscillation |
|---|---:|---:|---:|
| rung-a (1 trust + 1 captive) | −1,217,927 | +0.181 | 0.068 |
| rung-b (2 trust) | **−845,264** | **−0.000** | 0.060 |

Removing the captive anchor makes the two hospitals symmetric (dispersion collapses to ~0) and
DS1 is actually **better off** (+372k; during backlog cost −193k) — with no captive customer to
keep serving, DS1 sheds backlog from both during the disruption. Same pattern under urgent20
(+403k). So the captive-vs-trust composition of the second hospital is second-order for the
disrupted distributor; if anything, an all-trust downstream is *easier* on it. (Shed *in* the
2-trust world would need a new run — bounded follow-up, not done here.)

---

## 5. The δ × capacity interaction (focused grid — does the flip move with δ? does Doroudi reproduce?)

Swept both stresses together: MN2 cap {400,240,180,140} × δ {0.10,0.20,0.35,0.50}. System
profit Δ (shed−base), $M:

| δ \ MN2 cap | 400 | 240 | 180 | 140 |
|---|---:|---:|---:|---:|
| 0.10 | +0.64 | +0.64 | −0.15 | −5.41 |
| 0.20 | +0.82 | +0.82 | +0.00 | −2.86 |
| 0.35 | +0.90 | +0.89 | −0.31 | −6.37 |
| 0.50 | +0.92 | +0.92 | −0.09 | −4.71 |

Two clean results, both pre-registered bounded-negatives:
- **The flip boundary is δ-invariant.** Shed turns system-harmful between cap 240 and 180 at
  *every* δ. Higher δ only scales the magnitude (above the flip it makes shed *more* beneficial,
  +0.64→+0.92M), it never moves the boundary. **Capacity alone governs the flip; trust
  sensitivity is second-order even in combination.**
- **The Doroudi collapse does not reproduce, even in the worst corner.** HC1's order-share
  returns to ~0.50 in *every* cell (δ=0.5 × cap 140 → 0.496). This bounds the claim: the
  switching-collapse needs the Theory-of-Mind strategic deprioritization, not just sharp trust +
  scarce capacity — our rule-based simulator with fixed allocation can't produce it.

## Pre-registration check (what we predicted vs. found)
- **Capacity:** predicted rerouting-fix degrades and the lever flips in {240,180,140} → **confirmed**,
  flips at ~180–240. Predicted shed benefit shrinks/maybe flips → **sharper than predicted:** DS1's
  *private* benefit shrinks but stays positive; the *system* benefit flips hard negative (the
  externality). 
- **δ:** predicted oscillation rises and HC1 may not return at high δ → **boring branch held:**
  δ-invariant, HC1 always returns, Doroudi collapse absent. Reported as the honest negative.
- **rung-b:** predicted dispersion shrinks, DS1 maybe loses both customers → dispersion **confirmed**
  (→0); DS1 outcome **opposite** (better, not worse).

## One-line summary for the meeting
Rerouting/shed is a clean win **only with spare healthy-chain capacity**; in the realistic
no-spare-capacity regime it stays privately rational for the disrupted distributor but becomes a
system disaster that hurts the rerouting hospital — a capacity-conditional misaligned incentive.
The result is robust to trust-sensitivity δ (the Doroudi collapse needs more than δ), and an
all-trust downstream doesn't change the distributor's story.
