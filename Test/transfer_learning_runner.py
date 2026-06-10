"""
Transfer Learning & Scenario Sensitivity Runner

Implements the full "train on scenario A, fine-tune on scenario B" pipeline
Supports sensitivity sweeps across disruption
length, info-sharing mode, and topology.

Usage:
  # Phase 1: Train from scratch on long disruption
  python transfer_learning_runner.py --phase train --scenario long_disruption --episodes 80

  # Phase 2: Fine-tune the trained model on short disruption
  python transfer_learning_runner.py --phase finetune --scenario short_disruption \
      --source-checkpoint checkpoints/long_disruption --episodes 30

  # Sensitivity sweep across disruption lengths
  python transfer_learning_runner.py --phase sweep --sweep-param disruption_length

  # Sensitivity sweep across info-sharing scenarios
  python transfer_learning_runner.py --phase sweep --sweep-param info_sharing

  Reproducibility: every phase calls set_global_seeds() and writes config_snapshot.json
  under the checkpoint directory (use --seed to override config.RANDOM_SEED).
"""
from __future__ import print_function

import argparse
import json
import os
import sys
import time
import warnings

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
warnings.filterwarnings('ignore')

import numpy as np
import tensorflow as tf

import config
import simulator.simulation_runner as sim_runner
import simulator.decision_maker as dmaker
from drl_simulation_profile_config import ConfigDrivenProfile
from drl_evaluation import compute_agent_metrics, summarize_period_range, print_comparison


SCENARIO_PRESETS = {
    'long_disruption': {
        'disruption_start': 110, 'disruption_end': 157,
        'info_sharing': 'partial', 'periods': 300,
    },
    'moderate_disruption': {
        'disruption_start': 110, 'disruption_end': 127,
        'info_sharing': 'partial', 'periods': 250,
    },
    'short_disruption': {
        'disruption_start': 110, 'disruption_end': 115,
        'info_sharing': 'partial', 'periods': 200,
    },
    'full_info': {
        'disruption_start': 110, 'disruption_end': 157,
        'info_sharing': 'full', 'periods': 300,
    },
    'no_info': {
        'disruption_start': 110, 'disruption_end': 157,
        'info_sharing': 'none', 'periods': 300,
    },
}


def _apply_scenario(scenario_cfg):
    """Monkey-patch config module with scenario-specific overrides."""
    if 'info_sharing' in scenario_cfg:
        config.INFO_SHARING_SCENARIO = scenario_cfg['info_sharing']
    if 'disruption_start' in scenario_cfg:
        config.DISRUPTIONS[0]['happen_day_1'] = scenario_cfg['disruption_start']
    if 'disruption_end' in scenario_cfg:
        config.DISRUPTIONS[0]['end_day_1'] = scenario_cfg['disruption_end']


def _repro_setup(snapshot_dir, seed=None):
    """Seed RNGs and write config_snapshot.json + run_seed.json for reproducibility."""
    config.set_global_seeds(seed)
    os.makedirs(snapshot_dir, exist_ok=True)
    path = config.save_config_snapshot(snapshot_dir)
    used = seed if seed is not None else config.RANDOM_SEED
    seed_path = config.save_run_seed_metadata(snapshot_dir, seed)
    print(f'  Reproducibility: run_seed_applied={used}  config_snapshot={path}  {os.path.basename(seed_path)}', flush=True)
    return path


