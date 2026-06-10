"""
r5 Reward Diagnostic Experiment
================================
Tests whether r5 = sign(1 - |beta1|) has a false-positive problem: rewarding
order-action stability when the agent should be responding to a disruption.

Runs with MAB disabled (single equal-weight arm), profit proxy off, and a
moderate 50% disruption. Trains for 200 episodes, then runs 5 eval episodes
with per-period logging. Produces:
  r5_test_results/
    experiment_config.json
    episode_{seed}_DS{i}_r5log.csv  (one per seed × DS agent)
    r5_statistics.csv
    r5_findings.md
    r5_diagnostic.png / .pdf
"""
import os
import sys
import json
import warnings
try:
    from tqdm import tqdm
except ImportError:
    print("tqdm not found — install with: pip install tqdm")
    sys.exit(1)

os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'
warnings.filterwarnings('ignore')

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'Test'))

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from scipy import stats as scipy_stats
import tensorflow as tf

import config
import simulator.simulation_runner as sim_runner
import simulator.decision_maker as dmaker
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'Test'))
from drl_simulation_profile_config import ConfigDrivenProfile

RESULTS_DIR = 'r5_test_results'
CKPT_DIR = os.path.join(RESULTS_DIR, 'checkpoint')
TRAIN_EPISODES = 500
CHECKPOINT_INTERVAL = 50   # save a numbered snapshot every N episodes
EVAL_SEEDS = [42, 123, 256, 789, 1024, 1337, 2048, 4096, 8192, 16384]
DISRUPTION_START = 110
DISRUPTION_END = 157
WARMUP_END = 60


# ---------------------------------------------------------------------------
# Config overrides
# ---------------------------------------------------------------------------

def apply_config_overrides():
    config.MAB_REWARD_ARMS = [[1.0, 1.0, 1.0, 1.0, 1.0, 1.0]]
    config.DRL_EQ1_PROXY_WEIGHT = 0.0
    config.DISRUPTIONS[0]['decrease_factor_1'] = 0.95
    config.INFO_SHARING_SCENARIO = 'full'
    config.TOTAL_EPISODES = TRAIN_EPISODES
    os.makedirs(RESULTS_DIR, exist_ok=True)
    with open(os.path.join(RESULTS_DIR, 'experiment_config.json'), 'w') as f:
        json.dump(config.snapshot_config(), f, indent=2, sort_keys=True)
    # Pre-flight: print effective thesis-faithful config so we can confirm in logs
    print("[config] === THESIS-FAITHFUL OVERNIGHT RUN ===")
    print(f"  layer_type    : {config.DRL_LAYER_TYPE}")
    print(f"  hidden_size   : {config.DRL_HIDDEN_SIZE}  (GRU width same)")
    print(f"  dropout       : {config.DRL_DROPOUT}")
    print(f"  actor_lr      : {config.DRL_ACTOR_LR}  (x {config.DRL_GRU_LR_FACTOR} for GRU)")
    print(f"  critic_lr     : {config.DRL_CRITIC_LR}  (x {config.DRL_GRU_LR_FACTOR} for GRU)")
    print(f"  history_size  : {config.DRL_HISTORY_SIZE}")
    print(f"  info_sharing  : {config.INFO_SHARING_SCENARIO}")
    print(f"  disruption    : magnitude={config.DISRUPTIONS[0]['decrease_factor_1']}, "
          f"window=[{config.DISRUPTIONS[0]['happen_day_1']}, "
          f"{config.DISRUPTIONS[0]['end_day_1']}]")
    print(f"  MAB arms      : single equal-weight {config.MAB_REWARD_ARMS}")
    print(f"  proxy weight  : {config.DRL_EQ1_PROXY_WEIGHT}")
    print(f"  train_episodes: {TRAIN_EPISODES}")
    print(f"  eval_seeds    : {len(EVAL_SEEDS)} seeds")


# ---------------------------------------------------------------------------
# Simulation builder — DS1 as DRL only, DS2 as simple base-stock
# ---------------------------------------------------------------------------

def build_simulation_single_drl():
    """Build simulation with only DS1 as DRL; DS2 uses simple base-stock."""
    profile = ConfigDrivenProfile()
    decision_maker = dmaker.PerAgentDecisionMaker()

    hc_dmakers = []
    for i, hc in enumerate(profile.health_centers):
        recipe = config.HC_ORDER_SPLIT[i] if i < len(config.HC_ORDER_SPLIT) else 'equally'
        hc_dm = dmaker.SimpleHCDecisionMaker(hc, recipe)
        decision_maker.add_decision_maker(hc_dm)
        hc_dmakers.append(hc_dm)

    mn_dmakers = []
    for mn in profile.manufacturers:
        mn_dm = dmaker.SimpleMNDecisionMaker(mn)
        decision_maker.add_decision_maker(mn_dm)
        mn_dmakers.append(mn_dm)

    tf.keras.backend.clear_session()

    drl_dmakers = []
    for i, ds in enumerate(profile.distributors):
        ds_id = f'DS {i + 1}'
        if i == 0:
            ds_dm = dmaker.DRLDSDecisionMaker(
                ds, mn_dmakers, hc_dmakers, profile.time_periods,
                ds_id, config.TOTAL_EPISODES)
            drl_dmakers.append(ds_dm)
        else:
            ds_dm = dmaker.SimpleDSDecisionMaker(ds)
        decision_maker.add_decision_maker(ds_dm)

    runner = sim_runner.SimulationRunner(
        profile.simulation, decision_maker, profile.agent_builder,
        profile.parameterize_sim_agents, profile.add_patient_model,
        profile.add_disruptions)

    return profile.simulation, runner, drl_dmakers


