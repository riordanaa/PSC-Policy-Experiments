"""Value-decomposition study: composable policy components.

HC side (subclass FlexibleHCDecisionMaker from routing_study/policies.py):
  RecoveryAwareWriteoffHC  H1: write off a source's stale pipeline ONLY while that source's
                           delivery rate is depressed; count it again once the source revives
                           (kills the double-supply glut).
  DetectRerouteHC          H3: deployable detect-then-reroute. A source is flagged DOWN after
                           w consecutive periods with on-time delivery rate < theta_down;
                           while DOWN its split share is stepped to down_share (rung-d style);
                           it recovers after w_up consecutive periods >= theta_up.

DS side (subclass AllocFlexibleDS from understanding_study/alloc_policies.py — keeps the
pluggable allocation rule):
  ShapedDS                 One class, composable knobs, ALL default off (defaults must be
                           bit-identical to AllocFlexibleDS — gated):
    buffer_b / buffer_window   order-up-to raised by B (always, or only inside a period
                               window — the JIT/oracle pre-build for the ceiling)
    taper_*                  during persistent delivery shortfall, cap orders at the observed
                             delivery rate x taper_m (don't queue futile orders)
    throttle_c               post-shortfall, while clearing own backlog, cap orders at
                             predicted_demand x throttle_c (suppress the recovery spike)
    ss_freeze                during shortfall, cap up-to at its value when the shortfall
                             began (don't chase the inflated target)

All decision logic verbatim from the parents except the labeled knobs. No core simulator
edits anywhere.
"""
import os
import sys
from collections import deque

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import simulator.decision_maker as dmaker
from simulator.decision import OrderDecision
from routing_study.policies import FlexibleHCDecisionMaker
from understanding_study.alloc_policies import AllocFlexibleDS, flexible_allocate


# ---------------------------------------------------------------------------- HC side
class RecoveryAwareWriteoffHC(FlexibleHCDecisionMaker):
    """H1: stale on-order from source X is excluded from the ordering computation only
    while X looks dead (ontime_deliv_rate[X] < revive_theta). Once X delivers again, its
    pipeline is counted in full, so the HC stops double-ordering into the recovery."""

    def __init__(self, hc, revive_theta=0.5, **kw):
        super().__init__(hc, **kw)
        self.revive_theta = revive_theta

    def _counted_on_order(self, now):
        raw = sum(o.amount for o in self.hc.on_order)
        self.last_raw_on_order = raw
        if self.writeoff_k is None:
            self.last_counted_on_order = raw
            return raw
        total = 0
        for o in self.hc.on_order:
            lead = self.hc.lead_time_dict.get(o.dst, 2)
            stale = (now - o.place_time) > self.writeoff_k * lead
            src_dead = self.hc.ontime_deliv_rate.get(o.dst, 1.0) < self.revive_theta
            if stale and src_dead:
                continue            # written off only while the source looks dead
            total += o.amount
        self.last_counted_on_order = total
        return total


class DetectRerouteHC(FlexibleHCDecisionMaker):
    """H3: deployable detect-then-reroute. No oracle: the trigger is the observed on-time
    delivery rate. While a source is flagged DOWN, the split steps to down_share for it
    (healthy sources share the rest); otherwise the normal split applies."""

    def __init__(self, hc, theta_down=0.5, w_down=3, theta_up=0.6, w_up=3,
                 down_share=0.1, **kw):
        super().__init__(hc, **kw)
        self.theta_down = theta_down
        self.w_down = w_down
        self.theta_up = theta_up
        self.w_up = w_up
        self.down_share = down_share
        self._low = {}    # consecutive low-rate periods per source
        self._high = {}   # consecutive ok-rate periods per source (while flagged down)
        self.down = {}    # source -> currently flagged down?
        self.trigger_log = []   # (period, source, 'down'|'up') for diagnostics

    def _update_detector(self, now):
        for up in self.hc.upstream_nodes:
            rate = self.hc.ontime_deliv_rate.get(up, 1.0)
            if not self.down.get(up, False):
                self._low[up] = self._low.get(up, 0) + 1 if rate < self.theta_down else 0
                if self._low[up] >= self.w_down:
                    self.down[up] = True
                    self._high[up] = 0
                    self.trigger_log.append((now, up, 'down'))
            else:
                self._high[up] = self._high.get(up, 0) + 1 if rate >= self.theta_up else 0
                if self._high[up] >= self.w_up:
                    self.down[up] = False
                    self._low[up] = 0
                    self.trigger_log.append((now, up, 'up'))

    def _per_upstream_amounts(self, orderAmount, now):
        self._update_detector(now)
        down_srcs = [u for u in self.hc.upstream_nodes if self.down.get(u, False)]
        ups = list(self.hc.upstream_nodes)
        if down_srcs and len(down_srcs) < len(ups):
            amounts = {}
            down_total = 0
            for u in down_srcs:
                amounts[u] = int(float(orderAmount) * self.down_share / len(down_srcs))
                down_total += amounts[u]
            healthy = [u for u in ups if u not in down_srcs]
            rest = orderAmount - down_total
            for u in healthy:
                amounts[u] = int(float(rest) / len(healthy))
            return amounts
        return super()._per_upstream_amounts(orderAmount, now)


