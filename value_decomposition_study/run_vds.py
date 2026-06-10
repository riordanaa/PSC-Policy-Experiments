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


RUNG_A_HC = [dict(split_recipe='bytrust'), dict(split_recipe='equally')]


def hc_factory_for(policy, a):
    if policy.startswith('dsseat'):
        # the THESIS world: HC layer exactly as shipped (HC1 bytrust, HC2 equally,
        # delta hard-coded 0.1, no sharpening, no write-off)
        return lambda hc, i: FlexibleHCDecisionMaker(hc, **RUNG_A_HC[i])
    if policy.startswith('sat_full_oracle'):
        base = dict(RUNG_C_HC)
        base.update(onset_window=DIS, onset_disrupted_ds=None, onset_disrupted_share=0.1)
        return lambda hc, i: FlexibleHCDecisionMaker(hc, **base)
    if policy.startswith('a1_superset') or policy.startswith('sat_full') \
            or policy.startswith('h5_compound'):
        return lambda hc, i: UpstreamSignalRerouteHC(
            hc, threshold_frac=0.5, down_share=0.1, **RUNG_C_HC)
    if policy.startswith('h4b_ceiling'):
        base = dict(RUNG_C_HC)
        base.update(onset_window=DIS, onset_disrupted_ds=None, onset_disrupted_share=0.1)
        return lambda hc, i: RecoveryAwareWriteoffHC(hc, revive_theta=0.5, **base)
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
    if policy.startswith('dsseat'):
        def f(ds):
            dm = ShapedDS(
                ds, rule=rule,
                buffer_b=a.buffer_b,
                b_elev=a.b_elev, recovery_dwell=a.recovery_dwell,
                taper_thresh=None,
                prebook_f=(a.prebook_f if a.prebook_f > 0 else None),
                smooth_cap=(a.smooth_cap if a.smooth_cap > 0 else None),
                oo_gamma=(a.oo_gamma if a.oo_gamma >= 0 else None),
                throttle_c=(a.throttle_c if a.throttle_c > 0 else None),
                alloc_alpha=a.alloc_alpha)
            if a.mn_taper > 0:
                dm.mn_taper_m = a.mn_taper
            dm.needs_mn_watch = True   # all dsseat knobs read the upstream signal
            return dm
        return f
    if policy.startswith('a1_superset'):
        # A1 verification: TRUE superset oracle = full deployable stack (reroute+taper+prio)
        # + JIT buffer at the HEALTHY DS (the location lesson from sat50, never tried in slack)
        counter = {'i': 0}

        def f(ds):
            i = counter['i']; counter['i'] += 1
            b = a.buffer_b if i == 1 else 0
            dm = ShapedDS(ds, rule=rule, buffer_b=b,
                          buffer_window=(DIS[0] - a.jit_lead, DIS[1]))
            dm.mn_taper_m = a.taper_m
            return dm
        return f
    if policy.startswith('sat_full'):
        counter = {'i': 0}

        def f(ds):
            i = counter['i']; counter['i'] += 1
            b = a.buffer_b if i == 1 else 0     # standing buffer at DS_healthy only
            dm = ShapedDS(ds, rule=rule, buffer_b=b)
            dm.mn_taper_m = a.taper_m
            return dm
        return f
    if policy.startswith('h5_compound'):
        def f(ds):
            dm = ShapedDS(ds, rule=rule)
            dm.mn_taper_m = a.taper_m      # watch_mn wired post-build
            return dm
        return f
    if policy.startswith('h4b_ceiling'):
        counter = {'i': 0}

        def f(ds):
            i = counter['i']; counter['i'] += 1
            b = a.buffer_b if i == 0 else 0
            dm = ShapedDS(ds, rule=rule, buffer_b=b,
                          buffer_window=(DIS[0] - a.jit_lead, DIS[1]))
            dm.mn_taper_m = a.taper_m
            return dm
        return f
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


def set_regime(regime, duration=48):
    """Returns the original DISRUPTIONS for restoration.

    regime: 'slack' or 'satXX' (MN_healthy at XX% during the window).
    duration: disruption length in periods; window = [110, 109+duration]
    (duration=48 reproduces the thesis long window 110-157)."""
    original = copy.deepcopy(config.DISRUPTIONS)
    end_day = 109 + int(duration)
    first = dict(original[0])
    first['end_day_1'] = end_day
    if regime == 'slack':
        config.DISRUPTIONS = [first]
        return original
    assert regime.startswith('sat')
    factor_healthy = 1.0 - int(regime[3:]) / 100.0   # sat50 -> MN_healthy at 50% => factor 0.5
    second = dict(first)
    second['manufacturer_index'] = 1
    second['decrease_factor_1'] = factor_healthy
    config.DISRUPTIONS = [first, second]
    return original