# ---------------------------------------------------------------------------
# Training phase
# ---------------------------------------------------------------------------

def run_episode(runner, drl_dmakers, eps, do_reset):
    for dm in drl_dmakers:
        dm.ds_env.reset()
        dm.episode = eps
    for pr in range(config.TOTAL_PERIODS):
        runner.next_cycle(do_reset)
        do_reset = False
    return True  # next call should do_reset=True


def _save_checkpoint_with_state(drl_dmakers, directory, episode):
    os.makedirs(directory, exist_ok=True)
    for dm in drl_dmakers:
        dm.ds_env.save_checkpoint(directory)
    state = {
        'episode': episode,
        'exploration_rate': float(drl_dmakers[0].ds_env.exploration_rate),
    }
    with open(os.path.join(directory, 'training_state.json'), 'w') as f:
        json.dump(state, f, indent=2)


def phase_train(resume=False):
    curve_path = os.path.join(RESULTS_DIR, 'training_curve.csv')
    start_episode = 0
    existing_curve = []

    if resume and os.path.exists(os.path.join(CKPT_DIR, 'training_state.json')):
        with open(os.path.join(CKPT_DIR, 'training_state.json')) as f:
            state = json.load(f)
        start_episode = int(state.get('episode', 0))
        saved_exploration = float(state.get('exploration_rate', config.DRL_INITIAL_EXPLORATION))
        print(f"\n=== RESUMING TRAINING from episode {start_episode}/{TRAIN_EPISODES} ===")
        if os.path.exists(curve_path):
            existing_curve = pd.read_csv(curve_path).to_dict('records')
    else:
        saved_exploration = config.DRL_INITIAL_EXPLORATION
        print(f"\n=== TRAINING ({TRAIN_EPISODES} episodes) ===")

    if start_episode >= TRAIN_EPISODES:
        print("  Training already complete.")
        return

    config.set_global_seeds(42)
    tf.keras.backend.clear_session()
    simulation, runner, drl_dmakers = build_simulation_single_drl()
    runner._update_patient(0)
    runner._update_agents(0)

    if resume and start_episode > 0:
        for dm in drl_dmakers:
            dm.ds_env.load_checkpoint(CKPT_DIR)
            dm.ds_env.exploration_rate = saved_exploration
            dm.ds_env.current_episode = start_episode

    curve_rows = list(existing_curve)
    do_reset = start_episode > 0

    with tqdm(range(start_episode, TRAIN_EPISODES), desc='Training', unit='ep',
              initial=start_episode, total=TRAIN_EPISODES,
              bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt} eps [{elapsed}<{remaining}]') as pbar:
        for eps in pbar:
            for dm in drl_dmakers:
                dm.ds_env.reset()
                dm.episode = eps
            ep_reward = 0.0
            ep_backlog_sum = 0.0
            for pr in range(config.TOTAL_PERIODS):
                runner.next_cycle(do_reset)
                do_reset = False
                for dm in drl_dmakers:
                    ep_reward += float(dm.ds_env.reward)
                    ep_backlog_sum += float(dm.ds_env.backlog)
            do_reset = True

            for dm in drl_dmakers:
                curve_rows.append({
                    'episode': eps + 1,
                    'ds_id': dm.ds_env.ds_id,
                    'total_reward': round(ep_reward, 4),
                    'mean_backlog': round(ep_backlog_sum / config.TOTAL_PERIODS, 2),
                    'final_backlog': round(float(dm.ds_env.backlog), 2),
                    'exploration_rate': round(float(dm.ds_env.exploration_rate), 6),
                })

            completed = eps + 1
            if completed % CHECKPOINT_INTERVAL == 0:
                snap_dir = os.path.join(RESULTS_DIR, f'checkpoint_ep{completed}')
                _save_checkpoint_with_state(drl_dmakers, snap_dir, completed)
                _save_checkpoint_with_state(drl_dmakers, CKPT_DIR, completed)
                pd.DataFrame(curve_rows).to_csv(curve_path, index=False)
                pbar.write(f"  [ep {completed}] checkpoint saved, curve flushed")

    _save_checkpoint_with_state(drl_dmakers, CKPT_DIR, TRAIN_EPISODES)
    pd.DataFrame(curve_rows).to_csv(curve_path, index=False)
    print(f"  checkpoint saved → {CKPT_DIR}")
    print(f"  training curve → {curve_path}")


# ---------------------------------------------------------------------------
# Eval phase
# ---------------------------------------------------------------------------

