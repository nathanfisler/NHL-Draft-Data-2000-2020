import pandas as pd
import numpy as np
import re

file_path = "/Users/tess/Documents/nhl_connector/raw/NHL Draft - 2000-2020 new.xlsx"
all_sheets = pd.read_excel(file_path, sheet_name=None, header=0)

forwards_list = []
defencemen_list = []

def find_col(df, col_name):
    """Return the first column that contains the given base name."""
    matches = [str(c) for c in df.columns if col_name.lower() in str(c).lower()]
    return matches[0] if matches else None

def safe_num_col(df, base):
    col = find_col(df, base)
    if col:
        return pd.to_numeric(df[col], errors="coerce").fillna(0)
    return pd.Series([0] * len(df))

def gp_threshold_factor(gp_series, threshold=20):
    factor = gp_series / threshold
    factor = factor.clip(upper=1)
    return factor

for sheet_name, df in all_sheets.items():
    print(f"Processing: {sheet_name}")

    # Force all column names to strings and strip
    df.columns = df.columns.map(str).str.strip()

    # Strip whitespace from string columns only
    str_cols = df.select_dtypes(include='object').columns
    df[str_cols] = df[str_cols].apply(lambda col: col.str.strip())

    # Extract draft year from sheet name
    match = re.search(r"(19|20)\d{2}", sheet_name)
    df["Draft Year"] = int(match.group(0)) if match else np.nan

    # Detect position column
    pos_col = find_col(df, "Pos")
    if not pos_col:
        print(f"⚠️ Skipping sheet {sheet_name}: No Pos column found")
        continue

    df["Pos"] = df[pos_col].astype(str).str.upper().str.strip()
    df["Pos"] = df["Pos"].str.replace(r"[\s\-]", "", regex=True)
    df["PrimaryPos"] = df["Pos"].str.split("/").str[0]  # first listed position

    # Load core stats dynamically
    df["G"] = safe_num_col(df, "G")
    df["A"] = safe_num_col(df, "A")
    df["PTS"] = safe_num_col(df, "PTS")
    df["GP"] = safe_num_col(df, "GP").replace(0, np.nan)
    df["+/-"] = safe_num_col(df, "+/-")
    df["PointShares"] = safe_num_col(df, "PS")

    # Per-game stats
    df["GPG"] = (df["G"] / df["GP"]).fillna(0)
    df["APG"] = (df["A"] / df["GP"]).fillna(0)
    df["PPG"] = (df["PTS"] / df["GP"]).fillna(0)
    df["PlusMinusPG"] = (df["+/-"] / df["GP"]).fillna(0)

    # --- CLASSIFY PLAYERS BY PRIMARY POSITION ---
    forwards = df[df["PrimaryPos"].isin(["C", "LW", "RW"])].copy()
    defence = df[df["PrimaryPos"] == "D"].copy()

    # --- FORWARDS ---
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

    # --- DEFENCE ---
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

# --- SAVE OUTPUTS SEPARATELY ---
if forwards_list:
    all_forwards = pd.concat(forwards_list, ignore_index=True)
    all_forwards.sort_values(by=["PrimaryPos", "Draft Year", "WeightedScore"], ascending=[True, True, False], inplace=True)
    all_forwards.to_csv("forwards_weighted.csv", index=False)

if defencemen_list:
    all_defencemen = pd.concat(defencemen_list, ignore_index=True)
    all_defencemen.sort_values(by=["Draft Year", "WeightedScore"], ascending=[True, False], inplace=True)
    all_defencemen.to_csv("defencemen_weighted.csv", index=False)

print("✅ Done! Forwards and defencemen saved separately.")
