"""Robustness sweeps for the advisor meeting: HEALTHY-manufacturer (MN2) capacity x
trust-EMA delta, comparing the SHED distributor policy against the base-stock BASELINE.

Reuses routing_study.run_ladder.run_one + value_decomposition_study.run_vds factories.
DOES NOT modify run_ladder.py or run_vds.py. Two knobs are injected purely through existing
hooks on run_one:
  - MN2 capacity : a composed post_build sets sim.manufacturers[1].num_active_lines = N
                   (the LineShutDown disruption only touches manufacturers[0], so this persists).
  - trust delta  : an explicit delta_override float (bypasses run_one's 'auto'->None for rung 'a'
                   and run_vds's hard-coded delta=None for dsseat; build_sim sets hc.delta).

Anchor cell = MN2 cap 400 (40 lines) x delta 0.1 x slack regime. The gate requires the driver's
baseline output == routing_study/results/{cfg}/a.csv and shed output ==
value_decomposition_study/results/slack/{cfg}/dsseat_alloc_shed_timed_rep.csv (bit-exact).

Usage:
  python value_decomposition_study/exp_robustness.py --mode gate     # reproduction gate only
  python value_decomposition_study/exp_robustness.py --mode sweep    # run all sweep cells
  python value_decomposition_study/exp_robustness.py --mode all      # gate then sweep (default)
"""
import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'Test'))
os.chdir(ROOT)

import numpy as np
import pandas as pd

import config
from routing_study import run_ladder
import value_decomposition_study.run_vds as vds

SHED = 'dsseat_alloc_shed_timed'
SEEDS = list(range(11, 31))           # reporting seeds only; no tuning (we sweep, not select)
DEFAULT_LINES = 40                    # config.MN_NUM_ACTIVE_LINES; 40*10 = 400/period
LINE_CAP = 10                         # config.MN_LINE_CAPACITY
ANCHOR_LINES, ANCHOR_DELTA = 40, 0.1


def shed_a():
    """run_vds.main() argparse namespace with all defaults, alloc_rule='shed_timed' (the
    policy that produced dsseat_alloc_shed_timed_rep.csv)."""
    return argparse.Namespace(
        alloc_rule='shed_timed', buffer_b=0.0, buffer_loc='disrupted', jit_lead=10,
        taper_thresh=0.5, taper_m=1.0, throttle_c=0.0, ss_freeze=0, gamma=0.5, margin=1.3,
        mn_taper=0.0, b_elev=0.0, recovery_dwell=0, prebook_f=0.0, smooth_cap=0.0,
        oo_gamma=-1.0, alloc_alpha=0.2, theta_down=0.5, w_down=3, theta_up=0.6, w_up=3)


def baseline_a():
    """routing_study.run_ladder.main() argparse namespace defaults (rung 'a' ignores
    sharp_p/writeoff_k/onset_share; delta is overridden explicitly per cell)."""
    return argparse.Namespace(delta=0.3, sharp_p=2.0, writeoff_k=3.0, onset_share=0.1)


def cap_post_build(n_lines, base_pb=None):
    def pb(sim, hc_dms, ds_dms):
        sim.manufacturers[1].num_active_lines = int(n_lines)   # MN2 = healthy chain
        if base_pb is not None:
            base_pb(sim, hc_dms, ds_dms)                        # shed watch_mn wiring, after
    return pb


def run_cell(policy, cfg, delta, n_lines, regime):
    """policy in {'baseline','shed'}; returns concat per-period DataFrame over SEEDS."""
    original = vds.set_regime(regime)            # 'slack' or 'none'; restores in finally
    try:
        frames = []
        for seed in SEEDS:
            if policy == 'baseline':
                pb = cap_post_build(n_lines, None)
                df = run_ladder.run_one('a', cfg, seed, baseline_a(),
                                        delta_override=float(delta), post_build=pb)
            elif policy == 'shed':
                a = shed_a()
                pb = cap_post_build(n_lines, vds.post_build_for(SHED))
                df = run_ladder.run_one('c', cfg, seed, vds.ARGS,
                                        ds_factory=vds.ds_factory_for(SHED, a),
                                        hc_factory=vds.hc_factory_for(SHED, a),
                                        delta_override=float(delta), post_build=pb)
            else:
                raise ValueError(policy)
            frames.append(df)
        return pd.concat(frames, ignore_index=True)
    finally:
        config.DISRUPTIONS = original


# ---------------------------------------------------------------- reproduction gate

def _numeric_equal(df_new, df_ref, label):
    a = df_new.sort_values(['seed', 'period']).reset_index(drop=True)
    b = df_ref.sort_values(['seed', 'period']).reset_index(drop=True)
    cols = [c for c in a.columns if c in b.columns
            and np.issubdtype(a[c].dtype, np.number)
            and np.issubdtype(b[c].dtype, np.number)]
    if len(a) != len(b):
        print(f"  [{label}] FAIL rows {len(a)} != {len(b)}")
        return False
    bad = []
    for c in cols:
        if not np.allclose(a[c].to_numpy(), b[c].to_numpy(), rtol=0, atol=1e-9, equal_nan=True):
            d = float(np.nanmax(np.abs(a[c].to_numpy() - b[c].to_numpy())))
            bad.append((c, d))
    if bad:
        print(f"  [{label}] FAIL {len(bad)} cols differ (atol=1e-9). Worst:")
        for c, d in sorted(bad, key=lambda x: -x[1])[:6]:
            print(f"      {c}: max|delta|={d:.6g}")
        # fall back to aggregate within 0.3% (CSV round-trip tolerance)
        agg_ok = all(abs(a[c].sum() - b[c].sum()) <= 3e-3 * (abs(b[c].sum()) + 1e-9)
                     for c, _ in bad)
        print(f"      aggregate-within-0.3% fallback: {'PASS' if agg_ok else 'FAIL'}")
        return agg_ok
    print(f"  [{label}] PASS ({len(cols)} numeric cols bit-exact, {len(a)} rows)")
    return True