def phase_eval():
    print(f"\n=== EVALUATION ({len(EVAL_SEEDS)} episodes) ===")
    all_logs = []
    for seed in tqdm(EVAL_SEEDS, desc='Evaluating', unit='ep',
                     bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt} seeds [{elapsed}<{remaining}]'):
        config.set_global_seeds(seed)
        tf.keras.backend.clear_session()
        simulation, runner, drl_dmakers = build_simulation_single_drl()
        runner._update_patient(0)
        runner._update_agents(0)
        for dm in drl_dmakers:
            dm.ds_env.load_checkpoint(CKPT_DIR)
            dm.ds_env.istest = True
            dm.ds_env.exploration_rate = config.DRL_MIN_EXPLORATION
            dm.ds_env.r5_log_enabled = True
            dm.ds_env.r5_log = []

        # Inline the episode loop so we can capture DS2 backlog each period
        ds2_backlog_log = []
        for dm in drl_dmakers:
            dm.ds_env.reset()
            dm.episode = 0
        do_reset = False
        for pr in range(config.TOTAL_PERIODS):
            runner.next_cycle(do_reset)
            do_reset = False
            if len(simulation.distributors) > 1:
                ds2_backlog_log.append({
                    'period': pr,
                    'seed': seed,
                    'ds2_backlog': simulation.distributors[1].backlog_level(),
                })

        for i, dm in enumerate(drl_dmakers):
            log_df = pd.DataFrame(dm.ds_env.r5_log)
            # Merge DS2 backlog in by period
            if ds2_backlog_log:
                ds2_df = pd.DataFrame(ds2_backlog_log)[['period', 'ds2_backlog']]
                log_df = log_df.merge(ds2_df, on='period', how='left')
            csv_path = os.path.join(RESULTS_DIR, f'episode_{seed}_DS{i+1}_r5log.csv')
            log_df.to_csv(csv_path, index=False)
            all_logs.append(log_df)
            print(f"  seed={seed} DS{i+1}: {len(log_df)} rows → {csv_path}")
    return all_logs


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------

def compute_statistics(all_logs):
    print("\n=== STATISTICS ===")
    df = pd.concat(all_logs, ignore_index=True)
    df['period'] = df['period'].astype(int)

    def phase(p):
        if WARMUP_END <= p < DISRUPTION_START:
            return 'pre'
        elif DISRUPTION_START <= p <= DISRUPTION_END:
            return 'during'
        elif p > DISRUPTION_END:
            return 'post'
        return 'warmup'

    df['phase'] = df['period'].apply(phase)
    results = []

    for ds_id in df['ds_id'].unique():
        sub = df[df['ds_id'] == ds_id].copy()
        pre_bl_mean = sub.loc[sub['phase'] == 'pre', 'ds_backlog'].mean()
        pre_bl_std = sub.loc[sub['phase'] == 'pre', 'ds_backlog'].std()
        bad_thresh = pre_bl_mean + pre_bl_std

        # A. False positive rate
        for ph in ['pre', 'during', 'post']:
            ph_data = sub[sub['phase'] == ph]
            if len(ph_data) == 0:
                continue
            rate = (ph_data['r5'] == 1.0).mean()
            results.append({'ds_id': ds_id, 'stat': 'A_r5_positive_rate',
                            'phase': ph, 'value': round(rate, 4), 'note': ''})

        # B. Slope discrimination
        for ph in ['pre', 'during', 'post']:
            ph_data = sub[sub['phase'] == ph]
            if len(ph_data) == 0:
                continue
            mean_abs_b = ph_data['beta1'].abs().mean()
            std_abs_b = ph_data['beta1'].abs().std()
            results.append({'ds_id': ds_id, 'stat': 'B_mean_abs_beta1',
                            'phase': ph, 'value': round(mean_abs_b, 4), 'note': ''})
            results.append({'ds_id': ds_id, 'stat': 'B_std_abs_beta1',
                            'phase': ph, 'value': round(std_abs_b, 4), 'note': ''})

        # C. Smoking-gun cross-tab (during disruption only)
        dur = sub[sub['phase'] == 'during'].copy()
        if len(dur) > 0:
            dur['bad_state'] = dur['ds_backlog'] > bad_thresh
            for bad in [True, False]:
                for r5_val in [1.0, -1.0, 0.0]:
                    count = ((dur['bad_state'] == bad) & (dur['r5'] == r5_val)).sum()
                    results.append({'ds_id': ds_id, 'stat': 'C_crosstab',
                                    'phase': 'during',
                                    'value': int(count),
                                    'note': f'bad_state={bad},r5={r5_val}'})
            bad_during = dur[dur['bad_state'] == True]
            p_r5_pos_given_bad = (bad_during['r5'] == 1.0).mean() if len(bad_during) > 0 else float('nan')
            results.append({'ds_id': ds_id, 'stat': 'C_P_r5pos_given_bad_during',
                            'phase': 'during', 'value': round(p_r5_pos_given_bad, 4), 'note': ''})
            results.append({'ds_id': ds_id, 'stat': 'C_bad_state_threshold',
                            'phase': 'pre', 'value': round(bad_thresh, 2), 'note': 'pre_mean+1std'})

        # D. Pearson correlation beta1 vs delta_backlog during disruption
        if len(dur) > 1:
            delta_bl = dur['ds_backlog'].diff().dropna()
            beta1_aligned = dur['beta1'].iloc[1:]
            if len(delta_bl) == len(beta1_aligned) and len(delta_bl) >= 3:
                r, p = scipy_stats.pearsonr(beta1_aligned.values, delta_bl.values)
                results.append({'ds_id': ds_id, 'stat': 'D_pearson_r_beta1_delta_backlog',
                                'phase': 'during', 'value': round(r, 4),
                                'note': f'p={p:.4f}'})

        # E. Mean backlog when r5=+1 vs r5=-1 during disruption
        if len(dur) > 0:
            for r5_val, label in [(1.0, 'r5_pos'), (-1.0, 'r5_neg')]:
                subset = dur[dur['r5'] == r5_val]
                mean_bl = subset['ds_backlog'].mean() if len(subset) > 0 else float('nan')
                results.append({'ds_id': ds_id, 'stat': 'E_mean_backlog_by_r5',
                                'phase': 'during', 'value': round(mean_bl, 2),
                                'note': label})

    stats_df = pd.DataFrame(results)
    stats_path = os.path.join(RESULTS_DIR, 'r5_statistics.csv')
    stats_df.to_csv(stats_path, index=False)
    print(f"  statistics saved → {stats_path}")

    _write_findings(stats_df, df)
    return stats_df, df


