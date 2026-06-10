"""Routing-ladder HC decision makers.

One parameterized subclass of SimpleHCDecisionMaker covering all rungs. The default
configuration replicates the parent's arithmetic EXACTLY (including int() rounding order),
which verify.py checks against the original class trajectory-for-trajectory.

No core simulator code is modified. The stale-order write-off is ACCOUNTING-ONLY: it changes
which on-order quantity the ordering formula counts; it never mutates hc.on_order (removing
entries would crash receive_delivery when the late shipment eventually arrives,
simulator/agent.py:201-202).
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import simulator.decision_maker as dmaker
from simulator.decision import OrderDecision, TreatDecision


class FlexibleHCDecisionMaker(dmaker.SimpleHCDecisionMaker):
    """Parameterized HC decision maker.

    Parameters
    ----------
    split_recipe : 'equally' | 'bytrust'   (rungs a/b; parent-identical arithmetic)
    sharp_p      : None or float — rung (c): split weights are trust**p (sharper redirection)
    writeoff_k   : None or float — rung (c): on-order entries older than k * lead_time(ds)
                   are excluded from the order-amount computation (accounting-only)
    onset_window : None or (start, end) — rung (d): inside the window, override the split with
                   a fixed share to the disrupted DS (oracle onset detection)
    onset_disrupted_ds : agent name string of the disrupted DS (e.g. 'ds_1')
    onset_disrupted_share : share of the order sent to the disrupted DS inside the window
    """

    def __init__(self, hc, split_recipe, sharp_p=None, writeoff_k=None,
                 onset_window=None, onset_disrupted_ds=None, onset_disrupted_share=0.1):
        super().__init__(hc, split_recipe)
        self.sharp_p = sharp_p
        self.writeoff_k = writeoff_k
        self.onset_window = onset_window
        self.onset_disrupted_ds = onset_disrupted_ds
        self.onset_disrupted_share = onset_disrupted_share
        # diagnostics, logged per period by the runner
        self.last_raw_on_order = 0
        self.last_counted_on_order = 0
        self.last_order_amount = 0
        self.last_split = {}

    # ---- hook 1: which on-order quantity the order formula counts -------------------
    def _counted_on_order(self, now):
        raw = sum(o.amount for o in self.hc.on_order)
        self.last_raw_on_order = raw
        if self.writeoff_k is None:
            self.last_counted_on_order = raw
            return raw
        total = 0
        for o in self.hc.on_order:
            lead = self.hc.lead_time_dict.get(o.dst, 2)
            if (now - o.place_time) <= self.writeoff_k * lead:
                total += o.amount
        self.last_counted_on_order = total
        return total

    # ---- hook 2: per-upstream order amounts ------------------------------------------
    # Default modes reproduce the parent's exact expressions (rounding included).
    def _per_upstream_amounts(self, orderAmount, now):
        ups = list(self.hc.upstream_nodes)

        in_onset_window = (
            self.onset_window is not None
            and self.onset_window[0] <= now <= self.onset_window[1])
        if in_onset_window:
            amounts = {}
            bad = self.onset_disrupted_ds
            healthy = [u for u in ups if u != bad]
            bad_amt = int(float(orderAmount) * self.onset_disrupted_share)
            amounts[bad] = bad_amt
            rest = orderAmount - bad_amt
            for u in healthy:
                amounts[u] = int(float(rest) / len(healthy))
            return amounts

        if self.split_recipe == 'equally':
            n = len(ups)
            return {u: int(float(orderAmount) / n) for u in ups}

        if self.split_recipe == 'bytrust':
            if self.sharp_p is None:
                sum_trust = 0
                for u in ups:
                    sum_trust += self.hc.trust[u]
                return {u: int(float(orderAmount * self.hc.trust[u]) / sum_trust)
                        for u in ups}
            weights = {u: self.hc.trust[u] ** self.sharp_p for u in ups}
            sum_w = sum(weights.values())
            if sum_w <= 0:
                n = len(ups)
                return {u: int(float(orderAmount) / n) for u in ups}
            return {u: int(float(orderAmount * weights[u]) / sum_w) for u in ups}

        raise ValueError("Split Order Recipe Is Not Defined")

    # ---- main: faithful copy of SimpleHCDecisionMaker.make_decision with the hooks ---
    def make_decision(self, now):
        totalInv = sum(tempIn.amount for tempIn in self.hc.inventory)
        totalOnOrder = self._counted_on_order(now)
        totalBacklog_non_urgent = self.hc.backlog_non_urgent + self.hc.non_urgent
        totalDemand = self.hc.urgent + totalBacklog_non_urgent

        # update trust (identical to simulator/decision_maker.py:99-131)
        delivery_amnt = {}
        for up_agent in self.hc.upstream_nodes:
            delivery_amnt[up_agent] = 0
        delivery = self.hc.get_history_item(now)['delivery']
        for deliv in delivery:
            delivery_amnt[deliv['src']] += deliv['item'].amount

        for up_agent in self.hc.upstream_nodes:
            recent_ordered = 0.0
            lookback = min(3, now)
            for ht in range(max(1, now - lookback), now):
                if self.hc.is_history_available(ht):
                    for order in self.hc.get_history_item(ht)['order']:
                        if order.dst == up_agent:
                            recent_ordered += order.amount
            avg_expected = recent_ordered / max(1, lookback)
            if avg_expected > 1:
                self.hc.ontime_deliv_rate[up_agent] = min(
                    1.0, delivery_amnt[up_agent] / avg_expected)
            elif hasattr(self.hc, 'on_time_delivery_rate'):
                idx = list(self.hc.upstream_nodes).index(up_agent)
                if idx < len(self.hc.on_time_delivery_rate):
                    self.hc.ontime_deliv_rate[up_agent] = \
                        self.hc.on_time_delivery_rate[idx]

        if self.split_recipe != 'bytrust' or now < 2:
            for up_agent in self.hc.upstream_nodes:
                self.hc.trust[up_agent] = 1
        else:
            for up_agent in self.hc.upstream_nodes:
                self.hc.trust[up_agent] = (1 - self.hc.delta) * self.hc.trust[up_agent] + \
                                          self.hc.delta * self.hc.ontime_deliv_rate[up_agent]

        # treat decision (identical to simulator/decision_maker.py:133-148)
        decisionT = TreatDecision()
        if totalDemand == 0:
            decisionT.non_urgent = 0
            decisionT.urgent = 0
        elif totalInv < totalDemand:
            decisionT.non_urgent = round(
                totalInv * (float(totalBacklog_non_urgent) / totalDemand))
            decisionT.urgent = min(self.hc.urgent,
                                   totalInv - decisionT.non_urgent)
        else:
            decisionT.non_urgent = int(totalBacklog_non_urgent)
            decisionT.urgent = int(self.hc.urgent)
        self.hc.decisions.append(decisionT)

        self.res_inventory = totalInv - decisionT.urgent - decisionT.non_urgent

        # order decision (identical formula; on-order counting + split are the hooks)
        totalBacklog_non_urgent -= decisionT.non_urgent
        orderAmount = max(self.hc.up_to_level -
                          totalOnOrder - self.res_inventory + totalBacklog_non_urgent, 0)
        max_hc_order = max(2.0 * self.hc.demand(now), 120)
        orderAmount = min(orderAmount, max_hc_order)
        self.last_order_amount = orderAmount

        amounts = self._per_upstream_amounts(orderAmount, now)
        self.last_split = dict(amounts)
        for up_agent in self.hc.upstream_nodes:
            decisionO = OrderDecision()
            decisionO.upstream = up_agent
            decisionO.amount = amounts[up_agent]
            self.hc.decisions.append(decisionO)


class LoggingSimpleDS(dmaker.SimpleDSDecisionMaker):
    """SimpleDSDecisionMaker (verbatim logic, simulator/decision_maker.py:198-221)
    that records the order amount it computed, for per-period logging."""

    def __init__(self, ds):
        super().__init__(ds)
        self.last_order_amount = 0

    def make_decision(self, now):
        inventory = self.ds.inventory_level()
        allocated = dmaker.allocate_proportional(self.ds)
        inventory -= allocated
        on_order = sum(o.amount for o in self.ds.on_order)
        backlog = self.ds.backlog_level()
        backlog -= allocated
        order_amount = max(self.ds.up_to_level + backlog - on_order - inventory, 0)
        max_order = max(2.0 * self.ds.predicted_demand, 120)
        order_amount = min(order_amount, max_order)
        self.last_order_amount = order_amount
        num_upstream_nodes = len(self.ds.upstream_nodes)
        for agent in self.ds.upstream_nodes:
            per_up_order = int(float(order_amount) / num_upstream_nodes)
            decision = OrderDecision()
            decision.upstream = agent
            decision.amount = per_up_order
            self.ds.decisions.append(decision)