def train_drl(episodes, periods, checkpoint_dir, source_checkpoint=None):
    """Train DRL agents, optionally loading from a source checkpoint (transfer learning)."""
    if source_checkpoint:
        config.TRANSFER_CHECKPOINT_DIR = source_checkpoint
    else:
        config.TRANSFER_CHECKPOINT_DIR = None

    tf.keras.backend.clear_session()
    profile = ConfigDrivenProfile('drl_train')
    for d in profile.simulation.disruptions:
        d.happen_day_1 = config.DISRUPTIONS[0]['happen_day_1']
        d.end_day_1 = config.DISRUPTIONS[0]['end_day_1']

    dm = dmaker.PerAgentDecisionMaker()
    hc_dms = []
    for i, hc in enumerate(profile.health_centers):
        recipe = config.HC_ORDER_SPLIT[i] if i < len(config.HC_ORDER_SPLIT) else 'equally'
        hc_dm = dmaker.SimpleHCDecisionMaker(hc, recipe)
        dm.add_decision_maker(hc_dm)
        hc_dms.append(hc_dm)
    mn_dms = []
    for mn in profile.manufacturers:
        mn_dm = dmaker.SimpleMNDecisionMaker(mn)
        dm.add_decision_maker(mn_dm)
        mn_dms.append(mn_dm)

    drl_dms = []
    for i, ds in enumerate(profile.distributors):
        ds_dm = dmaker.DRLDSDecisionMaker(ds, mn_dms, hc_dms, periods, f'DS {i+1}', episodes)
        dm.add_decision_maker(ds_dm)
        drl_dms.append(ds_dm)

    runner = sim_runner.SimulationRunner(
        profile.simulation, dm, profile.agent_builder,
        profile.parameterize_sim_agents, profile.add_patient_model, profile.add_disruptions)
    runner._update_patient(0)
    runner._update_agents(0)

    all_episodes = {}
    learning_curve = []
    do_reset = False

    for eps in range(episodes):
        t0 = time.time()
        for d in drl_dms:
            d.ds_env.reset()
            d.episode = eps
        ep_data = []
        for pr in range(periods):
            runner.next_cycle(do_reset)
            do_reset = False
            if pr > 0:
                ep_data.append(compute_agent_metrics(profile.simulation, profile.simulation.now))
        do_reset = True
        all_episodes[eps] = ep_data

        ds_bklg = np.mean([sum(d[a]['bklg'] for a in d if a.startswith('ds_')) for d in ep_data]) if ep_data else 0
        ds_profit = np.mean([sum(d[a]['profit'] for a in d) for d in ep_data]) if ep_data else 0
        elapsed = time.time() - t0
        learning_curve.append({'episode': eps, 'ds_bklg': float(ds_bklg),
                               'profit': float(ds_profit), 'time_s': elapsed})
        print(f'  Ep {eps:3d}/{episodes}: bklg={ds_bklg:7.1f}  profit={ds_profit:9.1f}  ({elapsed:.1f}s)')

    os.makedirs(checkpoint_dir, exist_ok=True)
    for d in drl_dms:
        d.ds_env.save_checkpoint(checkpoint_dir)
    curve_path = os.path.join(checkpoint_dir, 'learning_curve.json')
    with open(curve_path, 'w') as f:
        json.dump(learning_curve, f, indent=2)
    print(f'  Checkpoint saved to {checkpoint_dir}')

    return all_episodes, learning_curve


def run_baseline(periods):
    """Run baseline (base-stock DS) for 1 episode."""
    profile = ConfigDrivenProfile('baseline')
    for d in profile.simulation.disruptions:
        d.happen_day_1 = config.DISRUPTIONS[0]['happen_day_1']
        d.end_day_1 = config.DISRUPTIONS[0]['end_day_1']
    dm = dmaker.PerAgentDecisionMaker()
    for i, hc in enumerate(profile.health_centers):
        recipe = config.HC_ORDER_SPLIT[i] if i < len(config.HC_ORDER_SPLIT) else 'equally'
        dm.add_decision_maker(dmaker.SimpleHCDecisionMaker(hc, recipe))
    for mn in profile.manufacturers:
        dm.add_decision_maker(dmaker.SimpleMNDecisionMaker(mn))
    for ds in profile.distributors:
        dm.add_decision_maker(dmaker.SimpleDSDecisionMaker(ds))
    runner = sim_runner.SimulationRunner(
        profile.simulation, dm, profile.agent_builder,
        profile.parameterize_sim_agents, profile.add_patient_model, profile.add_disruptions)
    runner._update_patient(0)
    runner._update_agents(0)
    data = []
    for pr in range(periods):
        runner.next_cycle(False)
        if pr > 0:
            data.append(compute_agent_metrics(profile.simulation, profile.simulation.now))
    return data


