"""Independent audit of headline numbers from raw per-period CSVs.

Self-contained: uses only pandas/numpy, no repository modules.
"""
import pandas as pd
import numpy as np

BASE = r"C:\Users\aidan\Downloads\Inventory_DRL_MAB-main-20260508T223316Z-3-001\Inventory_DRL_MAB-main"

AGENTS = ["ds1", "ds2", "mn1", "mn2", "hc1", "hc2"]

FILES = {
    "h3b_u0": BASE + r"\value_decomposition_study\results\slack\urgent0\h3b_upstream_reroute.csv",
    "d_oracle_u0": BASE + r"\value_decomposition_study\results\slack\urgent0\d_oracle.csv",
    "h4_u0": BASE + r"\value_decomposition_study\results\slack\urgent0\h4_ceiling.csv",
    "alloc_u0": BASE + r"\understanding_study\results\urgent0\alloc_prio_hc1.csv",
    "c_u0": BASE + r"\routing_study\results\urgent0\c.csv",
    "h3_u0": BASE + r"\value_decomposition_study\results\slack\urgent0\h3_detect_reroute.csv",
    "h2_u0": BASE + r"\value_decomposition_study\results\slack\urgent0\h2_buffer_B600_d.csv",
    "h3b_u20": BASE + r"\value_decomposition_study\results\slack\urgent20\h3b_upstream_reroute.csv",
    "alloc_u20": BASE + r"\understanding_study\results\urgent20\alloc_prio_hc1.csv",
}

dfs = {}
load_errors = {}
for k, p in FILES.items():
    try:
        dfs[k] = pd.read_csv(p)
    except Exception as e:
        load_errors[k] = f"{type(e).__name__}: {e}"

def dp_cost(df):
    sub = df[df["period"] >= 110]
    n_seeds = df["seed"].nunique()
    total = 0.0
    for a in AGENTS:
        total += (1.0 * sub[f"{a}_inventory"] + 10.0 * sub[f"{a}_backlog"]).sum()
    return total / n_seeds

def lost_patients(df):
    sub = df[df["period"] >= 60]
    n_seeds = df["seed"].nunique()
    return (sub["hc1_lost_u"].sum() + sub["hc2_lost_u"].sum()) / n_seeds

def glut_peak_excess(df):
    inv_cols = [f"{a}_inventory" for a in AGENTS]
    by_period = df.groupby("period")[inv_cols].mean()  # mean over seeds per period
    system = by_period.sum(axis=1)
    pre_mean = system.loc[(system.index >= 60) & (system.index <= 109)].mean()
    peak = system.loc[system.index >= 158].max()
    return peak - pre_mean

def max_abs_diff(df1, df2):
    shared = [c for c in df1.columns if c in df2.columns and c != "rung"]
    num = [c for c in shared if pd.api.types.is_numeric_dtype(df1[c]) and pd.api.types.is_numeric_dtype(df2[c])]
    if len(df1) != len(df2):
        return None, f"row count mismatch: {len(df1)} vs {len(df2)}"
    a = df1[num].to_numpy(dtype=float)
    b = df2[num].to_numpy(dtype=float)
    return float(np.max(np.abs(a - b))), f"{len(num)} numeric shared columns compared"

CLAIMS = [
    (1, "h3b_u0", "dp-cost", 294796, 1, dp_cost),
    (2, None, "h3b == d_oracle (max|diff| < 1e-6)", "< 1e-6", None, None),
    (3, "h4_u0", "dp-cost", 284120, 5, dp_cost),
    (4, "alloc_u0", "dp-cost", 1062538, 5, dp_cost),
    (5, "c_u0", "dp-cost", 1209659, 5, dp_cost),
    (6, "h3_u0", "dp-cost", 1238875, 5, dp_cost),
    (7, "h2_u0", "dp-cost", 1303278, 5, dp_cost),
    (8, "h3b_u20", "lost patients", 203, 1, lost_patients),
    (9, "alloc_u20", "lost patients", 445, 1, lost_patients),
    (10, "h3b_u0", "glut peak excess", 478, 5, glut_peak_excess),
    (11, "alloc_u0", "glut peak excess", 2967, 10, glut_peak_excess),
]

rows = []
for num, key, metric, claimed, tol, fn in CLAIMS:
    if num == 2:
        if "h3b_u0" in dfs and "d_oracle_u0" in dfs:
            mad, note = max_abs_diff(dfs["h3b_u0"], dfs["d_oracle_u0"])
            if mad is None:
                rows.append((num, metric, "< 1e-6", note, "FAIL"))
            else:
                status = "PASS" if mad < 1e-6 else "FAIL"
                rows.append((num, metric, "< 1e-6", f"max|diff| = {mad:.3e} ({note})", status))
        else:
            rows.append((num, metric, "< 1e-6", "file load error", "FAIL"))
        continue
    if key not in dfs:
        rows.append((num, f"{key}: {metric}", claimed, f"LOAD ERROR: {load_errors.get(key)}", "FAIL"))
        continue
    val = fn(dfs[key])
    status = "PASS" if abs(val - claimed) <= tol else "FAIL"
    rows.append((num, f"{FILES[key].split(chr(92))[-3]}/{FILES[key].split(chr(92))[-2]}/{FILES[key].split(chr(92))[-1]}: {metric}",
                 f"{claimed:,}", f"{val:,.2f}", status))

# Claim 12: seeds check
expected = set(range(11, 31))
bad = []
for k, df in dfs.items():
    seeds = set(df["seed"].unique())
    if seeds != expected:
        bad.append(f"{k}: {sorted(seeds)}")
if load_errors:
    bad.append(f"unloadable files: {list(load_errors)}")
rows.append((12, "all files: seeds == {11..30} (20 distinct)", "11..30 x9 files",
             "all 9 files have exactly seeds 11..30" if not bad else "; ".join(bad),
             "PASS" if not bad else "FAIL"))

print(f"{'#':>2} | {'Metric / file':<70} | {'Claimed':>12} | {'Computed':<55} | Result")
print("-" * 160)
for r in rows:
    print(f"{r[0]:>2} | {str(r[1]):<70} | {str(r[2]):>12} | {str(r[3]):<55} | {r[4]}")

overall = all(r[4] == "PASS" for r in rows)
print()
print("OVERALL:", "PASS" if overall else "FAIL")
if load_errors:
    print("Files not verifiable:", load_errors)
