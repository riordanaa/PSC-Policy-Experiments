"""Value-decomposition study runner.

Wraps routing_study.run_ladder.run_one with named policy specs (hc_factory + ds_factory)
and regime overrides. All policies run on the rung-c routing baseline
(bytrust both HCs, trust^4, delta'=0.3, write-off k=5) unless the spec says otherwise.

Regimes:
  slack   the existing scenario (MN_disrupted at 5% during 110-157) — DEFAULT
  satXX   Phase 2 only: ADDITIONALLY MN_healthy cut to XX% during the same window
          (documented scope expansion; gates re-run in this world)

Usage:
  python value_decomposition_study/run_vds.py --policy h1_recovery_writeoff \
      --config urgent0 --seeds 11-30 [--regime slack] [--buffer-b 240] [--tag _x]
"""
import argparse
import copy
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'Test'))
os.chdir(ROOT)

import pandas as pd

import config
from routing_study import run_ladder
from routing_study.policies import FlexibleHCDecisionMaker
from understanding_study.alloc_policies import AllocFlexibleDS
from value_decomposition_study.policies_v2 import (
    RecoveryAwareWriteoffHC, DetectRerouteHC, ShapedDS,
    UpstreamSignalRerouteHC, DiscountWriteoffHC)

RUNG_C_HC = dict(split_recipe='bytrust', sharp_p=4.0, writeoff_k=5.0)
DELTA = 0.3
DIS = (110, 157)
ARGS = argparse.Namespace(delta=DELTA, sharp_p=4.0, writeoff_k=5.0, onset_share=0.1)


def hc_factory_for(policy, a):
    if policy == 'h1_recovery_writeoff' or policy.startswith('h4_ceiling'):
        base = dict(RUNG_C_HC)
        if policy.startswith('h4_ceiling'):
            base.update(onset_window=DIS, onset_disrupted_ds=None,
                        onset_disrupted_share=0.1)
        return lambda hc, i: RecoveryAwareWriteoffHC(hc, revive_theta=0.5, **base)
    if policy.startswith('h3b_upstream'):
        return lambda hc, i: UpstreamSignalRerouteHC(
            hc, threshold_frac=0.5, down_share=0.1, **RUNG_C_HC)
    if policy.startswith('h3_detect'):
        return lambda hc, i: DetectRerouteHC(
            hc, theta_down=a.theta_down, w_down=a.w_down,
            theta_up=a.theta_up, w_up=a.w_up, down_share=0.1, **RUNG_C_HC)
    if policy.startswith('h1b_gamma'):
        return lambda hc, i: DiscountWriteoffHC(hc, gamma=a.gamma, **RUNG_C_HC)
    if policy == 'd_oracle':
        base = dict(RUNG_C_HC)
        base.update(onset_window=DIS, onset_disrupted_ds=None, onset_disrupted_share=0.1)
        return lambda hc, i: FlexibleHCDecisionMaker(hc, **base)
    # default: plain rung-c HC layer
    return lambda hc, i: FlexibleHCDecisionMaker(hc, **RUNG_C_HC)


def ds_factory_for(policy, a):
    rule = a.alloc_rule
    if policy.startswith('h2_buffer') or policy.startswith('sat_buffer'):
        window = None
        loc = a.buffer_loc
        counter = {'i': 0}

        def f(ds):
            i = counter['i']; counter['i'] += 1
            b = a.buffer_b if (loc == 'both' or (loc == 'disrupted' and i == 0)
                               or (loc == 'healthy' and i == 1)) else 0
            return ShapedDS(ds, rule=rule, buffer_b=b, buffer_window=window)
        return f
    if policy.startswith('h4_ceiling'):
        counter = {'i': 0}

        def f(ds):
            i = counter['i']; counter['i'] += 1
            b = a.buffer_b if i == 0 else 0      # JIT pre-build at the disrupted DS only
            return ShapedDS(ds, rule=rule, buffer_b=b,
                            buffer_window=(DIS[0] - a.jit_lead, DIS[1]))
        return f
    if policy.startswith('sat_taper'):
        return lambda ds: ShapedDS(ds, rule=rule, taper_thresh=a.taper_thresh,
                                   taper_m=a.taper_m)
    if policy.startswith('sat_throttle'):
        return lambda ds: ShapedDS(ds, rule=rule, throttle_c=a.throttle_c,
                                   taper_thresh=None, freeze_thresh=0.5)
    if policy.startswith('sat_ssfreeze'):
        return lambda ds: ShapedDS(ds, rule=rule, ss_freeze=True)
    if policy.startswith('sat_compound'):
        counter = {'i': 0}

        def f(ds):
            i = counter['i']; counter['i'] += 1
            b = a.buffer_b if (a.buffer_loc == 'both'
                               or (a.buffer_loc == 'disrupted' and i == 0)
                               or (a.buffer_loc == 'healthy' and i == 1)) else 0
            return ShapedDS(ds, rule=rule, buffer_b=b,
                            taper_thresh=a.taper_thresh if a.taper_thresh > 0 else None,
                            taper_m=a.taper_m,
                            throttle_c=a.throttle_c if a.throttle_c > 0 else None,
                            ss_freeze=bool(a.ss_freeze))
        return f
    if policy == 'shaped_defaults_gate':
        return lambda ds: ShapedDS(ds, rule=rule)
    # default: plain allocation-rule DS
    return lambda ds: AllocFlexibleDS(ds, rule)


