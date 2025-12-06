import pandas as pd
import numpy as np
import re

file_path = "NHL Draft - 2000-2020 new.xlsx"
all_sheets = pd.read_excel(file_path, sheet_name=None, header=0)

forwards_list = []
defencemen_list = []
goalies_list = []

def safe_num(df, col):
    if col in df.columns:
        return pd.to_numeric(df[col], errors='coerce').fillna(0)
    else:
        return 0

def gp_threshold_factor(gp_series, threshold=20):
    """
    Sliding scale for games played:
    - Below threshold: GP_factor = GP / threshold
    - At or above threshold: GP_factor = 1
    Ensures very low GP are penalized immediately.
    """
    factor = gp_series / threshold
    factor = factor.clip(upper=1)
    return factor

for sheet_name, df in all_sheets.items():
    print(f"Processing: {sheet_name}")

    df.columns = df.columns.str.strip()

    # Extract draft year
    match = re.search(r"\b(19|20)\d{2}\b", sheet_name)
    if match:
        draft_year = int(match.group(0))
        df["Draft Year"] = draft_year
    else:
        df["Draft Year"] = np.nan

    if "Pos" not in df.columns:
        print(f"Skipping sheet {sheet_name}: no 'Pos' column")
        continue

    # Convert core stats
    for col in ["G", "A", "PTS", "GP", "+/-", "PointShares"]:
        df[col] = safe_num(df, col)

    df["GP"] = df["GP"].replace(0, np.nan)

    # Per-game stats
    df["GPG"] = (df["G"] / df["GP"]).fillna(0)
    df["APG"] = (df["A"] / df["GP"]).fillna(0)
    df["PPG"] = (df["PTS"] / df["GP"]).fillna(0)
    df["PlusMinusPG"] = (df["+/-"] / df["GP"]).fillna(0)

    # Position slices
    forwards = df[df["Pos"].isin(["C", "LW", "RW"])].copy()
    defence = df[df["Pos"].isin(["D"])].copy()
    goalies = df[df["Pos"].isin(["G"])].copy()

    # FORWARDS
    if not forwards.empty:
        gp_factor = gp_threshold_factor(forwards["GP"], threshold=20)
        forwards["WeightedScore"] = (
            0.50 * forwards["PointShares"] +
            0.20 * forwards["PPG"] +
            0.125 * forwards["GPG"] +
            0.125 * forwards["APG"] +
            0.050 * forwards["PlusMinusPG"]
        ) * gp_factor
        forwards_list.append(forwards)

    # DEFENCEMEN
    if not defence.empty:
        gp_factor = gp_threshold_factor(defence["GP"], threshold=20)
        defence["WeightedScore"] = (
            0.55 * defence["PointShares"] +
            0.15 * defence["PPG"] +
            0.10 * defence["GPG"] +
            0.10 * defence["APG"] +
            0.10 * defence["PlusMinusPG"]
        ) * gp_factor
        defencemen_list.append(defence)

    # GOALIES
    if not goalies.empty:
        for col in ["SV%", "GAA"]:
            if col in goalies.columns:
                goalies[col] = pd.to_numeric(goalies[col], errors="coerce").fillna(0)
            else:
                goalies[col] = 0

        gp_factor = gp_threshold_factor(goalies["GP"], threshold=20)
        goalies["WeightedScore"] = (
            0.40 * goalies["SV%"] +
            0.10 * (1 / (goalies["GAA"] + 1)) +
            0.50 * goalies["PointShares"]
        ) * gp_factor
        goalies_list.append(goalies)

# SAVE OUTPUT
if forwards_list:
    pd.concat(forwards_list, ignore_index=True).to_csv("forwards_weighted.csv", index=False)
if defencemen_list:
    pd.concat(defencemen_list, ignore_index=True).to_csv("defencemen_weighted.csv", index=False)
if goalies_list:
    pd.concat(goalies_list, ignore_index=True).to_csv("goalies_weighted.csv", index=False)

print("Done! Weighted scores adjusted with GP threshold sliding scale.")
