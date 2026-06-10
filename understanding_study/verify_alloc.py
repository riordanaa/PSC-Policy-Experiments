"""Gate for E1: the proportional rule, implemented through the NEW pluggable-allocator
code path, must reproduce the routing study's rung-c trajectories bit-for-bit (same seed,
same config). Proves the plumbing changes nothing except the allocate_to computation."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'Test'))
os.chdir(ROOT)

import pandas as pd

from understanding_study.run_allocation_bound import run_one_alloc

REF = os.path.join(ROOT, 'routing_study', 'results', 'urgent0', 'c.csv')


def main():
    ref = pd.read_csv(REF)
    ref11 = ref[ref['seed'] == 11].sort_values('period').reset_index(drop=True)
    new = run_one_alloc('proportional', 'urgent0', 11).sort_values('period').reset_index(drop=True)
    num_cols = [c for c in ref11.columns
                if c not in ('rung', 'config') and pd.api.types.is_numeric_dtype(ref11[c])]
    bad = []
    for c in num_cols:
        d = (ref11[c] - new[c]).abs().max()
        # the reference passed through CSV serialization; allow float round-trip noise
        # (1e-9 still catches any genuine logic difference — state vars are integers)
        if d > 1e-9:
            bad.append((c, d))
    if bad:
        print('GATE ALLOC: FAIL — diffs:', bad[:10])
        sys.exit(1)
    print(f'GATE ALLOC (proportional via new path == rung-c CSV, seed 11, '
          f'{len(num_cols)} columns x {len(ref11)} periods): PASS')


if __name__ == '__main__':
    main()
