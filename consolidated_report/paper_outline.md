# Paper outline (distilled from consolidated_findings.pdf — to be written fresh, not merged)

**Working title:** How Much Room Is There for Learning? A Value Decomposition for
Unforecastable Supply-Chain Disruptions

**Thesis (one sentence):** under a sudden, unforecastable disruption, nearly all achievable
value is captured by structure — what information is shared, where orders are routed, and
where/how much stock is held — leaving learned policies a measured residual near zero in
the studied regimes; the dominant lever flips predictably with disruption duration and
severity.

## Sections

1. **Introduction** — decision-first framing (Cohen et al.): instead of asking "does RL
   beat the baseline," measure how much room any policy has, then ask what fills it.
   Position vs Gijsbrechts et al. (DRL vs heuristics on canonical problems) and Dehaybe
   (non-stationarity learnable only when forecastable).
2. **Setting** — the thesis simulator (table); the inherited RL claim (Table 3.9) and its
   replication status.
3. **The routing artifact** — 67–91% result; stranded-order mechanism; supersedes the
   "unavoidable pile-up" framing. (Fig: backlog trajectories by rung.)
4. **Information is the binding constraint** — stock-cover masking (~6 periods); upstream
   signal ≡ oracle (bit-exact); foresight worth ~5% only with correct buffer location;
   bounded-family residual ≈ 0. (Quantifies the value of information sharing with a
   two-line rule — reframes the thesis's info-sharing narrative.)
5. **The distributor's seat** — full-grid ladder; demand-shaping confirmed (shed pair);
   the 49–51% vs 89% result with the three pre-registered interpretations; equity
   characterization (Pareto on totals, localized trough). (Fig: DS-seat shares bar.)
6. **Scarcity and the lever-flip map** — frontier (compound dominance 2.4× at matched
   premium); location flip; demand-aware per-event sizing (lost 505→41); redirect-cap
   refutation (orders are the production signal); recurrence robustness; coverage
   non-collapse (gated rules inert; RL lost 18% in no-disruption). (Fig: lever-flip map;
   frontier.)
7. **Negative results as design rules** — the seven backfired adaptive rules; consistency
   beats cleverness via the trust loop.
8. **Discussion** — what would change the conclusion (thesis baseline config; ramped
   onset = forecastable disruptions; richer action spaces at the hospital echelon);
   methodology note (gates, seed discipline, dual accounting, independent audits — one
   paragraph, pointing to the notebook).

## What stays OUT of the paper (notebook material)
Process incidents, audit counts, discarded batches, per-card verdicts, simulator bug
catalog (one footnote pointing to the repository).

## Blocking item
Section 5's interpretation hinges on the thesis Table 3.9 configuration (requested from
the author). Write sections 1–4 and 6–8 now; finalize 5 when the config arrives or after
documenting that it could not be obtained.