def set_regime(regime):
    """Returns the original DISRUPTIONS for restoration."""
    original = copy.deepcopy(config.DISRUPTIONS)
    if regime == 'slack':
        return original
    assert regime.startswith('sat')
    factor_healthy = 1.0 - int(regime[3:]) / 100.0   # sat50 -> MN_healthy at 50% => factor 0.5
    second = dict(config.DISRUPTIONS[0])
    second['manufacturer_index'] = 1
    second['decrease_factor_1'] = factor_healthy
    config.DISRUPTIONS = [config.DISRUPTIONS[0], second]
    return original


def post_build_for(policy):
    if not policy.startswith('h3b_upstream'):
        return None

    def wire(sim, hc_dms, ds_dms):
        # info-sharing wiring: each HC observes the MN feeding each of its DS sources
        ds_to_mn = {}
        for mn_idx, ds_idx in config.MN_DS_LINKS:
            ds_to_mn[sim.distributors[ds_idx].name()] = sim.manufacturers[mn_idx]
        for hc_dm in hc_dms:
            hc_dm.mn_of_source = {u: ds_to_mn[u]
                                  for u in hc_dm.hc.upstream_nodes if u in ds_to_mn}
    return wire


def run_policy(policy, demand_config, seeds, a, regime='slack'):
    original = set_regime(regime)
    try:
        frames = []
        for seed in seeds:
            df = run_ladder.run_one('c', demand_config, seed, ARGS,
                                    ds_factory=ds_factory_for(policy, a),
                                    hc_factory=hc_factory_for(policy, a),
                                    delta_override=DELTA,
                                    post_build=post_build_for(policy))
            df['rung'] = policy
            frames.append(df)
            print(f'{policy} {regime} {demand_config} seed {seed}: done', flush=True)
        return pd.concat(frames, ignore_index=True)
    finally:
        config.DISRUPTIONS = original


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--policy', required=True)
    ap.add_argument('--config', default='urgent0',
                    choices=list(run_ladder.DEMAND_CONFIGS))
    ap.add_argument('--seeds', default='11-30')
    ap.add_argument('--regime', default='slack')
    ap.add_argument('--alloc-rule', default='prio_hc1')
    ap.add_argument('--buffer-b', type=float, default=0)
    ap.add_argument('--buffer-loc', default='disrupted',
                    choices=['disrupted', 'healthy', 'both'])
    ap.add_argument('--jit-lead', type=int, default=10)
    ap.add_argument('--taper-thresh', type=float, default=0.5)
    ap.add_argument('--taper-m', type=float, default=1.0)
    ap.add_argument('--throttle-c', type=float, default=1.2)
    ap.add_argument('--ss-freeze', type=int, default=0)
    ap.add_argument('--gamma', type=float, default=0.5)
    ap.add_argument('--theta-down', type=float, default=0.5)
    ap.add_argument('--w-down', type=int, default=3)
    ap.add_argument('--theta-up', type=float, default=0.6)
    ap.add_argument('--w-up', type=int, default=3)
    ap.add_argument('--tag', default='')
    args = ap.parse_args()

    seeds = run_ladder.parse_seeds(args.seeds)
    out_dir = os.path.join(HERE, 'results', args.regime, args.config)
    os.makedirs(out_dir, exist_ok=True)
    df = run_policy(args.policy, args.config, seeds, args, regime=args.regime)
    path = os.path.join(out_dir, f'{args.policy}{args.tag}.csv')
    df.to_csv(path, index=False)
    print(f'wrote {path} ({len(df)} rows)', flush=True)


if __name__ == '__main__':
    main()
