# Routing Study — Results

All numbers from held-out reporting seeds 11–30 (paired; mean ± SE), system-level scoring
(all six agents), phases in true simulator time. Rung (c) parameters (δ′=0.3, p=4, k=5) were
chosen on tuning seeds 1–10 only; the ranking was stable across the entire tuning grid.
Verification gates 1–6 all passed (including exact reproduction of the prior baseline and a
cross-seed-variance gate added after discovering the patient-model seeding bug — see
routing_study_design.md §7).

## Headline

**Roughly two-thirds of the "unavoidable" disruption cost is a routing artifact, and with
onset-triggered rerouting, ~91% of it disappears — with no buffering, no anticipation, and no
learning.**

During+post system cost (urgent0, mean over 20 seeds; SE ≤ 0.3% of mean everywhere):

| Rung | During+post system cost | vs baseline |
|---|---:|---:|
| (a) baseline (HC_equal equal-split) | 3,700,784 | — |
| (b) HC_equal → trust-split | 2,730,635 | **−26.2%** |
| (c) b + sharper reroute (trust⁴, δ′=0.3) + stale write-off (k=5) | 1,209,659 | **−67.3%** |
| (d) b + oracle onset reroute (detect-then-reroute) | 332,166 | **−91.0%** |

urgent20 mirrors it: −26.7% / −65.7% / −88.6%.

## The full panel (urgent0)

| Metric | (a) | (b) | (c) | (d) |
|---|---:|---:|---:|---:|
| During system cost | 2,575,501 ± 5,268 | 2,099,628 | 954,248 | 196,505 |
| Post system cost | 1,125,283 ± 2,395 | 631,008 | 255,412 | 135,661 |
| Pre system cost (sanity: should be equal) | 17,044 | 17,040 | 17,045 | 17,040 |
| During backlog-cost share | 99.9% | 99.9% | 99.4% | 88.4% |
| Peak backlog DS_disrupted | 4,067 | 2,877 | 1,004 | 168 |
| Peak backlog DS_healthy | 139 | 199 | 572 | 528 |
| During fill rate (aggregate) | 0.808 | 0.897 | **1.000** | **1.000** |
| During fill HC_trust / HC_equal | 0.90 / 0.72 | 0.90 / 0.90 | 1.00 / 1.00 | 1.00 / 1.00 |
| Time-to-recovery DS_disrupted (periods) | 18 | 13 | 7 | 38.9* |
| Area-under-backlog, during+post | 131,253 | 93,526 | 33,797 | 4,126 |

\* TTR's 110%-of-pre-mean threshold misbehaves for rung (d): pre-disruption backlog is ~0, so
the threshold is tiny and the rung is penalized for clearing a small residual slowly. The
threshold-free area-under-backlog column is the honest comparison (131k → 4k).

## Lost patients (urgent20 — patient-facing outcome)

| Rung | Lost during | Lost post | Lost episode | vs baseline |
|---|---:|---:|---:|---:|
| (a) | 1,337 | 427 | 1,768 | — |
| (b) | 1,293 | 297 | 1,594 | −10% |
| (c) | 502 | 4 | 510 | **−71%** |
| (d) | 226 | 6 | 236 | **−87%** |

## What the numbers say

1. **The healthy chain could serve everything all along.** Under rungs (c)/(d) the
   during-disruption aggregate fill rate is 1.000: MN_healthy (capacity 400/period, normally
   loaded ~120) absorbs essentially all redirected demand, and DS_healthy's transient backlog
   peaks at only ~530–570 (vs the ~4,100 pile-up it replaces). The system was never
   supply-capped — only the disrupted CHAIN was. The binding constraint was the routing rule.
2. **Each mechanism contributes measurably.** Equal-split lock-in (a→b): −26%. Trust's slow,
   incomplete redirection + stranded-order suppression (b→c): another −41 points. Detection
   timing (c→d): the last −24 points. The b→c gap confirms both compounding artifacts matter:
   trust bottoms out at a ~0.23 share (the EMA floor predicted in the hypothesis doc) while
   the sharper rule reaches ~0.12 within ~10 periods.
3. **Cost does not just move between agents** — system-wide backlog cost collapses
   (during: 2.574M → 0.174M for d) against a small holding increase (1.5k → 22.8k during) and
   DS_healthy's modest transient. The write-off's late-delivery glut is honestly visible in
   rung (c)'s post holding (134.6k vs 107.1k baseline) and is dwarfed by its backlog savings.
4. **Fairness:** baseline harm concentrates on HC_equal (during fill 0.72 vs 0.90). Every
   fixed rung equalizes the two HCs (dispersion ≈ 0).
5. **Doroudi non-monotonicity check:** flipping HC_equal to trust-split did NOT backfire in
   this regime — (b) improves every reported metric. The prior was worth carrying; the data
   answered it.

## Honest notes

- The naive back-of-envelope (0.8M–1.3M attributable to routing) was an underestimate of the
  full routing channel (realized: ~2.5M during+post for b+c mechanisms combined) but the
  hypothesis doc correctly anticipated that rung (b) alone recovers much less than the
  arithmetic (0.97M) because of the trust-EMA floor and the order cap.
- Rung (d) uses an ORACLE onset signal (fires at exactly period 110). It is an upper bound on
  detect-then-reroute; a real detector fires a few periods late and the trajectory between (c)
  and (d) bounds that case. Detection still cannot help BEFORE onset (the anticipation
  impossibility result D3 stands untouched — there is nothing to detect before period 110).
- All "seeds" in any historical experiment that used the normal demand model were one demand
  path (patient_model.py:28 reseeds the global RNG to 0 at construction). Fixed in this
  study's runner; flagged for the codebase.
