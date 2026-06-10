# NEXT_PLAN — written after Phases 1+2 complete (2026-06-10)

> **UPDATE 2026-06-11 (post H10 — current state of the queue):**
> - DONE since the list below was written: severity-aware redirect (item 1 — REFUTED, H9);
>   demand-aware buffer sizing (item 2 — KEPT, refined to per-event sizing under H10);
>   sat30 location screen (item 6 — corrected the map cell); **recurring-disruption
>   robustness (item 3 — PASSED, map publication-ready)**; coverage-collapse and shed-equity
>   verifications (H10).
> - REMAINING, in priority order:
>   1. **USER ACTION: obtain the thesis Table 3.9 configuration from the author** — the
>      only item that can change the interpretation of the 49%-vs-89% result.
>   2. **Paper distillation** from `consolidated_report/` (skeleton drafted at
>      `consolidated_report/paper_outline.md`).
>   3. **Ramped-onset regime** — the second paper; awaits user approval (new regime).
>   4. When corrected DRL code arrives: evaluate vs the regime-appropriate compounds
>      (bars in the consolidated claims table), same seeds/gates/accounting.
>   5. Deferred small items (urgent20 map columns, γ-discount under scarcity) — only if a
>      reviewer asks.

> **UPDATE 2026-06-11 (post Part A verification + Part B / H8):** the decision now in front
> of the user is (a) whether to run Part C (severity-aware redirect across the map +
> demand-aware buffer sizing + sat30 location screen) as planned, and (b) how to weigh the
> project's center of gravity given H8: simple DS-seat rules capture ~49–51% of the thesis
> RL's claimed loss-removal (audited), with the residual attributable to either a mechanism
> outside the enumerated family or baseline non-comparability (branch iii — the Table 3.9
> config request to the thesis author is now the single highest-value piece of missing
> information). New item for review: promote the DS-seat compound
> (shed × taper × standing) to a named policy in the paper, with the taper's
> patient-cost caveat attached.

Per protocol: items inside the already-approved scope could be executed freely; items
introducing a NEW REGIME or NEW POLICY CLASS pause for user review. Everything below is the
latter or is deliberately deferred — **nothing here was executed overnight.**

## Requires user review (new policy class)

1. **Severity-aware redirect** (motivated directly by H7's routing-flips-negative result):
   a reroute that caps redirected volume at the surviving chain's OBSERVED headroom
   (e.g., redirect min(demand, recent healthy-chain delivery rate) and leave the rest with
   the dead chain's trickle). Hypothesis: removes the sat30 routing penalty and the urgent20
   reroute-alone penalty, making routing safe at every severity. This is the single most
   valuable next experiment: it would make the deployable compound robust across the whole
   map. New policy class (state-dependent redirect cap) → user approval.
2. **Demand-aware buffer sizing** (motivated by H6's urgent20 nuance: the frozen grid was
   scaled to urgent0 demand and B1440 > B960 under urgent20): size B to measured demand
   minus measured surviving capacity. Borderline (parameterization of an existing class);
   flagged for review rather than assumed in-scope.

## Requires user review (new regime)

3. **Disruption-frequency axis** (recurring disruptions): the premium of standing insurance
   amortizes across events; a single-event episode understates the buffer's value per unit
   premium. One extra axis would complete the insurance economics.
4. **Ramped-onset disruption** (the dossier's original Fork B): with H3's masking result,
   a ramp would give downstream detectors positive lead — the one regime where DETECTION
   (vs info-sharing) could earn value. Still the "second paper" in our judgment.

## In scope but deliberately deferred (diminishing returns)

5. urgent20 columns for the non-primary map cells (map is urgent0; primary cell has both).
6. Buffer-location screen repeated at sat30 (healthy-location assumed from sat50 screen;
   at sat30 "healthy" is less healthy — worth a 12-run check if the map is published).
7. h1b-style γ-discount under scarcity (slack verdict: marginal; unlikely to change).

## For the RL question (when corrected code arrives)

The bar is now regime-dependent and all-simple-rules:
- slack: h5 compound (reroute+taper) — 273k full / 221k ex-MN; lost 204.
- sat50,d48: sat_full compound — 767k urgent0; B1440 variant, lost 505 urgent20.
- The measured room above these is ~zero (slack: oracle compositions add nothing;
  sat50: no measured policy beats the compound). Any learned policy must beat these
  numbers on the same seeds, same gates, both accounting conventions, fairness-preserving.