def evaluate(drl_episodes, baseline_data, periods, dis_start, dis_end, label):
    """Compare last DRL episode vs baseline and return results dict."""
    warmup = getattr(config, 'WARMUP_PERIODS', 0)
    pre = (max(1, warmup), max(warmup, dis_start - 1))
    during = (max(warmup + 1, dis_start), dis_end)
    post = (dis_end + 1, periods)

    last_ep = max(drl_episodes.keys())
    drl_data = drl_episodes[last_ep]

    results = {}
    for tag, (s, e) in [('pre', pre), ('during', during), ('post', post)]:
        b = summarize_period_range(baseline_data, s, e, tag)
        d = summarize_period_range(drl_data, s, e, tag)
        r = print_comparison(b, d, f'{label} {tag.upper()} ({s}-{e})')
        results[tag] = r
    return results


def run_sweep(param_name, episodes, periods_base, seed=None):
    """Run a sensitivity sweep across one parameter dimension."""
    if param_name == 'disruption_length':
        sweep_configs = [
            ('short_5',   {'disruption_start': 110, 'disruption_end': 115}),
            ('short_10',  {'disruption_start': 110, 'disruption_end': 120}),
            ('mod_17',    {'disruption_start': 110, 'disruption_end': 127}),
            ('mod_30',    {'disruption_start': 110, 'disruption_end': 140}),
            ('long_47',   {'disruption_start': 110, 'disruption_end': 157}),
            ('long_60',   {'disruption_start': 110, 'disruption_end': 170}),
        ]
    elif param_name == 'info_sharing':
        sweep_configs = [
            ('full',    {'info_sharing': 'full'}),
            ('partial', {'info_sharing': 'partial'}),
            ('none',    {'info_sharing': 'none'}),
        ]
    else:
        print(f'Unknown sweep parameter: {param_name}')
        return

    sweep_root = os.path.join('checkpoints', f'sweep_{param_name}')
    _repro_setup(sweep_root, seed)

    all_results = {}
    for name, overrides in sweep_configs:
        print(f'\n{"="*80}')
        print(f'  SWEEP: {param_name} = {name}')
        print(f'{"="*80}')

        _apply_scenario(overrides)
        dis_start = config.DISRUPTIONS[0]['happen_day_1']
        dis_end = config.DISRUPTIONS[0]['end_day_1']
        periods = max(periods_base, dis_end + 30)

        ckpt_dir = os.path.join('checkpoints', f'sweep_{param_name}', name)
        _repro_setup(ckpt_dir, seed)
        drl_eps, curve = train_drl(episodes, periods, ckpt_dir)
        baseline = run_baseline(periods)
        results = evaluate(drl_eps, baseline, periods, dis_start, dis_end, name)
        all_results[name] = {
            'config': overrides,
            'results': {k: {kk: float(vv) for kk, vv in v.items()} for k, v in results.items()},
            'learning_curve_final': curve[-1] if curve else {},
        }

    summary_path = os.path.join('checkpoints', f'sweep_{param_name}', 'summary.json')
    os.makedirs(os.path.dirname(summary_path), exist_ok=True)
    with open(summary_path, 'w') as f:
        json.dump(all_results, f, indent=2)
    print(f'\nSweep summary saved to {summary_path}')

    print(f'\n{"="*80}')
    print(f'  SWEEP SUMMARY: {param_name}')
    print(f'{"="*80}')
    print(f'  {"Setting":<15} | {"Profit Diff":>12} | {"Backlog Diff":>12} | {"Verdict":>10}')
    print(f'  {"-"*15}-+-{"-"*12}-+-{"-"*12}-+-{"-"*10}')
    for name, data in all_results.items():
        dur = data['results'].get('during', {})
        pd_val = dur.get('profit_diff', 0)
        bd = dur.get('sys_bklg_diff', 0)
        verdict = 'PASS' if pd_val > 0 and bd < 0 else 'PARTIAL' if pd_val > 0 or bd < 0 else 'FAIL'
        print(f'  {name:<15} | {pd_val:+12.1f} | {bd:+12.1f} | {verdict:>10}')