def _write_findings(stats_df, df):
    lines = ["# r5 Diagnostic Findings\n"]
    lines.append("**Setup:** 2×2×2 topology, 2 DRL agents, MAB off (equal weights), "
                 "profit proxy off, 95% severe disruption (thesis-faithful) (periods 110–157), "
                 "200 training episodes, 5 eval episodes averaged.\n")

    def get_val(ds, stat, ph, note=''):
        row = stats_df[(stats_df['ds_id'] == ds) & (stats_df['stat'] == stat) &
                       (stats_df['phase'] == ph) & (stats_df['note'].str.contains(note, regex=False))]
        return float(row['value'].values[0]) if len(row) > 0 else float('nan')

    for ds_id in sorted(df['ds_id'].unique()):
        lines.append(f"\n## {ds_id}\n")

        # A
        pre_r = get_val(ds_id, 'A_r5_positive_rate', 'pre')
        dur_r = get_val(ds_id, 'A_r5_positive_rate', 'during')
        post_r = get_val(ds_id, 'A_r5_positive_rate', 'post')
        diff = abs(dur_r - pre_r) if not (np.isnan(dur_r) or np.isnan(pre_r)) else float('nan')
        verdict_a = "**CONFIRMS hypothesis**" if diff < 0.15 else "does not confirm hypothesis"
        lines.append(f"**A. False-positive rate** — r5=+1 pre: {pre_r:.2%}, during: {dur_r:.2%}, "
                     f"post: {post_r:.2%}. Difference pre→during: {diff:.2%}. "
                     f"{verdict_a}: r5 {'barely discriminates' if diff < 0.15 else 'does discriminate'} "
                     f"between stable and disruption phases.\n")

        # B
        pre_b = get_val(ds_id, 'B_mean_abs_beta1', 'pre')
        dur_b = get_val(ds_id, 'B_mean_abs_beta1', 'during')
        b_diff = abs(dur_b - pre_b) if not (np.isnan(dur_b) or np.isnan(pre_b)) else float('nan')
        verdict_b = "**CONFIRMS hypothesis**" if b_diff < 0.3 else "does not confirm hypothesis"
        lines.append(f"**B. Slope discrimination** — mean |β₁| pre: {pre_b:.4f}, during: {dur_b:.4f}. "
                     f"Change: {b_diff:.4f}. {verdict_b}: the order slope "
                     f"{'barely changes' if b_diff < 0.3 else 'changes substantially'} during disruption, "
                     f"so r5 {'cannot signal' if b_diff < 0.3 else 'can signal'} the disruption period.\n")

        # C
        p_bad = get_val(ds_id, 'C_P_r5pos_given_bad_during', 'during')
        thresh = get_val(ds_id, 'C_bad_state_threshold', 'pre')
        verdict_c = "**CONFIRMS hypothesis**" if (not np.isnan(p_bad) and p_bad > 0.5) else "does not confirm hypothesis"
        lines.append(f"**C. Smoking-gun cross-tab** — bad-state threshold (backlog): {thresh:.1f}. "
                     f"P(r5=+1 | bad state, during disruption): {p_bad:.2%}. "
                     f"{verdict_c}: r5 {'rewards the agent in a bad state more than half the time' if (not np.isnan(p_bad) and p_bad > 0.5) else 'does not predominantly reward bad states'}.\n")

        # D
        r_val = get_val(ds_id, 'D_pearson_r_beta1_delta_backlog', 'during')
        r_row = stats_df[(stats_df['ds_id'] == ds_id) & (stats_df['stat'] == 'D_pearson_r_beta1_delta_backlog')]
        p_note = r_row['note'].values[0] if len(r_row) > 0 else ''
        verdict_d = "**CONFIRMS hypothesis**" if (not np.isnan(r_val) and abs(r_val) < 0.3) else "does not confirm hypothesis"
        lines.append(f"**D. Pearson correlation β₁ vs Δbacklog (during)** — r = {r_val:.4f} ({p_note}). "
                     f"{verdict_d}: a {'near-zero' if abs(r_val) < 0.3 else 'substantial'} correlation means "
                     f"β₁ is {'not tracking' if abs(r_val) < 0.3 else 'tracking'} the backlog change signal.\n")

        # E
        bl_pos = get_val(ds_id, 'E_mean_backlog_by_r5', 'during', 'r5_pos')
        bl_neg = get_val(ds_id, 'E_mean_backlog_by_r5', 'during', 'r5_neg')
        verdict_e = ("**CONFIRMS hypothesis**"
                     if (not np.isnan(bl_pos) and not np.isnan(bl_neg) and bl_pos >= bl_neg * 0.85)
                     else "does not confirm hypothesis")
        lines.append(f"**E. Reward inconsistency** — mean backlog when r5=+1: {bl_pos:.1f}, "
                     f"when r5=−1: {bl_neg:.1f}. {verdict_e}: "
                     f"{'backlog is similar or higher when r5 fires positive — r5 is not penalizing bad states' if (not np.isnan(bl_pos) and not np.isnan(bl_neg) and bl_pos >= bl_neg * 0.85) else 'backlog is clearly lower when r5 fires positive, meaning r5 is discriminating correctly'}.\n")

    md_path = os.path.join(RESULTS_DIR, 'r5_findings.md')
    with open(md_path, 'w') as f:
        f.writelines(lines)
    print(f"  findings saved → {md_path}")


