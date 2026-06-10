"""E1: allocation bound on the routing-fixed (rung c) baseline, slack regime.

Runs the DS allocation family closed-loop on top of rung-c HC routing
(bytrust both HCs, trust^4, delta'=0.3, write-off k=5) and the standard SimpleDS ordering
logic. The proportional rule IS rung c (already on disk in routing_study/results); the gate in
verify_alloc.py proves the new code path reproduces it bit-for-bit.

Usage:
  python understanding_study/run_allocation_bound.py --rules equal,prio_hc1,prio_hc2,backlog_priority,serve_captive \
      --config urgent0 --seeds 11-30
"""
import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'Test'))
os.chdir(ROOT)

import pandas as pd

from routing_study import run_ladder
from understanding_study.alloc_policies import AllocFlexibleDS

RUNG_C_ARGS = argparse.Namespace(delta=0.3, sharp_p=4.0, writeoff_k=5.0, onset_share=0.1)


def run_one_alloc(rule, demand_config, seed):
    df = run_ladder.run_one('c', demand_config, seed, RUNG_C_ARGS,
                            ds_factory=lambda ds: AllocFlexibleDS(ds, rule))
    df['rung'] = f'alloc_{rule}'
    return df


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--rules',
                    default='equal,prio_hc1,prio_hc2,backlog_priority,serve_captive')
    ap.add_argument('--config', default='urgent0',
                    choices=list(run_ladder.DEMAND_CONFIGS))
    ap.add_argument('--seeds', default='11-30')
    args = ap.parse_args()

    seeds = run_ladder.parse_seeds(args.seeds)
    out_dir = os.path.join(HERE, 'results', args.config)
    os.makedirs(out_dir, exist_ok=True)

    for rule in args.rules.split(','):
        frames = []
        for seed in seeds:
            frames.append(run_one_alloc(rule, args.config, seed))
            print(f'alloc {rule} {args.config} seed {seed}: done', flush=True)
        df = pd.concat(frames, ignore_index=True)
        path = os.path.join(out_dir, f'alloc_{rule}.csv')
        df.to_csv(path, index=False)
        print(f'wrote {path} ({len(df)} rows)', flush=True)


if __name__ == '__main__':
    main()
