"""Tune rung (c) parameters on TUNING SEEDS 1-10 ONLY (pre-registered split;
reporting seeds 11-30 are never touched here).

Grid: delta' in {0.3, 0.5} x sharp_p in {2, 4} x writeoff_k in {2, 3, 5}.
Criterion: mean during+post (periods 110-300) system-level cost
(holding 1/unit x inventory + backlog 10/unit x backlog, summed over all six agents),
urgent0 config. Rung (b) is run as the no-extras reference.
"""
import argparse
import itertools
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'Test'))
os.chdir(ROOT)

import pandas as pd

from routing_study import run_ladder

TUNING_SEEDS = list(range(1, 11))
HERE = os.path.dirname(os.path.abspath(__file__))

HOLD = 1.0
BACK = 10.0
AGENTS = ['ds1', 'ds2', 'mn1', 'mn2', 'hc1', 'hc2']


def system_cost(df, lo=110, hi=300):
    d = df[(df['period'] >= lo) & (df['period'] <= hi)]
    cost = 0.0
    for a in AGENTS:
        cost += HOLD * d[f'{a}_inventory'].sum() + BACK * d[f'{a}_backlog'].sum()
    return cost


def args_for(delta, p, k):
    return argparse.Namespace(delta=delta, sharp_p=p, writeoff_k=k, onset_share=0.1)


def main():
    rows = []
    # reference: rung b (delta hard-coded 0.1, plain trust split, no write-off)
    costs = [system_cost(run_ladder.run_one('b', 'urgent0', s, args_for(0.1, 2, 3)))
             for s in TUNING_SEEDS]
    rows.append(dict(variant='b_reference', delta=0.1, p=None, k=None,
                     mean_cost=sum(costs) / len(costs)))
    print(f"b_reference: {rows[-1]['mean_cost']:,.0f}", flush=True)

    for delta, p, k in itertools.product((0.3, 0.5), (2, 4), (2, 3, 5)):
        costs = [system_cost(run_ladder.run_one('c', 'urgent0', s, args_for(delta, p, k)))
                 for s in TUNING_SEEDS]
        mean_cost = sum(costs) / len(costs)
        rows.append(dict(variant=f'c_d{delta}_p{p}_k{k}', delta=delta, p=p, k=k,
                         mean_cost=mean_cost))
        print(f"c delta={delta} p={p} k={k}: {mean_cost:,.0f}", flush=True)

    out = pd.DataFrame(rows).sort_values('mean_cost')
    path = os.path.join(HERE, 'results', 'tuning_c.csv')
    os.makedirs(os.path.dirname(path), exist_ok=True)
    out.to_csv(path, index=False)
    print('\nRanking (lower=better):')
    print(out.to_string(index=False))
    print(f'\nwrote {path}')


if __name__ == '__main__':
    main()
