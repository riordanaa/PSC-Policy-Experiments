"""
Evaluate DRL distributors vs base-stock during long disruption.

Examples:
  python evaluate_drl.py --fast
  python evaluate_drl.py --episodes 80 --periods 300
"""
from __future__ import print_function

import argparse
import os
import sys
import warnings

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
warnings.filterwarnings('ignore')

import tensorflow as tf

import config

from drl_evaluation import summarize_period_range, print_comparison


def _apply_eval_overrides(periods, dis_start, dis_end, train_eps):
    """Monkey-patch drl_evaluation module globals before run_*."""
    import drl_evaluation as tpr
    tpr.PERIODS = periods
    tpr.TRAIN_EPISODES = train_eps
    tpr.DISRUPTION_START = dis_start
    tpr.DISRUPTION_END = dis_end


def main():
    p = argparse.ArgumentParser(description='DRL vs baseline during disruption')
    p.add_argument('--fast', action='store_true', help='120 periods, disruption 40–87, 12 episodes')
    p.add_argument('--episodes', type=int, default=None, help='override EVAL_TRAIN_EPISODES')
    p.add_argument('--periods', type=int, default=None, help='override TOTAL_PERIODS cap')
    args = p.parse_args()

    if args.fast:
        periods = 120
        dis_start, dis_end = 40, 87
        train_eps = 12
        warmup_eff = 20
    else:
        warmup_eff = getattr(config, 'WARMUP_PERIODS', 0)
        periods = args.periods or min(config.TOTAL_PERIODS, 300)
        d0 = config.DISRUPTIONS[0]
        dis_start = int(d0['happen_day_1'])
        dis_end = int(d0['end_day_1'])
        train_eps = args.episodes or getattr(config, 'EVAL_TRAIN_EPISODES', 45)

    if dis_end >= periods:
        print('Warning: disruption end >= periods; extending periods', file=sys.stderr)
        periods = dis_end + 30

    _apply_eval_overrides(periods, dis_start, dis_end, train_eps)

    import drl_evaluation as tpr

    print('=' * 80, flush=True)
    print(' DRL vs baseline evaluation', flush=True)
    print(f' Topology {config.N_MN}x{config.N_DS}x{config.N_HC} | periods={periods} | '
          f'train_ep={train_eps} | disruption MN1: {dis_start}-{dis_end}', flush=True)
    print(f' Profit params f={config.PROFIT_PER_UNIT} c={config.INVENTORY_HOLDING_COST} '
          f'h={config.BACKLOG_COST}', flush=True)
    print('=' * 80, flush=True)

    config.set_global_seeds()
    snap_dir = os.path.join('checkpoints', 'eval_contribution')
    config.save_config_snapshot(snap_dir)
    config.save_run_seed_metadata(snap_dir, None)
    print(f' Config snapshot + run_seed.json -> {snap_dir}', flush=True)

    tf.keras.backend.clear_session()
    print('\n--- Training DRL (quiet) ---', flush=True)
    drl_episodes = tpr.run_drl()
    print('--- Baseline run ---', flush=True)
    baseline_data = tpr.run_baseline()

    wu = warmup_eff
    pre = (max(1, wu), max(wu, dis_start - 1))
    during = (max(wu + 1, dis_start), dis_end)
    post = (dis_end + 1, periods)

    def _slice_tag(name, a, b):
        return f'{name} (periods {a}-{b}, after warm-up >= {wu})'

    last_ep = train_eps - 1
    drl_data = drl_episodes[last_ep]

    baseline_pre = summarize_period_range(baseline_data, pre[0], pre[1], 'pre')
    baseline_dur = summarize_period_range(baseline_data, during[0], during[1], 'dur')
    baseline_post = summarize_period_range(baseline_data, post[0], post[1], 'post')

    drl_pre = summarize_period_range(drl_data, pre[0], pre[1], 'pre')
    drl_dur = summarize_period_range(drl_data, during[0], during[1], 'dur')
    drl_post = summarize_period_range(drl_data, post[0], post[1], 'post')

    print('\n' + '=' * 80)
    print(f' RESULTS: DRL episode {last_ep} vs baseline')
    print('=' * 80)

    r_pre = print_comparison(baseline_pre, drl_pre, _slice_tag('PRE-DISRUPTION', pre[0], pre[1]))
    r_dur = print_comparison(baseline_dur, drl_dur, _slice_tag('DURING DISRUPTION', during[0], during[1]))
    r_post = print_comparison(baseline_post, drl_post, _slice_tag('POST-DISRUPTION', post[0], post[1]))

    profit_win = r_dur['profit_diff'] > 0
    bklg_win = r_dur['sys_bklg_diff'] < 0
    print('\n' + '-' * 80)
    print(' Verdict (disruption window):')
    print('   DRL higher system profit: %s  (delta = %+.1f)' % (
        'YES' if profit_win else 'NO', r_dur['profit_diff']))
    print('   DRL lower DS+HC backlog:  %s  (delta = %+.1f)' % (
        'YES' if bklg_win else 'NO', r_dur['sys_bklg_diff']))
    if profit_win and bklg_win:
        print('\n   Both criteria met — supports the stated contribution.')
    elif profit_win:
        print('\n   Profit only — consider more episodes or reward tuning for backlog.')
    elif bklg_win:
        print('\n   Backlog only — check revenue/allocations vs holding costs.')
    else:
        print('\n   Neither criterion met at this training horizon.')
    print('-' * 80)

    return 0 if (profit_win and bklg_win) else 1


if __name__ == '__main__':
    sys.exit(main())