def main():
    p = argparse.ArgumentParser(description='Transfer Learning & Scenario Runner')
    p.add_argument('--phase', choices=['train', 'finetune', 'sweep', 'evaluate'],
                   required=True, help='Pipeline phase')
    p.add_argument('--scenario', type=str, default='long_disruption',
                   help=f'Scenario preset: {list(SCENARIO_PRESETS.keys())}')
    p.add_argument('--episodes', type=int, default=None)
    p.add_argument('--periods', type=int, default=None)
    p.add_argument('--source-checkpoint', type=str, default=None,
                   help='Source checkpoint dir for fine-tuning')
    p.add_argument('--checkpoint-dir', type=str, default=None,
                   help='Where to save trained weights')
    p.add_argument('--sweep-param', type=str, default='disruption_length',
                   choices=['disruption_length', 'info_sharing'])
    p.add_argument('--seed', type=int, default=None,
                   help='Random seed (default: config.RANDOM_SEED)')
    args = p.parse_args()

    if args.scenario in SCENARIO_PRESETS:
        _apply_scenario(SCENARIO_PRESETS[args.scenario])
    periods = args.periods or SCENARIO_PRESETS.get(args.scenario, {}).get('periods', 300)
    episodes = args.episodes or getattr(config, 'EVAL_TRAIN_EPISODES', 45)
    dis_start = config.DISRUPTIONS[0]['happen_day_1']
    dis_end = config.DISRUPTIONS[0]['end_day_1']
    ckpt_dir = args.checkpoint_dir or os.path.join('checkpoints', args.scenario)

    if args.phase == 'sweep':
        print(f'Phase: SWEEP over "{args.sweep_param}"')
        run_sweep(args.sweep_param, episodes, periods, args.seed)
        return 0

    if args.phase == 'train':
        print(f'Phase: TRAIN from scratch on "{args.scenario}"')
        print(f'  Episodes={episodes}, Periods={periods}, Info={config.INFO_SHARING_SCENARIO}')
        print(f'  Disruption: {dis_start}-{dis_end}')
        _repro_setup(ckpt_dir, args.seed)
        drl_eps, _ = train_drl(episodes, periods, ckpt_dir)
        baseline = run_baseline(periods)
        evaluate(drl_eps, baseline, periods, dis_start, dis_end, args.scenario)

    elif args.phase == 'finetune':
        src = args.source_checkpoint
        if not src:
            print('ERROR: --source-checkpoint required for finetune phase', file=sys.stderr)
            return 1
        print(f'Phase: FINE-TUNE from "{src}" on "{args.scenario}"')
        print(f'  Episodes={episodes}, Periods={periods}, Info={config.INFO_SHARING_SCENARIO}')
        _repro_setup(ckpt_dir, args.seed)
        drl_eps, _ = train_drl(episodes, periods, ckpt_dir, source_checkpoint=src)
        baseline = run_baseline(periods)
        evaluate(drl_eps, baseline, periods, dis_start, dis_end, f'{args.scenario}(ft)')

    elif args.phase == 'evaluate':
        eval_out = ckpt_dir + '_eval'
        config.TRANSFER_CHECKPOINT_DIR = ckpt_dir
        print(f'Phase: EVALUATE checkpoint "{ckpt_dir}" on "{args.scenario}"')
        _repro_setup(eval_out, args.seed)
        drl_eps, _ = train_drl(1, periods, eval_out, source_checkpoint=ckpt_dir)
        baseline = run_baseline(periods)
        evaluate(drl_eps, baseline, periods, dis_start, dis_end, f'{args.scenario}(eval)')

    return 0


if __name__ == '__main__':
    sys.exit(main())