# ---------------------------------------------------------------------------
# Plots
# ---------------------------------------------------------------------------

def generate_plots(df):
    print("\n=== GENERATING PLOTS ===")
    ds_ids = sorted(df['ds_id'].unique())
    colors_ds = {'DS 1': '#1f77b4', 'DS 2': '#ff7f0e'}
    colors_hc = {'HC 1': '#aec7e8', 'HC 2': '#ffbb78'}
    periods = sorted(df['period'].unique())

    def mean_se(sub, col):
        grouped = sub.groupby('period')[col]
        m = grouped.mean().reindex(periods)
        se = grouped.sem().reindex(periods).fillna(0)
        return m.values, se.values

    fig, axes = plt.subplots(4, 1, figsize=(12, 14), sharex=True)
    fig.suptitle('r5 Diagnostic: Order Stability Reward During Disruption\n'
                 f'({TRAIN_EPISODES}-episode trained agent, 5 eval episodes averaged, '
                 'MAB off, equal weights, 95% severe disruption (thesis-faithful))',
                 fontsize=11, y=0.98)

    def shade_disruption(ax):
        ax.axvspan(DISRUPTION_START, DISRUPTION_END, alpha=0.12, color='red',
                   label='Disruption (110–157)')
        ax.axvline(DISRUPTION_START, color='red', lw=0.8, ls='--', alpha=0.5)
        ax.axvline(DISRUPTION_END, color='red', lw=0.8, ls='--', alpha=0.5)

    # Panel 1: Order actions
    ax = axes[0]
    for ds_id in ds_ids:
        sub = df[df['ds_id'] == ds_id]
        m, se = mean_se(sub, 'order_action')
        ax.plot(periods, m, color=colors_ds[ds_id], label=ds_id, lw=1.5)
        ax.fill_between(periods, m - se, m + se, alpha=0.2, color=colors_ds[ds_id])
    shade_disruption(ax)
    ax.set_ylabel('Order quantity')
    ax.set_title('(1) Order quantity over time')
    ax.legend(loc='upper right', fontsize=8)
    ax.grid(True, alpha=0.3)

    # Panel 2: Beta1 (raw slope)
    ax = axes[1]
    for ds_id in ds_ids:
        sub = df[df['ds_id'] == ds_id]
        m, se = mean_se(sub, 'beta1')
        ax.plot(periods, m, color=colors_ds[ds_id], label=ds_id, lw=1.5)
        ax.fill_between(periods, m - se, m + se, alpha=0.2, color=colors_ds[ds_id])
    ax.axhline(1.0, color='gray', ls='--', lw=1.0, label='β₁ = ±1 threshold')
    ax.axhline(-1.0, color='gray', ls='--', lw=1.0)
    ax.axhline(0.0, color='black', ls=':', lw=0.7, alpha=0.5)
    shade_disruption(ax)
    ax.set_ylabel('β₁ (raw slope)')
    ax.set_title('(2) Rolling order-action slope β₁ — r5 fires +1 when |β₁| < 1')
    ax.legend(loc='upper right', fontsize=8)
    ax.grid(True, alpha=0.3)

    # Panel 3: r5 value
    ax = axes[2]
    for ds_id in ds_ids:
        sub = df[df['ds_id'] == ds_id]
        m, se = mean_se(sub, 'r5')
        ax.plot(periods, m, color=colors_ds[ds_id], label=ds_id, lw=1.5)
        ax.fill_between(periods, m - se, m + se, alpha=0.2, color=colors_ds[ds_id])
    ax.axhline(0.0, color='black', ls=':', lw=0.7, alpha=0.5)
    shade_disruption(ax)
    ax.set_ylabel('r5 value')
    ax.set_ylim(-1.3, 1.3)
    ax.set_title('(3) r5 output (+1 = stable rewarded, −1 = penalised)')
    ax.legend(loc='upper right', fontsize=8)
    ax.grid(True, alpha=0.3)

    # Panel 4: Backlogs
    ax = axes[3]
    ds1_sub = df[df['ds_id'] == ds_ids[0]]
    # DS1 (DRL agent)
    m, se = mean_se(ds1_sub, 'ds_backlog')
    ax.plot(periods, m, color=colors_ds['DS 1'], label='DS 1 (DRL)', lw=1.5)
    ax.fill_between(periods, m - se, m + se, alpha=0.2, color=colors_ds['DS 1'])
    # DS2 (base-stock) — captured directly from simulation
    if 'ds2_backlog' in ds1_sub.columns and ds1_sub['ds2_backlog'].notna().any():
        m2, se2 = mean_se(ds1_sub, 'ds2_backlog')
        ax.plot(periods, m2, color=colors_ds['DS 2'], label='DS 2 (base-stock)', lw=1.5)
        ax.fill_between(periods, m2 - se2, m2 + se2, alpha=0.2, color=colors_ds['DS 2'])
    for hc_col, hc_label, hc_color in [('hc1_backlog', 'HC 1', colors_hc['HC 1']),
                                         ('hc2_backlog', 'HC 2', colors_hc['HC 2'])]:
        m, se = mean_se(ds1_sub, hc_col)
        ax.plot(periods, m, color=hc_color, label=hc_label, lw=1.2, ls='--')
        ax.fill_between(periods, m - se, m + se, alpha=0.15, color=hc_color)
    shade_disruption(ax)
    ax.set_ylabel('Backlog level')
    ax.set_xlabel('Period')
    ax.set_title('(4) DS1 DRL vs DS2 base-stock backlog (solid); HC backlog (dashed)')
    ax.legend(loc='upper left', fontsize=8)
    ax.grid(True, alpha=0.3)

    plt.tight_layout(rect=[0, 0, 1, 0.96])

    png_path = os.path.join(RESULTS_DIR, 'r5_diagnostic.png')
    pdf_path = os.path.join(RESULTS_DIR, 'r5_diagnostic.pdf')
    fig.savefig(png_path, dpi=200, bbox_inches='tight')
    print(f"  plot saved → {png_path}")
    try:
        fig.savefig(pdf_path, bbox_inches='tight')
        print(f"  plot saved → {pdf_path}")
    except PermissionError:
        print(f"  [WARNING] Could not save PDF (file may be open) — PNG saved successfully")
    plt.close(fig)

    # Disruption sanity check
    dur_data = df[df['period'].between(DISRUPTION_START, DISRUPTION_END)]
    pre_data = df[df['period'].between(WARMUP_END, DISRUPTION_START - 1)]
    if len(dur_data) > 0 and len(pre_data) > 0:
        dur_bl = dur_data['ds_backlog'].mean()
        pre_bl = pre_data['ds_backlog'].mean()
        print(f"\n  [sanity] mean DS backlog pre={pre_bl:.1f}, during={dur_bl:.1f}")
        if dur_bl <= pre_bl * 1.05:
            print("  [WARNING] Backlog barely changed during disruption — "
                  "check that disruption config fired correctly.")
        else:
            print("  [OK] Backlog rose during disruption — disruption fired.")