class UpstreamSignalRerouteHC(DetectRerouteHC):
    """H3b: detect-then-reroute on the SHARED UPSTREAM signal instead of downstream
    delivery rate. The HC observes the manufacturers' live machine state
    (num_active_lines) — exactly the 'In production' visibility the thesis's full
    info-sharing scenario grants — and flags a source DOWN while its feeding MN is below
    threshold_frac of nominal capacity. No oracle: the signal is simulator state that an
    info-sharing system would broadcast; it changes AT onset, removing the ~6-period
    stock-cover masking that blinds delivery-rate detectors.

    Wiring: `mn_of_source` {ds_name: mn_agent} is injected post-build by the runner."""

    def __init__(self, hc, threshold_frac=0.5, **kw):
        super().__init__(hc, **kw)
        self.threshold_frac = threshold_frac
        self.mn_of_source = {}    # injected post-build
        self.nominal_lines = None

    def _update_detector(self, now):
        for up, mn in self.mn_of_source.items():
            if self.nominal_lines is None:
                self.nominal_lines = {}
            nominal = self.nominal_lines.setdefault(up, mn.num_active_lines)
            nominal = max(nominal, mn.num_active_lines)
            self.nominal_lines[up] = nominal
            was_down = self.down.get(up, False)
            is_down = mn.num_active_lines < self.threshold_frac * nominal
            self.down[up] = is_down
            if is_down != was_down:
                self.trigger_log.append((now, up, 'down' if is_down else 'up'))


class HeadroomCappedRerouteHC(FlexibleHCDecisionMaker):
    """C1: severity-aware redirect. Rung-c trust^p routing, but the volume sent to any
    SURVIVING source is capped at margin x that source's observed recent delivery rate
    (per-HC, rolling mean over `window` periods). Excess stays with the original split.
    Rationale (H7): sharp redirection overloads a capacity-cut surviving chain (worst
    measured policy at sat30/d48); the surviving MN ramps with orders up to its cap, so
    margin>1 lets the redirect PROBE upward at a controlled rate instead of slamming."""

    def __init__(self, hc, margin=1.3, window=5, **kw):
        super().__init__(hc, **kw)
        self.margin = margin
        self.window = window
        self._recent_deliv = {}   # source -> deque of recent delivery amounts

    def _per_upstream_amounts(self, orderAmount, now):
        amounts = super()._per_upstream_amounts(orderAmount, now)
        # update per-source delivery observations
        deliv = {u: 0.0 for u in self.hc.upstream_nodes}
        for d in self.hc.get_history_item(now)['delivery']:
            deliv[d['src']] = deliv.get(d['src'], 0.0) + d['item'].amount
        for u in self.hc.upstream_nodes:
            dq = self._recent_deliv.setdefault(u, deque(maxlen=self.window))
            dq.append(deliv.get(u, 0.0))
        # cap each source's share at margin x its observed delivery rate; excess goes to
        # the other source(s) proportionally to their uncapped amounts
        ups = list(self.hc.upstream_nodes)
        # the cap binds only on the redirect SURGE: it is floored at the source's equal
        # share of this period's order, so baseline ordering always bootstraps. (First
        # version capped everything at margin x rate + 1 from a cold start of rate=0;
        # the simulator drops orders <= 1 unit, so the system deadlocked at zero flow —
        # caught in tuning by a margin-invariant 94M cost. See LEDGER.)
        def cap_of(u):
            dq = self._recent_deliv[u]
            rate = sum(dq) / max(1, len(dq))
            return max(int(self.margin * rate) + 1,
                       int(float(orderAmount) / max(1, len(ups))))
        capped = {}
        excess = 0
        for u in ups:
            give = min(amounts.get(u, 0), cap_of(u))
            excess += amounts.get(u, 0) - give
            capped[u] = give
        if excess > 0:
            room = {u: max(0, cap_of(u) - capped[u]) for u in ups}
            tot_room = sum(room.values())
            if tot_room > 0:
                for u in ups:
                    add = min(room[u], int(excess * room[u] / tot_room))
                    capped[u] += add
            # any residual is not ordered this period; the order formula re-adds it
            # via backlog next period
        return capped


