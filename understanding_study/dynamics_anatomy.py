"""E3: period-by-period anatomy of the routing-fixed (rung c) world, vs baseline (rung a).

Pure analysis of routing_study/results/urgent0/{a,c}.csv. Two figures:
  anatomy_hc_layer:  trust, order routing, receipts, on-order raw vs counted (write-off)
  anatomy_ds_layer:  DS backlogs/inventories, up-to targets, DS_disrupted orders vs receipts
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd

RDIR = os.path.join(ROOT, 'routing_study', 'results', 'urgent0')
FDIR = os.path.join(HERE, 'results', 'figures')
DIS = (110, 157)


def m(df, col):
    return df.groupby('period')[col].mean()


def shade(ax, legend=False):
    ax.axvspan(*DIS, alpha=0.12, color='red',
               label='disruption' if legend else None)


def main():
    os.makedirs(FDIR, exist_ok=True)
    a = pd.read_csv(os.path.join(RDIR, 'a.csv'))
    c = pd.read_csv(os.path.join(RDIR, 'c.csv'))

    # ---------------- HC layer ----------------
    fig, axes = plt.subplots(4, 1, figsize=(11, 13), sharex=True)

    ax = axes[0]
    ax.plot(m(c, 'hc2_trust_ds1'), color='#d62728', lw=1.6,
            label='HC_equal trust in DS_disrupted')
    ax.plot(m(c, 'hc2_trust_ds2'), color='#2ca02c', lw=1.6,
            label='HC_equal trust in DS_healthy')
    ax.plot(m(c, 'hc1_trust_ds1'), color='#d62728', lw=1.2, ls='--',
            label='HC_trust trust in DS_disrupted')
    shade(ax, True)
    ax.set_ylabel('Trust')
    ax.set_title("(1) Trust collapses against the dead chain and recovers after "
                 "(rung c, delta'=0.3)", loc='left', fontsize=10)
    ax.legend(fontsize=8); ax.grid(alpha=0.3)

    ax = axes[1]
    ax.plot(m(c, 'hc2_order_to_ds1'), color='#d62728', lw=1.6,
            label='HC_equal orders to DS_disrupted')
    ax.plot(m(c, 'hc2_order_to_ds2'), color='#2ca02c', lw=1.6,
            label='HC_equal orders to DS_healthy')
    ax.plot(m(a, 'hc2_order_to_ds1'), color='gray', lw=1.2, ls=':',
            label='baseline (rung a): orders to DS_disrupted')
    shade(ax)
    ax.set_ylabel('Units / period')
    ax.set_title('(2) Order routing: trust^4 redirects within ~10 periods '
                 '(baseline never does)', loc='left', fontsize=10)
    ax.legend(fontsize=8); ax.grid(alpha=0.3)

    ax = axes[2]
    ax.plot(m(c, 'hc2_deliv_from_ds1'), color='#d62728', lw=1.4,
            label='HC_equal receipts from DS_disrupted')
    ax.plot(m(c, 'hc2_deliv_from_ds2'), color='#2ca02c', lw=1.4,
            label='HC_equal receipts from DS_healthy')
    shade(ax)
    ax.set_ylabel('Units / period')
    ax.set_title('(3) Receipts follow routing with pipeline lag; note the late '
                 'DS_disrupted deliveries after recovery (the glut source)',
                 loc='left', fontsize=10)
    ax.legend(fontsize=8); ax.grid(alpha=0.3)

    ax = axes[3]
    ax.plot(m(c, 'hc2_on_order_raw'), color='#9467bd', lw=1.6,
            label='HC_equal on-order (raw ledger)')
    ax.plot(m(c, 'hc2_on_order_counted'), color='#1f77b4', lw=1.6,
            label='counted by ordering formula (after write-off)')
    shade(ax)
    ax.set_ylabel('Units')
    ax.set_xlabel('Period')
    ax.set_title('(4) The write-off in action: stale pipeline ignored for ordering, '
                 'but still delivers later', loc='left', fontsize=10)
    ax.legend(fontsize=8); ax.grid(alpha=0.3)

    fig.suptitle('Anatomy of the fixed-routing world: HC layer (urgent0, mean over seeds)',
                 fontsize=11)
    plt.tight_layout(rect=[0, 0, 1, 0.985])
    for ext in ('png', 'pdf'):
        fig.savefig(os.path.join(FDIR, f'anatomy_hc_layer.{ext}'),
                    dpi=170, bbox_inches='tight')
    plt.close(fig)

    # ---------------- DS layer ----------------
    fig, axes = plt.subplots(3, 1, figsize=(11, 10), sharex=True)

    ax = axes[0]
    ax.plot(m(c, 'ds1_backlog'), color='#d62728', lw=1.6, label='DS_disrupted backlog')
    ax.plot(m(c, 'ds2_backlog'), color='#2ca02c', lw=1.6, label='DS_healthy backlog')
    ax.plot(m(c, 'ds1_inventory'), color='#d62728', lw=1.2, ls='--',
            label='DS_disrupted inventory')
    ax.plot(m(c, 'ds2_inventory'), color='#2ca02c', lw=1.2, ls='--',
            label='DS_healthy inventory')
    shade(ax, True)
    ax.set_ylabel('Units')
    ax.set_title('(1) Distributor state (rung c)', loc='left', fontsize=10)
    ax.legend(fontsize=8); ax.grid(alpha=0.3)

    ax = axes[1]
    ax.plot(m(c, 'ds1_up_to'), color='#d62728', lw=1.6, label='DS_disrupted up-to target')
    ax.plot(m(c, 'ds2_up_to'), color='#2ca02c', lw=1.6, label='DS_healthy up-to target')
    shade(ax)
    ax.set_ylabel('Units')
    ax.set_title('(2) Up-to targets: the HEALTHY chain\'s target balloons (~900) as it '
                 'absorbs the surge; the dead chain\'s falls with its rerouted demand',
                 loc='left', fontsize=10)
    ax.legend(fontsize=8); ax.grid(alpha=0.3)

    ax = axes[2]
    deliv1 = (m(c, 'hc1_deliv_from_ds1') + m(c, 'hc2_deliv_from_ds1'))
    ax.plot(m(c, 'ds1_order'), color='#d62728', lw=1.6,
            label='DS_disrupted orders placed (to dead MN)')
    ax.plot(deliv1, color='#1f77b4', lw=1.6,
            label='DS_disrupted shipments out (to HCs)')
    ax.plot(m(c, 'ds1_demand'), color='gray', lw=1.2, ls=':',
            label='demand routed to DS_disrupted')
    shade(ax)
    ax.set_ylabel('Units / period')
    ax.set_xlabel('Period')
    ax.set_title('(3) Dead-factory queue: modest during-disruption orders sit at the dead MN '
                 'for up to 48 periods (441k backlog cost); the post-recovery order spike '
                 'feeds the glut', loc='left', fontsize=10)
    ax.legend(fontsize=8); ax.grid(alpha=0.3)

    fig.suptitle('Anatomy of the fixed-routing world: DS layer (urgent0, mean over seeds)',
                 fontsize=11)
    plt.tight_layout(rect=[0, 0, 1, 0.985])
    for ext in ('png', 'pdf'):
        fig.savefig(os.path.join(FDIR, f'anatomy_ds_layer.{ext}'),
                    dpi=170, bbox_inches='tight')
    plt.close(fig)
    print('anatomy figures written to', FDIR)


if __name__ == '__main__':
    main()