# ---------------------------------------------------------------------------
# Training curve plot
# ---------------------------------------------------------------------------

def generate_training_curve_plot():
    curve_path = os.path.join(RESULTS_DIR, 'training_curve.csv')
    if not os.path.exists(curve_path):
        print("  No training curve data found — skipping plot")
        return
    df = pd.read_csv(curve_path)
    # Rolling smoothing window
    window = max(1, len(df) // 20)

    fig, axes = plt.subplots(3, 1, figsize=(12, 9), sharex=True)
    fig.suptitle(f'Training Curve — DS1 DRL Agent ({TRAIN_EPISODES} episodes, '
                 'MAB off, equal weights, 95% severe disruption (thesis-faithful))', fontsize=11)

    for ds_id in sorted(df['ds_id'].unique()):
        sub = df[df['ds_id'] == ds_id].sort_values('episode')
        color = '#1f77b4' if ds_id == 'DS 1' else '#ff7f0e'

        # Panel 1: total reward
        ax = axes[0]
        ax.plot(sub['episode'], sub['total_reward'], alpha=0.3, color=color, lw=0.8)
        ax.plot(sub['episode'], sub['total_reward'].rolling(window, min_periods=1).mean(),
                color=color, lw=2, label=f'{ds_id} (smooth)')
        ax.set_ylabel('Total reward / episode')
        ax.set_title('(1) Cumulative reward per episode (raw + smoothed)')
        ax.legend(fontsize=8)
        ax.grid(True, alpha=0.3)

        # Panel 2: mean backlog
        ax = axes[1]
        ax.plot(sub['episode'], sub['mean_backlog'], alpha=0.3, color=color, lw=0.8)
        ax.plot(sub['episode'], sub['mean_backlog'].rolling(window, min_periods=1).mean(),
                color=color, lw=2, label=ds_id)
        ax.set_ylabel('Mean DS backlog / episode')
        ax.set_title('(2) Mean DS backlog per episode — should decrease as agent learns')
        ax.legend(fontsize=8)
        ax.grid(True, alpha=0.3)

        # Panel 3: exploration rate
        ax = axes[2]
        ax.plot(sub['episode'], sub['exploration_rate'], color=color, lw=1.5, label=ds_id)
        ax.set_ylabel('Exploration rate')
        ax.set_xlabel('Episode')
        ax.set_title('(3) Exploration rate decay')
        ax.legend(fontsize=8)
        ax.grid(True, alpha=0.3)

    # Mark checkpoint intervals
    for ax in axes:
        for ep in range(CHECKPOINT_INTERVAL, TRAIN_EPISODES + 1, CHECKPOINT_INTERVAL):
            ax.axvline(ep, color='green', lw=0.5, ls=':', alpha=0.5)

    plt.tight_layout()
    png_path = os.path.join(RESULTS_DIR, 'training_curve.png')
    fig.savefig(png_path, dpi=200, bbox_inches='tight')
    try:
        fig.savefig(os.path.join(RESULTS_DIR, 'training_curve.pdf'), bbox_inches='tight')
    except PermissionError:
        pass
    plt.close(fig)
    print(f"  training curve plot → {png_path}")


# ---------------------------------------------------------------------------
# Dead-zone plot
# ---------------------------------------------------------------------------

def generate_deadzone_plot(df=None):
    """β₁ histogram + r5 frequency bar — visualises the structural dead zone."""
    if df is None:
        # Load from saved CSVs if called standalone
        csv_files = [os.path.join(RESULTS_DIR, f)
                     for f in os.listdir(RESULTS_DIR)
                     if f.endswith('_r5log.csv')]
        if not csv_files:
            print("  No eval CSVs found — skipping dead-zone plot")
            return
        df = pd.concat([pd.read_csv(p) for p in csv_files], ignore_index=True)

    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    fig.suptitle('r5 Dead-Zone Analysis: β₁ Distribution vs. ±1 Threshold\n'
                 f'({len(df)} timesteps across {len(df["episode"].unique())} eval episodes)',
                 fontsize=11)

    # --- Left: β₁ histogram ---
    ax = axes[0]
    beta1_vals = df['beta1'].dropna().values
    ax.hist(beta1_vals, bins=50, color='#1f77b4', edgecolor='white', alpha=0.85)
    ax.axvline(1.0, color='red', lw=2, ls='--', label='r5 threshold (β₁ = +1)')
    ax.axvline(-1.0, color='red', lw=2, ls='--', label='r5 threshold (β₁ = −1)')
    ax.axvline(0.0, color='black', lw=1, ls=':', alpha=0.6)

    max_abs = np.abs(beta1_vals).max()
    ax.annotate(f'Max |β₁| = {max_abs:.3f}\n(threshold = 1.0)',
                xy=(max_abs, ax.get_ylim()[1] * 0.5 if ax.get_ylim()[1] > 0 else 1),
                xytext=(0.62, 0.75), textcoords='axes fraction',
                arrowprops=dict(arrowstyle='->', color='darkred'),
                fontsize=9, color='darkred',
                bbox=dict(boxstyle='round,pad=0.3', facecolor='lightyellow', alpha=0.8))

    ax.set_xlabel('β₁ (OLS slope over last 8 order actions)', fontsize=10)
    ax.set_ylabel('Frequency (timesteps)', fontsize=10)
    ax.set_title('(A) β₁ Distribution — all values far from ±1 threshold\n'
                 'r5 fires +1 whenever |β₁| < 1, −1 whenever |β₁| > 1', fontsize=9)
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)

    # Shade the "dead zone" between ±1 lines
    y_top = ax.get_ylim()[1] if ax.get_ylim()[1] > 0 else len(beta1_vals)
    ax.axvspan(-1.0, 1.0, alpha=0.06, color='green', label='r5=+1 zone')
    ax.set_xlim(min(-1.5, beta1_vals.min() - 0.1), max(1.5, beta1_vals.max() + 0.1))

    # --- Right: r5 value bar chart ---
    ax = axes[1]
    r5_counts = df['r5'].value_counts().sort_index()
    all_vals = [-1.0, 0.0, 1.0]
    counts = [int(r5_counts.get(v, 0)) for v in all_vals]
    labels = ['r5 = −1\n(penalised)', 'r5 = 0\n(neutral)', 'r5 = +1\n(rewarded)']
    bar_colors = ['#d62728', '#7f7f7f', '#2ca02c']

    bars = ax.bar(labels, counts, color=bar_colors, edgecolor='white', width=0.5)
    total = sum(counts)
    for bar, count in zip(bars, counts):
        pct = count / total * 100 if total > 0 else 0
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + total * 0.01,
                f'{count}\n({pct:.1f}%)', ha='center', va='bottom', fontsize=10, fontweight='bold')

    ax.set_ylabel('Count (timesteps)', fontsize=10)
    ax.set_title('(B) r5 Value Distribution — r5 = −1 never fires\n'
                 'All non-warmup timesteps receive r5 = +1 (false positive)', fontsize=9)
    ax.set_ylim(0, total * 1.18)
    ax.grid(True, alpha=0.3, axis='y')

    # Annotation box
    neg_pct = counts[0] / total * 100 if total > 0 else 0
    pos_pct = counts[2] / total * 100 if total > 0 else 0
    ax.text(0.97, 0.96,
            f'r5 = +1: {pos_pct:.1f}% of timesteps\n'
            f'r5 = −1: {neg_pct:.1f}% of timesteps\n'
            f'Max |β₁| = {max_abs:.3f}  (threshold = 1.0)',
            transform=ax.transAxes, ha='right', va='top', fontsize=9,
            bbox=dict(boxstyle='round,pad=0.4', facecolor='lightyellow', alpha=0.9))

    plt.tight_layout()
    png_path = os.path.join(RESULTS_DIR, 'r5_deadzone.png')
    pdf_path = os.path.join(RESULTS_DIR, 'r5_deadzone.pdf')
    fig.savefig(png_path, dpi=200, bbox_inches='tight')
    print(f"  dead-zone plot → {png_path}")
    try:
        fig.savefig(pdf_path, bbox_inches='tight')
        print(f"  dead-zone plot → {pdf_path}")
    except PermissionError:
        print(f"  [WARNING] Could not save PDF (file may be open) — PNG saved successfully")
    plt.close(fig)