def post_build_for(policy):
    needs_hc = policy.startswith(('h3b_upstream', 'h5_compound', 'sat_full', 'a1_superset'))
    needs_ds = policy.startswith(('h5_compound', 'h4b_ceiling', 'sat_full', 'a1_superset',
                                  'dsseat'))
    if not (needs_hc or needs_ds):
        return None

    def wire(sim, hc_dms, ds_dms):
        # info-sharing wiring: agents observe the live state of the MN feeding each chain
        ds_to_mn = {}
        for mn_idx, ds_idx in config.MN_DS_LINKS:
            ds_to_mn[sim.distributors[ds_idx].name()] = sim.manufacturers[mn_idx]
        if needs_hc:
            for hc_dm in hc_dms:
                if hasattr(hc_dm, 'mn_of_source'):
                    hc_dm.mn_of_source = {u: ds_to_mn[u]
                                          for u in hc_dm.hc.upstream_nodes
                                          if u in ds_to_mn}
        if needs_ds:
            for ds_dm in ds_dms:
                if getattr(ds_dm, 'mn_taper_m', None) is not None \
                        or getattr(ds_dm, 'needs_mn_watch', False):
                    ds_dm.watch_mn = ds_to_mn.get(ds_dm.ds.name())
    return wire


def run_policy(policy, demand_config, seeds, a, regime='slack', duration=48):
    original = set_regime(regime, duration)
    # dsseat policies live in the THESIS world: as-shipped delta (agent.py hard-codes 0.1)
    delta = None if policy.startswith('dsseat') else DELTA
    try:
        frames = []
        for seed in seeds:
            df = run_ladder.run_one('c', demand_config, seed, ARGS,
                                    ds_factory=ds_factory_for(policy, a),
                                    hc_factory=hc_factory_for(policy, a),
                                    delta_override=delta,
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
    ap.add_argument('--duration', type=int, default=48)
    ap.add_argument('--alloc-rule', default='prio_hc1')
    ap.add_argument('--buffer-b', type=float, default=0)
    ap.add_argument('--buffer-loc', default='disrupted',
                    choices=['disrupted', 'healthy', 'both'])
    ap.add_argument('--jit-lead', type=int, default=10)
    ap.add_argument('--taper-thresh', type=float, default=0.5)
    ap.add_argument('--taper-m', type=float, default=1.0)
    ap.add_argument('--throttle-c', type=float, default=0)   # 0 = off; was 1.2, which
    # silently activated the throttle in every dsseat run (caught 2026-06-11)
    ap.add_argument('--ss-freeze', type=int, default=0)
    ap.add_argument('--gamma', type=float, default=0.5)
    ap.add_argument('--mn-taper', type=float, default=0)
    ap.add_argument('--b-elev', type=float, default=0)
    ap.add_argument('--recovery-dwell', type=int, default=0)
    ap.add_argument('--prebook-f', type=float, default=0)
    ap.add_argument('--smooth-cap', type=float, default=0)
    ap.add_argument('--oo-gamma', type=float, default=-1)
    ap.add_argument('--alloc-alpha', type=float, default=0.2)
    ap.add_argument('--theta-down', type=float, default=0.5)
    ap.add_argument('--w-down', type=int, default=3)
    ap.add_argument('--theta-up', type=float, default=0.6)
    ap.add_argument('--w-up', type=int, default=3)
    ap.add_argument('--tag', default='')
    args = ap.parse_args()

    seeds = run_ladder.parse_seeds(args.seeds)
    regime_dir = args.regime if args.duration == 48 else f'{args.regime}_d{args.duration}'
    out_dir = os.path.join(HERE, 'results', regime_dir, args.config)
    os.makedirs(out_dir, exist_ok=True)
    df = run_policy(args.policy, args.config, seeds, args, regime=args.regime,
                    duration=args.duration)
    path = os.path.join(out_dir, f'{args.policy}{args.tag}.csv')
    df.to_csv(path, index=False)
    print(f'wrote {path} ({len(df)} rows)', flush=True)


if __name__ == '__main__':
    main()