class CapacityAwareRerouteHC(FlexibleHCDecisionMaker):
    """C1 variant 2: cap each source's share at margin x its SHARED CAPACITY signal
    (feeding MN's live active_lines x line_capacity, split across the HCs it serves) —
    the same info-sharing channel as the h3b reroute. Unlike the delivery-observation cap,
    capacity does not depend on our own orders, so it cannot throttle the supplier's ramp.
    mn_of_source wired post-build (as in UpstreamSignalRerouteHC); n_hcs static (=2)."""

    def __init__(self, hc, margin=1.1, n_hcs=2, **kw):
        super().__init__(hc, **kw)
        self.margin = margin
        self.n_hcs = n_hcs
        self.mn_of_source = {}    # injected post-build

    def _per_upstream_amounts(self, orderAmount, now):
        amounts = super()._per_upstream_amounts(orderAmount, now)
        ups = list(self.hc.upstream_nodes)

        def cap_of(u):
            mn = self.mn_of_source.get(u)
            if mn is None:
                return 10 ** 9
            capacity = mn.num_active_lines * mn.line_capacity
            return max(int(self.margin * capacity / self.n_hcs),
                       int(float(orderAmount) / max(1, len(ups))))

        capped = {}
        excess = 0
        for u in ups:
            give = min(amounts.get(u, 0), cap_of(u))
            excess += amounts.get(u, 0) - give
            capped[u] = give
        if excess > 0:
            room = {u: max(0, cap_of(u) - capped[u]) for u in ups}
            tot_room = sum(room.values())
            if tot_room > 0:
                for u in ups:
                    capped[u] += min(room[u], int(excess * room[u] / tot_room))
        return capped


class DiscountWriteoffHC(FlexibleHCDecisionMaker):
    """H1b: instead of writing dead-source stale pipeline off entirely (gamma=0, the
    rung-c behavior that double-orders) or counting it fully (gamma=1, the original
    suppression), count it at a discount gamma — acknowledging it WILL eventually arrive."""

    def __init__(self, hc, gamma=0.5, **kw):
        super().__init__(hc, **kw)
        self.gamma = gamma

    def _counted_on_order(self, now):
        raw = sum(o.amount for o in self.hc.on_order)
        self.last_raw_on_order = raw
        if self.writeoff_k is None:
            self.last_counted_on_order = raw
            return raw
        total = 0.0
        for o in self.hc.on_order:
            lead = self.hc.lead_time_dict.get(o.dst, 2)
            stale = (now - o.place_time) > self.writeoff_k * lead
            total += o.amount * (self.gamma if stale else 1.0)
        self.last_counted_on_order = total
        return total


