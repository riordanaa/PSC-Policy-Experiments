"""Phase 2 / H5: the routing ladder re-run in a saturated regime.

A saturated regime ADDITIONALLY cuts MN_healthy during the same window (sat50 = to 50%).
This is the study's one documented scope expansion; gates G5/G6 must pass in the regime
before its results are used (gates_vds.py --gates 5,6 --regime satXX).

Usage:
  python value_decomposition_study/run_sat_ladder.py --regime sat50 --config urgent0 --seeds 11-30
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
from value_decomposition_study.run_vds import set_regime

import config


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--regime', default='sat50')
    ap.add_argument('--config', default='urgent0')
    ap.add_argument('--rungs', default='a,b,c,d')
    ap.add_argument('--seeds', default='11-30')
    ap.add_argument('--duration', type=int, default=48)
    ap.add_argument('--recur2', type=int, default=0)
    args_cli = ap.parse_args()

    ladder_args = argparse.Namespace(delta=0.3, sharp_p=4.0, writeoff_k=5.0,
                                     onset_share=0.1)
    seeds = run_ladder.parse_seeds(args_cli.seeds)
    regime_dir = (args_cli.regime if args_cli.duration == 48
                  else f'{args_cli.regime}_d{args_cli.duration}')
    if args_cli.recur2:
        regime_dir += f'_recur{args_cli.recur2}'
    out_dir = os.path.join(HERE, 'results', regime_dir, args_cli.config)
    os.makedirs(out_dir, exist_ok=True)

    original = set_regime(args_cli.regime, args_cli.duration, args_cli.recur2)
    try:
        for rung in args_cli.rungs.split(','):
            frames = []
            for seed in seeds:
                frames.append(run_ladder.run_one(rung, args_cli.config, seed,
                                                 ladder_args))
                print(f'sat-ladder {rung} {args_cli.regime} {args_cli.config} '
                      f'seed {seed}: done', flush=True)
            df = pd.concat(frames, ignore_index=True)
            path = os.path.join(out_dir, f'ladder_{rung}.csv')
            df.to_csv(path, index=False)
            print(f'wrote {path}', flush=True)
    finally:
        config.DISRUPTIONS = original


if __name__ == '__main__':
    main()