# ---------------------------------------------------------------------------
# Reward-components plot (all 6 r_i over time)
# ---------------------------------------------------------------------------

_REWARD_META = {
    'r1': ('HC backlog balance (mean over HCs)', '[−3, +1]'),
    'r2': ('Order fulfillment vs demand', '{−1, 0, +1}'),
    'r3': ('Inventory in-band of up-to-level (±2σ)', '{−1, 0, +1}'),
    'r4': ('DS backlog balance', '[−3, +1]'),
    'r5': ('Order-action stability  sign(1−|β₁|)', '{−1, 0, +1}'),
    'r6': ('MN production / demand alignment', '{−1, +1}'),
}


def generate_reward_components_plot(df=None):
    """Plot r1..r6 over time, averaged across eval seeds with ±1 SE bands."""
    if df is None:
        csv_files = [os.path.join(RESULTS_DIR, f)
                     for f in os.listdir(RESULTS_DIR)
                     if f.endswith('_r5log.csv')]
        if not csv_files:
            print("  No eval CSVs found — skipping reward-components plot")
            return
        df = pd.concat([pd.read_csv(p) for p in csv_files], ignore_index=True)

    periods = sorted(df['period'].unique())

    def _mean_se(col):
        g = df.groupby('period')[col]
        m = g.mean().reindex(periods).values
        se = g.sem().reindex(periods).fillna(0).values
        return m, se

    def _phase_means(col):
        pre = df.loc[(df['period'] >= WARMUP_END) & (df['period'] < DISRUPTION_START), col].mean()
        dur = df.loc[(df['period'] >= DISRUPTION_START) & (df['period'] <= DISRUPTION_END), col].mean()
        post = df.loc[df['period'] > DISRUPTION_END, col].mean()
        return pre, dur, post

    n_seeds = df.groupby('period').size().iloc[0] if len(periods) else 0
    fig, axes = plt.subplots(6, 1, figsize=(12, 14), sharex=True)
    fig.suptitle(
        'Reward Components Over Time — DS 1 (DRL) Test Run\n'
        f'({n_seeds} eval seeds averaged, {TRAIN_EPISODES}-episode trained agent, '
        'MAB off, equal weights, 95% severe disruption (thesis-faithful))',
        fontsize=11, y=0.997)

    colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b']

    for i, r in enumerate(['r1', 'r2', 'r3', 'r4', 'r5', 'r6']):
        ax = axes[i]
        intent, rng = _REWARD_META[r]
        m, se = _mean_se(r)
        ax.plot(periods, m, color=colors[i], lw=1.5)
        ax.fill_between(periods, m - se, m + se, color=colors[i], alpha=0.25)
        ax.axhline(0.0, color='black', ls=':', lw=0.7, alpha=0.5)
        ax.axvspan(DISRUPTION_START, DISRUPTION_END, alpha=0.12, color='red',
                   label='Disruption (110–157)' if i == 0 else None)
        ax.axvline(DISRUPTION_START, color='red', lw=0.8, ls='--', alpha=0.5)
        ax.axvline(DISRUPTION_END, color='red', lw=0.8, ls='--', alpha=0.5)

        pre, dur, post = _phase_means(r)
        ax.set_title(
            f'{r}: {intent}   |   range {rng}   |   '
            f'phase mean pre={pre:.2f}, during={dur:.2f}, post={post:.2f}',
            fontsize=9, loc='left')
        ax.set_ylabel(r, fontsize=11)

        arr = df[r].dropna().values
        if len(arr):
            lo, hi = float(np.min(arr)), float(np.max(arr))
            pad = 0.5 if hi == lo else max(0.2, (hi - lo) * 0.15)
            ax.set_ylim(lo - pad, hi + pad)

        ax.grid(True, alpha=0.3)
        if i == 0:
            ax.legend(loc='upper right', fontsize=8)

    axes[-1].set_xlabel('Period', fontsize=11)
    plt.tight_layout(rect=[0, 0, 1, 0.975])

    png_path = os.path.join(RESULTS_DIR, 'reward_components.png')
    pdf_path = os.path.join(RESULTS_DIR, 'reward_components.pdf')
    fig.savefig(png_path, dpi=200, bbox_inches='tight')
    print(f"  reward-components plot → {png_path}")
    try:
        fig.savefig(pdf_path, bbox_inches='tight')
        print(f"  reward-components plot → {pdf_path}")
    except PermissionError:
        print(f"  [WARNING] Could not save PDF (file may be open) — PNG saved successfully")
    plt.close(fig)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--skip-train', action='store_true',
                        help='Skip training, use existing checkpoint for eval+plots only')
    parser.add_argument('--resume', action='store_true',
                        help='Resume training from latest checkpoint in r5_test_results/checkpoint/')
    parser.add_argument('--train-only', action='store_true',
                        help='Train only, skip eval and diagnostic plots')
    args = parser.parse_args()

    print("=== r5 Reward Diagnostic ===")
    apply_config_overrides()

    if args.skip_train:
        print(f"\n=== SKIPPING TRAINING (using checkpoint: {CKPT_DIR}) ===")
    else:
        phase_train(resume=args.resume)
        generate_training_curve_plot()

    if not args.train_only:
        all_logs = phase_eval()
        stats_df, df = compute_statistics(all_logs)
        generate_plots(df)
        generate_deadzone_plot(df)
        generate_reward_components_plot(df)

        # Reward-input variable plots (r1, r2, r3, r4, r6).
        # gen_reward_inputs.py is a standalone script; invoke it as a subprocess
        # so it can run in isolation and from the standalone command line too.
        inputs_script = os.path.join(os.path.dirname(__file__), 'gen_reward_inputs.py')
        if os.path.exists(inputs_script):
            print("\n=== GENERATING REWARD-INPUT PLOTS ===")
            import subprocess
            try:
                subprocess.run([sys.executable, inputs_script], check=True)
            except subprocess.CalledProcessError as e:
                print(f"  [WARNING] gen_reward_inputs.py exited with {e.returncode}")

    print(f"\nDone. All outputs in: {os.path.abspath(RESULTS_DIR)}/")