# ---------------------------------------------------------------------------- DS side
class ShapedDS(AllocFlexibleDS):
    """Composable DS ordering shaping on top of AllocFlexibleDS. All knobs default OFF;
    with defaults this class must be bit-identical to AllocFlexibleDS (gated)."""

    def __init__(self, ds, rule='proportional',
                 buffer_b=0, buffer_window=None,
                 taper_thresh=None, taper_window=5, taper_m=1.0,
                 throttle_c=None,
                 ss_freeze=False, freeze_thresh=0.5,
                 b_elev=0, recovery_dwell=0,
                 prebook_f=None, smooth_cap=None,
                 oo_gamma=None, oo_k=3.0,
                 alloc_alpha=0.2):
        super().__init__(ds, rule)
        self.buffer_b = buffer_b
        self.buffer_window = buffer_window
        self.taper_thresh = taper_thresh
        self.taper_window = taper_window
        self.taper_m = taper_m
        self.throttle_c = throttle_c
        self.ss_freeze = ss_freeze
        self.freeze_thresh = freeze_thresh
        # DS-seat study knobs (all default off -> behavior bit-identical, gated)
        self.b_elev = b_elev                  # state-elevated up-to while MN down + dwell
        self.recovery_dwell = recovery_dwell  # periods of elevation after recovery
        self.prebook_f = prebook_f            # anti-taper: order >= f x demand while down
        self.smooth_cap = smooth_cap          # max |order - last order| per period
        self.oo_gamma = oo_gamma              # stale-pipeline discount (age > oo_k x lead)
        self.oo_k = oo_k
        self.alloc_alpha = alloc_alpha        # smoothing for stateful allocation rules
        self.mn_down = False
        self._dwell_left = 0
        self._mn_nominal = None
        self._last_sent = None
        self._orders = deque(maxlen=max(taper_window, 5))
        self._receipts = deque(maxlen=max(taper_window, 5))
        self._frozen_up_to = None
        self._in_shortfall = False
        self._was_shortfall = False   # for the post-shortfall throttle

    def _recent_fill(self):
        o = sum(self._orders)
        return (sum(self._receipts) / o) if o > 1 else 1.0

    def _update_mn_state(self):
        """Shared upstream signal: down while this DS's MN is below 50% of nominal lines.
        Tracks the post-recovery dwell window for the elevated mode."""
        if getattr(self, 'watch_mn', None) is None:
            return
        nominal = self._mn_nominal or self.watch_mn.num_active_lines
        self._mn_nominal = max(nominal, self.watch_mn.num_active_lines)
        was_down = self.mn_down
        self.mn_down = self.watch_mn.num_active_lines < 0.5 * self._mn_nominal
        if was_down and not self.mn_down:
            self._dwell_left = self.recovery_dwell
        elif not self.mn_down and self._dwell_left > 0:
            self._dwell_left -= 1

    def make_decision(self, now):
        self._update_mn_state()
        receipts = sum(d['item'].amount
                       for d in self.ds.get_history_item(now)['delivery'])
        self._receipts.append(receipts)

        inventory = self.ds.inventory_level()
        allocated = flexible_allocate(self.ds, self.rule, now, ctx=self)
        inventory -= allocated
        if self.oo_gamma is not None:
            on_order = 0.0
            for o in self.ds.on_order:
                lead = self.ds.lead_time_dict.get(o.dst, 2)
                stale = (now - o.place_time) > self.oo_k * lead
                on_order += o.amount * (self.oo_gamma if stale else 1.0)
        else:
            on_order = sum(o.amount for o in self.ds.on_order)
        backlog = self.ds.backlog_level()
        backlog -= allocated

        fill = self._recent_fill()
        shortfall = fill < (self.taper_thresh if self.taper_thresh is not None
                            else self.freeze_thresh)
        if shortfall and not self._in_shortfall:
            self._frozen_up_to = float(self.ds.up_to_level)
        if not shortfall and self._in_shortfall:
            self._was_shortfall = True
        self._in_shortfall = shortfall

        up_to = float(self.ds.up_to_level)
        if self.ss_freeze and self._in_shortfall and self._frozen_up_to is not None:
            up_to = min(up_to, self._frozen_up_to)
        if self.buffer_b:
            in_window = (self.buffer_window is None
                         or self.buffer_window[0] <= now <= self.buffer_window[1])
            if in_window:
                up_to += self.buffer_b
        if self.b_elev and (self.mn_down or self._dwell_left > 0):
            up_to += self.b_elev          # state-dependent (two-regime) base stock

        order_amount = max(up_to + backlog - on_order - inventory, 0)
        max_order = max(2.0 * self.ds.predicted_demand, 120)
        order_amount = min(order_amount, max_order)

        if self.taper_thresh is not None and self._in_shortfall:
            recent_rate = (sum(self._receipts) / max(1, len(self._receipts)))
            order_amount = min(order_amount, recent_rate * self.taper_m)
        if self.throttle_c is not None and self._was_shortfall and backlog > 0:
            order_amount = min(order_amount,
                               self.ds.predicted_demand * self.throttle_c)
        if self.throttle_c is not None and self._was_shortfall and backlog <= 0:
            self._was_shortfall = False   # caught up; throttle disengages

        # Order-taper-toward-failed-source — a DISCRETE pre-registered rule triggered by
        # the shared upstream signal: while down, cap orders at the observed recent
        # delivery rate x mn_taper_m. Detection never feeds a continuous optimizer.
        if getattr(self, 'mn_taper_m', None) is not None and self.mn_down:
            recent_rate = sum(self._receipts) / max(1, len(self._receipts))
            order_amount = min(order_amount, recent_rate * self.mn_taper_m)
        # Prebook (anti-taper): while down, keep ordering at >= f x predicted demand to
        # pre-book recovery production (queued orders fill first when capacity returns)
        if self.prebook_f is not None and self.mn_down:
            order_amount = max(order_amount,
                               min(self.prebook_f * self.ds.predicted_demand, max_order))
        # Order smoothing (bullwhip damping): cap per-period change
        if self.smooth_cap is not None and self._last_sent is not None:
            lo = self._last_sent - self.smooth_cap
            hi = self._last_sent + self.smooth_cap
            order_amount = min(max(order_amount, lo), hi)
            order_amount = max(0, min(order_amount, max_order))
        self._last_sent = order_amount

        self.last_order_amount = order_amount
        self._orders.append(order_amount)
        num_upstream_nodes = len(self.ds.upstream_nodes)
        for agent in self.ds.upstream_nodes:
            per_up_order = int(float(order_amount) / num_upstream_nodes)
            decision = OrderDecision()
            decision.upstream = agent
            decision.amount = per_up_order
            self.ds.decisions.append(decision)
