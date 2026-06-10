# LEDGER — tried / kept / discarded

| Item | Status | Reason (one line, traceable) |
|---|---|---|
| Recovery-aware write-off (H1) | DISCARDED | Glut unchanged (excess 3,033 vs 2,967), cost +2%; double-order committed mid-window — revival at recovery too late by construction. |
| γ-discount write-off (H1b, γ=0.5) | DISCARDED (marginal) | −1.5% (1,044k vs 1,063k); whole accounting channel ≈ glut holding ~25–30k; rerouting fixes the glut better as a side effect. |
| Standing DS buffers in slack (H2) | DISCARDED | Coverage ≤ 0 at every B (B600: −241k at +31k premium); buffer feeds the dead-factory queue + glut. Supersedes broken-routing "42% insurance". |
| Delivery-rate detect-then-reroute (H3) | DISCARDED | Strictly worse than built-in trust EMA (1,239k vs 1,063k); ~6-period stock-cover masking is structural for ANY downstream delivery-statistics detector. |
| Upstream-signal reroute (H3b) | **KEPT — promoted to compound** | Equals oracle exactly (294,796 urgent0; 203 lost urgent20). Two-line rule; quantifies info-sharing value (~750k + 242 patients). |
| JIT pre-build B=120 (H4 component) | KEPT (ceiling only) | +11k value at 2.7k premium WITH oracle window; collapses for B>120; no patient benefit. Not worth deploying without oracle timing. |
| Static-priority allocation | KEPT (fairness-costed baseline) | −12.4% vs proportional; dispersion cost ±0.023 fill. Both baselines carried per A3. |
| backlog-priority / serve-captive allocation | DISCARDED (prior study) | +56% / +25% — alternating failures degrade both trust loops. |
