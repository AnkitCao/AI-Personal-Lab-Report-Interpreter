import pandas as pd
import random
from collections import defaultdict

# =========================
# 1. File paths
# =========================

LABEVENTS_PATH = "/Users/ankit/Downloads/labevents.csv"
DLAB_PATH = "/Users/ankit/Downloads/d_labitems.csv"
OUTPUT_PATH = "/Users/ankit/Downloads/labevents_sample.csv"
ITEMID_MAP_PATH = "/Users/ankit/Downloads/labevents_sample_itemids.csv"

chunksize = 500_000
n_encounters = 500
random_seed = 42

usecols = [
    "subject_id",
    "hadm_id",
    "itemid",
    "charttime",
    "value",
    "valuenum",
    "valueuom",
    "ref_range_lower",
    "ref_range_upper",
    "flag",
]


# =========================
# 2. Assign each lab a group label
#    Annual checkup style:
#    CBC / METABOLIC / LIPID / A1C
# =========================

def classify_lab(label, fluid, category):
    lab = str(label).lower()
    fluid = str(fluid)
    category = str(category)

    if fluid != "Blood":
        return None

    # Keep Chemistry / Hematology only, drop Blood Gas
    if category not in ("Chemistry", "Hematology"):
        return None

    if (
        "a1c" in lab
        or "glycohemoglobin" in lab
        or "glycated hemoglobin" in lab
    ):
        return "A1C"

    if any(k in lab for k in ["cholesterol", "triglycer", "hdl", "ldl"]):
        return "LIPID"

    # Exclude hemoglobin electrophoresis / abnormal hemoglobin from CBC
    if any(
        k in lab
        for k in [
            "hemoglobin a2",
            "hemoglobin  a",
            "hemoglobin  a1",
            "hemoglobin  a2",
            "hemoglobin  c",
            "hemoglobin  f",
            "hemoglobin  s",
            "hemoglobin c",
            "hemoglobin f",
            "hemoglobin s",
            "hemoglobin h",
            "hemoglobin other",
            "fetal hemoglobin",
            "plasma hemoglobin",
            "carboxyhemoglobin",
            "methemoglobin",
        ]
    ):
        return None

    if any(
        k in lab
        for k in [
            "hemoglobin",
            "hematocrit",
            "platelet count",
            "white blood",
            "red blood cells",
        ]
    ):
        return "CBC"

    if any(
        k in lab
        for k in [
            "glucose",
            "creatinine",
            "sodium",
            "potassium",
            "urea nitrogen",
            "calcium, total",
            "albumin",
            "bilirubin, total",
        ]
    ):
        return "METABOLIC"

    return None


# =========================
# 3. Select itemids from d_labitems
# =========================

d_lab = pd.read_csv(DLAB_PATH)

d_lab["lab_group"] = [
    classify_lab(label, fluid, category)
    for label, fluid, category in zip(
        d_lab["label"], d_lab["fluid"], d_lab["category"]
    )
]

selected_lab_items = d_lab.loc[
    d_lab["lab_group"].notna(),
    ["itemid", "label", "fluid", "category", "lab_group"],
].copy()

selected_lab_items.to_csv(ITEMID_MAP_PATH, index=False)

itemid_to_group = dict(
    zip(selected_lab_items["itemid"], selected_lab_items["lab_group"])
)
selected_itemids = set(itemid_to_group.keys())

print("Selected lab items:")
print(selected_lab_items.sort_values(["lab_group", "label"]).to_string(index=False))
print("\nCounts by group:")
print(selected_lab_items["lab_group"].value_counts().to_string())
print("Saved itemid map:", ITEMID_MAP_PATH)


# =========================
# 4. Pass 1
#    Record which lab groups each encounter has
#    Do not load the full 18GB file into memory
# =========================

# encounter key = (subject_id, hadm_id)
encounter_groups = defaultdict(set)

for i, chunk in enumerate(
    pd.read_csv(
        LABEVENTS_PATH,
        usecols=["subject_id", "hadm_id", "itemid", "valuenum"],
        chunksize=chunksize,
        low_memory=False,
    )
):
    print(f"Pass 1 scanning chunk {i + 1}")

    chunk = chunk[
        chunk["itemid"].isin(selected_itemids)
        & chunk["valuenum"].notna()
        & chunk["hadm_id"].notna()
    ]

    if chunk.empty:
        continue

    chunk["lab_group"] = chunk["itemid"].map(itemid_to_group)

    for (subject_id, hadm_id), groups in (
        chunk.groupby(["subject_id", "hadm_id"])["lab_group"]
        .apply(set)
        .items()
    ):
        encounter_groups[(int(subject_id), int(hadm_id))].update(groups)

print("Encounters with any selected labs:", len(encounter_groups))


# =========================
# 5. Keep encounters with
#    CBC + METABOLIC + (LIPID or A1C)
#    then randomly sample 500 encounters
# =========================

eligible = [
    key
    for key, groups in encounter_groups.items()
    if (
        "CBC" in groups
        and "METABOLIC" in groups
        and ("LIPID" in groups or "A1C" in groups)
    )
]

print("Eligible annual-checkup-style encounters:", len(eligible))

random.seed(random_seed)
selected_encounters = set(
    random.sample(eligible, min(n_encounters, len(eligible)))
)

print("Selected encounters:", len(selected_encounters))
del encounter_groups


# =========================
# 6. Pass 2
#    Write checkup labs for the 500 sampled encounters
# =========================

first_write = True
total_rows = 0

for i, chunk in enumerate(
    pd.read_csv(
        LABEVENTS_PATH,
        usecols=usecols,
        chunksize=chunksize,
        low_memory=False,
    )
):
    print(f"Pass 2 extracting chunk {i + 1}")

    chunk = chunk[
        chunk["itemid"].isin(selected_itemids)
        & chunk["valuenum"].notna()
        & chunk["hadm_id"].notna()
    ]

    if chunk.empty:
        continue

    keys = list(
        zip(chunk["subject_id"].astype(int), chunk["hadm_id"].astype(int))
    )
    keep = [key in selected_encounters for key in keys]
    filtered = chunk.loc[keep]

    if filtered.empty:
        continue

    filtered.to_csv(
        OUTPUT_PATH,
        mode="w" if first_write else "a",
        header=first_write,
        index=False,
    )

    first_write = False
    total_rows += len(filtered)

print("Done!")
print("Saved:", OUTPUT_PATH)
print("Total rows:", total_rows)
print("Encounters:", len(selected_encounters))
print("Patients:", len({sid for sid, _ in selected_encounters}))
