import pandas as pd
import requests
from bs4 import BeautifulSoup, Comment
import time
from io import StringIO
import os
import random

# ---------- Config ----------
excel_file = "NHL Draft - 2000-2020 new.xlsx"  # Your draft file
output_folder = "output_csvs"
os.makedirs(output_folder, exist_ok=True)
requests_per_minute = 20
delay = 60 / requests_per_minute  # seconds between requests
# -----------------------------

def fetch_advanced_stats(player_id, player_type='skater'):
    """
    Fetch advanced stats for a player from Hockey Reference.
    Works for both skaters and goalies.
    """
    url = f'https://www.hockey-reference.com/players/{player_id[0]}/{player_id}.html'
    response = requests.get(url)
    
    if response.status_code != 200:
        print(f"Failed to fetch {player_id} ({url})")
        return pd.DataFrame()
    
    soup = BeautifulSoup(response.text, "html.parser")
    
    # Determine table ID
    table_id = 'skater_stats' if player_type == 'skater' else 'goalie_stats'
    table = soup.find('table', id=table_id)

    # Check for table inside comments (Hockey Reference hides some tables in comments)
    if table is None:
        for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
            if table_id in comment:
                commented_soup = BeautifulSoup(comment, "html.parser")
                table = commented_soup.find('table', id=table_id)
                break
    
    if table is None:
        print(f"No stats table found for {player_id}")
        return pd.DataFrame()
    
    # Read table into pandas
    df = pd.read_html(StringIO(str(table)))[0]
    
    # Clean multi-index columns
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [' '.join(col).strip() for col in df.columns.values]
    
    return df

# ---------- Test with one player ----------
xls = pd.ExcelFile(excel_file)
sheet_name = xls.sheet_names[0]
df = pd.read_excel(excel_file, sheet_name=sheet_name)

# Pick the 7th row (index 6)
row = df.iloc[6]
player_id = str(row.iloc[21]).strip()  # adjust column index for player ID

# Determine if skater/goalie (optional: could also be hard-coded)
player_type = 'skater'  # or 'goalie' if you know

# Fetch stats safely with throttling
adv_df = fetch_advanced_stats(player_id, player_type)
time.sleep(delay)  # respect 20 requests/minute

if not adv_df.empty:
    print(f"Advanced stats for {player_id}:")
    print(adv_df)
else:
    print(f"No stats found for {player_id}")

# Optional: save single-player stats
output_path = os.path.join(output_folder, f"{player_id}_stats.csv")
adv_df.to_csv(output_path, index=False)
print(f"Saved stats to {output_path}")
