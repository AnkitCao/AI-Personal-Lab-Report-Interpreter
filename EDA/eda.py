"""
eda.py

Basic exploratory data analysis on the final database
(../Data/health_interpreter.db). Descriptive statistics + a handful of
charts, kept simple on purpose -- this is a sanity check on the data,
not a deliverable in itself.

Run (from the EDA/ folder):
    python eda.py

Outputs:
    summary_stats.txt   -- descriptive statistics, plain text
    chart_*.png          -- a few charts
"""

import sqlite3
import pandas as pd
import matplotlib.pyplot as plt

DB_PATH = "../Data/health_interpreter.db"

conn = sqlite3.connect(DB_PATH)
lab = pd.read_sql("SELECT * FROM app_lab_results", conn)
enc = pd.read_sql("SELECT * FROM app_encounters", conn)
conn.close()

lines = []


def log(text=""):
    print(text)
    lines.append(text)


# =========================
# 1. Descriptive statistics
# =========================

log("=== app_lab_results: shape ===")
log(f"{lab.shape[0]} rows x {lab.shape[1]} columns")

log("\n=== value_num: overall descriptive stats ===")
log(lab["value_num"].describe().to_string())

log("\n=== rows per lab_group ===")
log(lab["lab_group"].value_counts().to_string())

log("\n=== rows per test_name ===")
log(lab["test_name"].value_counts().to_string())

log("\n=== status distribution ===")
log(lab["status"].value_counts().to_string())

log("\n=== value_num descriptive stats, per test_name ===")
log(lab.groupby("test_name")["value_num"].describe().to_string())

log("\n=== app_encounters: shape ===")
log(f"{enc.shape[0]} rows x {enc.shape[1]} columns")

log("\n=== patient gender distribution (one row per encounter) ===")
log(enc["gender"].value_counts().to_string())

log("\n=== anchor_age descriptive stats ===")
log(enc["anchor_age"].describe().to_string())

log("\n=== lab_record_count per encounter: descriptive stats ===")
log(enc["lab_record_count"].describe().to_string())

log("\n=== abnormal_result_count per encounter: descriptive stats ===")
log(enc["abnormal_result_count"].describe().to_string())

log("\n=== how many encounters have each panel ===")
for col in ["has_cbc", "has_metabolic", "has_lipid", "has_a1c"]:
    log(f"{col}: {enc[col].sum()} / {len(enc)}")

with open("summary_stats.txt", "w") as f:
    f.write("\n".join(lines))

print("\nSaved: summary_stats.txt")


# =========================
# 2. Charts
# =========================

plt.rcParams["figure.dpi"] = 110

# --- chart 1: lab records per lab_group ---
fig, ax = plt.subplots(figsize=(6, 4))
lab["lab_group"].value_counts().plot(kind="bar", ax=ax, color="#4C72B0")
ax.set_title("Lab Records per Panel (lab_group)")
ax.set_xlabel("lab_group")
ax.set_ylabel("count")
plt.tight_layout()
fig.savefig("chart_1_records_per_lab_group.png")
plt.close(fig)

# --- chart 2: status distribution ---
fig, ax = plt.subplots(figsize=(6, 4))
order = ["NORMAL", "HIGH", "LOW", "ABNORMAL", "UNKNOWN"]
lab["status"].value_counts().reindex(order).plot(kind="bar", ax=ax, color="#DD8452")
ax.set_title("Result Status Distribution")
ax.set_xlabel("status")
ax.set_ylabel("count")
plt.tight_layout()
fig.savefig("chart_2_status_distribution.png")
plt.close(fig)

# --- chart 3: patient age distribution (one row per encounter) ---
fig, ax = plt.subplots(figsize=(6, 4))
enc["anchor_age"].plot(kind="hist", bins=20, ax=ax, color="#55A868")
ax.set_title("Patient Age Distribution (per encounter)")
ax.set_xlabel("anchor_age")
plt.tight_layout()
fig.savefig("chart_3_age_distribution.png")
plt.close(fig)

# --- chart 4: abnormal results per encounter ---
fig, ax = plt.subplots(figsize=(6, 4))
enc["abnormal_result_count"].plot(kind="hist", bins=30, ax=ax, color="#C44E52")
ax.set_title("Abnormal Results per Encounter")
ax.set_xlabel("abnormal_result_count")
plt.tight_layout()
fig.savefig("chart_4_abnormal_per_encounter.png")
plt.close(fig)

# --- chart 5: Glucose value distribution with reference range ---
# note: a handful of ICU patients have genuine extreme values (up to 2517
# mg/dL, real hyperglycemic crises, not data errors -- see summary_stats
# for the full range). The x-axis is capped at 400 here just so the
# histogram is readable; the underlying data is untouched.
glucose = lab[lab["test_name"] == "Glucose"]
fig, ax = plt.subplots(figsize=(6, 4))
glucose["value_num"].plot(kind="hist", bins=60, ax=ax, color="#8172B2")
lo, hi = glucose["ref_range_lower"].iloc[0], glucose["ref_range_upper"].iloc[0]
ax.axvline(lo, color="black", linestyle="--", linewidth=1, label=f"ref range [{lo}, {hi}]")
ax.axvline(hi, color="black", linestyle="--", linewidth=1)
ax.set_xlim(0, 400)
n_over = (glucose["value_num"] > 400).sum()
ax.set_title(f"Glucose Value Distribution (x-axis capped at 400;\n{n_over} genuine extreme values above 400 not shown)")
ax.set_xlabel("mg/dL")
ax.legend()
plt.tight_layout()
fig.savefig("chart_5_glucose_distribution.png")
plt.close(fig)

print("Saved 5 charts: chart_1_*.png ... chart_5_*.png")
