# -*- coding: utf-8 -*-
"""Independent audit of value_decomposition_study headline numbers.

Self-contained: reads raw per-period CSVs with pandas only. Does NOT import
anything from routing_study / understanding_study / value_decomposition_study.
"""
import os
import pandas as pd

ROOT = r"C:\Users\aidan\Downloads\Inventory_DRL_MAB-main-20260508T223316Z-3-001\Inventory_DRL_MAB-main\value_decomposition_study\results"

PREFIXES = ["ds1", "ds2", "mn1", "mn2", "hc1", "hc2"]
HOLD = 1.0
BACK = 10.0
DIS_START = 110  # disruption starts at period 110


def load(relpath):
    path = os.path.join(ROOT, relpath)
    df = pd.read_csv(path)
    return df


def duration_for(relpath):
    d = relpath.replace("/", "\\").split("\\")[0]  # top dir, e.g. sat70_d5
    if "_d5" in d:
        return 5
    if "_d17" in d:
        return 17
    return 48


def n_seeds(df):
    return df["seed"].nunique()


def dp_cost(df):
    sub = df[df["period"] >= DIS_START]
    total = 0.0
    for p in PREFIXES:
        total += HOLD * sub[f"{p}_inventory"].sum() + BACK * sub[f"{p}_backlog"].sum()
    return total / n_seeds(df)


def pre_cost(df):
    sub = df[(df["period"] >= 60) & (df["period"] <= 109)]
    total = 0.0
    for p in PREFIXES:
        total += HOLD * sub[f"{p}_inventory"].sum() + BACK * sub[f"{p}_backlog"].sum()
    return total / n_seeds(df)


def during_fill(df, dis_end):
    sub = df[(df["period"] >= DIS_START) & (df["period"] <= dis_end)]
    treated = (sub["hc1_treated_u"].sum() + sub["hc1_treated_nu"].sum()
               + sub["hc2_treated_u"].sum() + sub["hc2_treated_nu"].sum())
    patients = (sub["hc1_patient_u"].sum() + sub["hc1_patient_nu"].sum()
                + sub["hc2_patient_u"].sum() + sub["hc2_patient_nu"].sum())
    return treated / patients


def lost(df):
    sub = df[df["period"] >= 60]
    return (sub["hc1_lost_u"].sum() + sub["hc2_lost_u"].sum()) / n_seeds(df)


def seeds_set(df):
    return sorted(df["seed"].unique().tolist())


def within(computed, claimed, rel_tol=0.002, abs_tol=None):
    if abs_tol is not None:
        return abs(computed - claimed) <= abs_tol
    return abs(computed - claimed) <= rel_tol * abs(claimed)


rows = []
seed_files = []  # (relpath, df) for claim 12


def add(claim_no, claimed_desc, computed_desc, ok):
    rows.append((claim_no, claimed_desc, computed_desc, "PASS" if ok else "FAIL"))


# ---- Claims 1-3: sat50/urgent0 ladder dp-costs ----
for claim_no, fname, claimed in [
    (1, r"sat50\urgent0\ladder_a.csv", 3702034),
    (2, r"sat50\urgent0\ladder_c.csv", 2737448),
    (3, r"sat50\urgent0\ladder_d.csv", 1861007),
]:
    df = load(fname)
    seed_files.append((fname, df))
    c = dp_cost(df)
    add(claim_no, f"dp-cost = {claimed:,}", f"dp-cost = {c:,.1f}", within(c, claimed))

# ---- Claim 4: sat50/urgent0 sat_full_compound_B960 ----
rel = r"sat50\urgent0\sat_full_compound_B960.csv"
df = load(rel)
seed_files.append((rel, df))
c_dp = dp_cost(df)
dis_end = DIS_START - 1 + duration_for(rel)
c_fill = during_fill(df, dis_end)
c_pre = pre_cost(df)
premium = c_pre - 17044
ok4 = (within(c_dp, 766830)
       and c_fill >= 0.999
       and 45000 <= premium <= 55000)
add(4, "dp-cost = 766,830; fill >= 0.999; premium in [45k,55k]",
    f"dp-cost = {c_dp:,.1f}; fill = {c_fill:.5f}; pre-cost = {c_pre:,.1f}; premium = {premium:,.1f}",
    ok4)

# ---- Claim 5 ----
rel = r"sat50\urgent0\sat_buffer_B1440_healthy.csv"
df = load(rel)
seed_files.append((rel, df))
c = dp_cost(df)
add(5, "dp-cost = 1,957,174", f"dp-cost = {c:,.1f}", within(c, 1957174))