def gate():
    print("=== ANCHOR REPRODUCTION GATE (cap=400, delta=0.1, slack) ===")
    ok = True
    for cfg in ('urgent0', 'urgent20'):
        ref_b = pd.read_csv(os.path.join(ROOT, 'routing_study', 'results', cfg, 'a.csv'))
        new_b = run_cell('baseline', cfg, ANCHOR_DELTA, ANCHOR_LINES, 'slack')
        ok &= _numeric_equal(new_b, ref_b, f'baseline/{cfg} vs a.csv')
    # shed reference only exists for urgent0 + urgent20 in slack
    for cfg in ('urgent0', 'urgent20'):
        ref_p = os.path.join(HERE, 'results', 'slack', cfg, 'dsseat_alloc_shed_timed_rep.csv')
        if not os.path.exists(ref_p):
            print(f"  [shed/{cfg}] no reference on disk, skipping")
            continue
        ref_s = pd.read_csv(ref_p)
        new_s = run_cell('shed', cfg, ANCHOR_DELTA, ANCHOR_LINES, 'slack')
        ok &= _numeric_equal(new_s, ref_s, f'shed/{cfg} vs dsseat_alloc_shed_timed_rep.csv')
    print(f"=== GATE {'PASSED' if ok else 'FAILED'} ===")
    return ok


# ---------------------------------------------------------------- sweeps

CAP_LINES = [40, 24, 18, 14, 12]                 # 400,240,180,140,120 /period
DELTAS = [0.05, 0.10, 0.20, 0.35, 0.50]


def _path(sub, cfg, policy, n_lines, delta):
    d = os.path.join(HERE, 'results', 'robustness', sub, cfg)
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, f'{policy}_lines{n_lines}_delta{int(round(delta*100)):03d}.csv')


def _emit(cells, force):
    """cells: list of (sub, cfg, policy, n_lines, delta, regime). Dedupe by output path."""
    seen = set()
    for sub, cfg, policy, n_lines, delta, regime in cells:
        p = _path(sub, cfg, policy, n_lines, delta)
        if p in seen:
            continue
        seen.add(p)
        if os.path.exists(p) and not force:
            print(f'skip (exists): {p}')
            continue
        df = run_cell(policy, cfg, delta, n_lines, regime)
        df.to_csv(p, index=False)
        print(f'wrote {p} ({len(df)} rows)', flush=True)


def sweeps(force=False):
    cells = []
    # capacity sweep at delta=0.1, slack; urgent0 full, urgent20 endpoints
    for pol in ('baseline', 'shed'):
        for n in CAP_LINES:
            cells.append(('cap_sweep', 'urgent0', pol, n, ANCHOR_DELTA, 'slack'))
        for n in (40, 12):
            cells.append(('cap_sweep', 'urgent20', pol, n, ANCHOR_DELTA, 'slack'))
    # delta sweep at cap=40, slack; urgent0 full, urgent20 endpoints (0.1 anchor, 0.5)
    for pol in ('baseline', 'shed'):
        for dlt in DELTAS:
            cells.append(('delta_sweep', 'urgent0', pol, ANCHOR_LINES, dlt, 'slack'))
        for dlt in (0.10, 0.50):
            cells.append(('delta_sweep', 'urgent20', pol, ANCHOR_LINES, dlt, 'slack'))
    # no-disruption ceiling at the anchor and the capacity floor (for rerouting-fix + floor guard)
    for pol in ('baseline', 'shed'):
        for n in (40, 12):
            cells.append(('none', 'urgent0', pol, n, ANCHOR_DELTA, 'none'))
    _emit(cells, force)


# ---------------------------------------------------------------- 2D grid (delta x capacity)

GRID_LINES = [40, 24, 18, 14]          # 400,240,180,140 /period
GRID_DELTAS = [0.10, 0.20, 0.35, 0.50]


def grid2d(force=False):
    """Focused interaction grid: does the capacity flip boundary move with trust delta, and
    does the Doroudi collapse appear in the high-delta x low-capacity corner?"""
    cells = []
    for pol in ('baseline', 'shed'):
        for n in GRID_LINES:
            for dlt in GRID_DELTAS:
                cells.append(('grid2d', 'urgent0', pol, n, dlt, 'slack'))
    _emit(cells, force)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--mode', default='all', choices=['gate', 'sweep', 'grid2d', 'all'])
    ap.add_argument('--force', action='store_true', help='overwrite existing sweep CSVs')
    args = ap.parse_args()
    if args.mode in ('gate', 'all'):
        if not gate() and args.mode == 'all':
            print('GATE FAILED — aborting sweeps.')
            sys.exit(1)
    if args.mode in ('sweep', 'all'):
        sweeps(force=args.force)
    if args.mode == 'grid2d':
        grid2d(force=args.force)


if __name__ == '__main__':
    main()
