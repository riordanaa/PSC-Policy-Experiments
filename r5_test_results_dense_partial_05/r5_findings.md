# r5 Diagnostic Findings
**Setup:** 2×2×2 topology, 2 DRL agents, MAB off (equal weights), profit proxy off, 50% moderate disruption (periods 110–157), 200 training episodes, 5 eval episodes averaged.

## DS 1
**A. False-positive rate** — r5=+1 pre: 100.00%, during: 100.00%, post: 100.00%. Difference pre→during: 0.00%. **CONFIRMS hypothesis**: r5 barely discriminates between stable and disruption phases.
**B. Slope discrimination** — mean |β₁| pre: 0.0283, during: 0.0354. Change: 0.0071. **CONFIRMS hypothesis**: the order slope barely changes during disruption, so r5 cannot signal the disruption period.
**C. Smoking-gun cross-tab** — bad-state threshold (backlog): 5437.7. P(r5=+1 | bad state, during disruption): 100.00%. **CONFIRMS hypothesis**: r5 rewards the agent in a bad state more than half the time.
**D. Pearson correlation β₁ vs Δbacklog (during)** — r = -0.0372 (p=0.5675). **CONFIRMS hypothesis**: a near-zero correlation means β₁ is not tracking the backlog change signal.
**E. Reward inconsistency** — mean backlog when r5=+1: 6509.1, when r5=−1: nan. does not confirm hypothesis: backlog is clearly lower when r5 fires positive, meaning r5 is discriminating correctly.