# ---- Claim 6: lost, sat50/urgent20 sat_full_compound_B1440 ----
rel = r"sat50\urgent20\sat_full_compound_B1440.csv"
df = load(rel)
seed_files.append((rel, df))
c = lost(df)
add(6, "lost = 505 (+/-2)", f"lost = {c:,.2f}", within(c, 505, abs_tol=2))

# ---- Claim 7: lost, sat50/urgent20 ladder_c ----
rel = r"sat50\urgent20\ladder_c.csv"
df_lc_u20 = load(rel)
seed_files.append((rel, df_lc_u20))
c = lost(df_lc_u20)
add(7, "lost = 1,591 (+/-2)", f"lost = {c:,.2f}", within(c, 1591, abs_tol=2))

# ---- Claim 8: h3b reroute dp-cost, must exceed ladder_c urgent20 dp-cost ----
rel = r"sat50\urgent20\h3b_upstream_reroute.csv"
df = load(rel)
seed_files.append((rel, df))
c_reroute = dp_cost(df)
c_lc = dp_cost(df_lc_u20)
ok8 = within(c_reroute, 5205099) and c_reroute > c_lc
add(8, "dp-cost = 5,205,099 AND > ladder_c(urgent20) dp-cost",
    f"dp-cost = {c_reroute:,.1f}; ladder_c(urgent20) dp-cost = {c_lc:,.1f}", ok8)

# ---- Claim 9: sat30/urgent0 ladder_c vs ladder_a ----
rel_c = r"sat30\urgent0\ladder_c.csv"
rel_a = r"sat30\urgent0\ladder_a.csv"
df_c = load(rel_c)
df_a = load(rel_a)
seed_files.append((rel_c, df_c))
seed_files.append((rel_a, df_a))
cc = dp_cost(df_c)
ca = dp_cost(df_a)
ok9 = within(cc, 7657315) and within(ca, 5132712) and cc > ca
add(9, "ladder_c dp-cost = 7,657,315 AND > ladder_a dp-cost = 5,132,712",
    f"ladder_c dp-cost = {cc:,.1f}; ladder_a dp-cost = {ca:,.1f}", ok9)

# ---- Claim 10 ----
rel = r"sat30\urgent0\sat_buffer_B4800_healthy.csv"
df = load(rel)
seed_files.append((rel, df))
c = dp_cost(df)
add(10, "dp-cost = 3,465,896", f"dp-cost = {c:,.1f}", within(c, 3465896))

# ---- Claim 11: sat70_d5/urgent0 ladder_a vs c, d (no-action-zone) ----
rel_a = r"sat70_d5\urgent0\ladder_a.csv"
rel_c = r"sat70_d5\urgent0\ladder_c.csv"
rel_d = r"sat70_d5\urgent0\ladder_d.csv"
da = load(rel_a)
dc = load(rel_c)
dd = load(rel_d)
ca = dp_cost(da)
cc = dp_cost(dc)
cd = dp_cost(dd)
ok11 = within(ca, 109697) and ca < cc and ca < cd
add(11, "ladder_a dp-cost = 109,697 AND < ladder_c AND < ladder_d",
    f"ladder_a = {ca:,.1f}; ladder_c = {cc:,.1f}; ladder_d = {cd:,.1f}", ok11)

# ---- Claim 12: seeds 11..30 in all files used in claims 1-10 ----
expected = list(range(11, 31))
bad = []
for relp, dfx in seed_files:
    s = seeds_set(dfx)
    if s != expected:
        bad.append(f"{relp}: {s}")
ok12 = len(bad) == 0
add(12, "all claim 1-10 files contain exactly seeds 11..30",
    "all OK" if ok12 else "; ".join(bad), ok12)

# ---- Output ----
print(f"{'#':>2} | {'CLAIMED':<60} | {'COMPUTED':<95} | RESULT")
print("-" * 175)
for n, cl, co, res in rows:
    print(f"{n:>2} | {cl:<60} | {co:<95} | {res}")
print("-" * 175)
n_pass = sum(1 for r in rows if r[3] == "PASS")
verdict = "ALL CLAIMS VERIFIED" if n_pass == len(rows) else "SOME CLAIMS FAILED"
print(f"Overall verdict: {n_pass}/{len(rows)} PASS -> {verdict}")
