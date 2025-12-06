import pandas as pd
import numpy as np
from dash import Dash, html, dcc, Input, Output
import plotly.graph_objects as go

# ---------------------------
# LOAD DATA (exclude goalies)
# ---------------------------
df_forwards = pd.read_csv("raw/forwards_weighted.csv")
df_defense = pd.read_csv("raw/defencemen_weighted.csv")
# Standardize columns
for df_tmp in [df_forwards, df_defense]:
    df_tmp.rename(columns={"WeightedScore": "Player Success Index"}, inplace=True)
    df_tmp["Draft Year"] = pd.to_numeric(df_tmp["Draft Year"], errors="coerce")
    df_tmp["Overall"] = pd.to_numeric(df_tmp["Overall"], errors="coerce")
    if "Draft Round" not in df_tmp.columns:
        df_tmp["Draft Round"] = ((df_tmp["Overall"] - 1) // 31 + 1)
    df_tmp["Draft Round"] = pd.to_numeric(df_tmp["Draft Round"], errors="coerce")

df = pd.concat([df_forwards, df_defense], ignore_index=True)  # Only forwards & defense

# ---------------------------
# EXPECTED VALUE / FREQUENCY ADJUSTMENT
# ---------------------------
df['Played'] = df['GP'] > 0  # True if the player actually played NHL games

pick_counts = df.groupby('Overall')['Player'].count().rename('TotalDrafted')
played_counts = df.groupby('Overall')['Played'].sum().rename('PlayersPlayed')

df = df.merge(pick_counts, on='Overall')
df = df.merge(played_counts, on='Overall')

df['Scaled_PSI'] = df['Player Success Index'] * (df['PlayersPlayed'] / df['TotalDrafted'])

min_psi = df['Scaled_PSI'].min()
max_psi = df['Scaled_PSI'].max()
df['PSI_1_10'] = 1 + 9 * (df['Scaled_PSI'] - min_psi) / (max_psi - min_psi)

position_colors = {'C': 'blue', 'LW': 'green', 'RW': 'red', 'D': 'orange'}

# ---------------------------
# INIT DASH APP
# ---------------------------
app = Dash(__name__)
server = app.server

# ---------------------------
# PREPARE EUROPEAN VS NORTH AMERICAN DATA
# ---------------------------
def nat_group(n):
    if n in ["CAN", "USA"]:
        return "North American"
    else:
        return "European"

df["Region"] = df["Nat."].apply(nat_group)

# ---------------------------
# FUNCTION: MAKE REGION COUNT CHART
# ---------------------------
def make_region_count_chart(filtered_df):
    df_r1 = filtered_df[filtered_df["Draft Round"] == 1]

    region_by_year = (
        df_r1.groupby(["Draft Year", "Region"])
        .size()
        .reset_index(name="Count")
    )

    fig = go.Figure()
    for region in region_by_year["Region"].unique():
        df_region = region_by_year[region_by_year["Region"] == region]
        fig.add_trace(go.Bar(
            x=df_region["Draft Year"],
            y=df_region["Count"],
            name=region
        ))

    fig.update_layout(
        title="Finnish Players Drafted in Round 1 2000-2020 (Count)",
        xaxis_title="Draft Year",
        yaxis_title="Number of Players",
        barmode='stack',
        title_x=0.5,
        legend=dict(x=1.05, y=1)
    )

    return fig

# ---------------------------
# APP LAYOUT
# ---------------------------
app.layout = html.Div(style={"padding": "20px"}, children=[
    html.H2("Player Success Analysis Tool for NHL Draft Data (2000–2020)",
            style={"textAlign": "center"}),
    html.P("Evaluation of player performance and value of draft position",
           style={"textAlign": "center", "fontSize": 14}),

    html.Div(style={"display": "flex", "gap": "15px", "margin-bottom": "20px", "flex-wrap": "wrap"}, children=[
        dcc.Dropdown(
            id="year-filter",
            options=[{"label": str(y), "value": y} for y in sorted(df["Draft Year"].dropna().unique())] +
                    [{"label": "All Years", "value": "all"}],
            value="all",
            style={"width": "200px"},
            placeholder="Select Year"
        ),
        dcc.Dropdown(
            id="team-filter",
            options=[{"label": t, "value": t} for t in sorted(df["Team"].dropna().unique())],
            multi=True,
            placeholder="Filter by team",
            style={"width": "200px"}
        ),
        dcc.Dropdown(
            id="country-filter",
            options=[{"label": c, "value": c} for c in sorted(df["Nat."].dropna().unique())],
            multi=True,
            placeholder="Filter by nationality",
            style={"width": "200px"}
        ),
        dcc.Input(
            id="overall-filter",
            type="number",
            min=1,
            max=int(df["Overall"].max()),
            placeholder="Filter by Overall Pick",
            style={"width": "200px"}
        ),
    ]),

    # ---------------------------
    # Region count chart
    # ---------------------------
    dcc.Graph(id="region-over-time", figure=make_region_count_chart(df)),

    dcc.Graph(id="bar-chart"),
    dcc.Graph(id="heatmap-chart"),
    dcc.Graph(id="scatter-chart")
])

# ---------------------------
# CALLBACK
# ---------------------------
@app.callback(
    Output("region-over-time", "figure"),
    Output("bar-chart", "figure"),
    Output("heatmap-chart", "figure"),
    Output("scatter-chart", "figure"),
    Input("year-filter", "value"),
    Input("team-filter", "value"),
    Input("country-filter", "value"),
    Input("overall-filter", "value"),
    Input("scatter-chart", "clickData")
)
def update_charts(selected_year, selected_teams, selected_countries, selected_overall, clicked_player):
    filtered = df.copy()

    if selected_year != "all":
        filtered = filtered[filtered["Draft Year"] == int(selected_year)]
    if selected_teams:
        filtered = filtered[filtered["Team"].isin(selected_teams)]
    if selected_countries:
        filtered = filtered[filtered["Nat."].isin(selected_countries)]
    if selected_overall:
        filtered = filtered[filtered["Overall"] == selected_overall]

    # ---------------------------
    # UPDATE REGION COUNT CHART
    # ---------------------------
    region_fig = make_region_count_chart(filtered)

    # ---------------------------
    # BAR CHART
    # ---------------------------
    if selected_year == "all":
        bar_data = df.groupby("Overall").agg(
            avg_psi=('PSI_1_10', 'mean'),
            TotalDrafted=('TotalDrafted', 'first'),
            PlayersPlayed=('PlayersPlayed', 'first')
        ).reset_index()
    else:
        bar_data = filtered.groupby("Overall").agg(
            avg_psi=('PSI_1_10', 'mean'),
            TotalDrafted=('TotalDrafted', 'first'),
            PlayersPlayed=('PlayersPlayed', 'first')
        ).reset_index()

    bar_fig = go.Figure()
    bar_fig.add_trace(go.Bar(
        x=bar_data["Overall"],
        y=bar_data["avg_psi"],
        marker_color='skyblue',
        name="Average PSI",
        hovertemplate="Draft Pick: %{x}<br>Average PSI: %{y:.2f}<extra></extra>"
    ))
    bar_fig.add_trace(go.Bar(
        x=bar_data["Overall"],
        y=bar_data["PlayersPlayed"] / bar_data["TotalDrafted"],
        marker_color='lightcoral',
        name="Fraction Played",
        yaxis='y2',
        hovertemplate="Draft Pick: %{x}<br>Fraction Played: %{y:.2f}<extra></extra>"
    ))
    bar_fig.update_layout(
        title={'text': "Player Success Index and Participation by Draft Pick", 'x': 0.5},
        annotations=[dict(
            x=0.56,
            y=1.05,
            xref='paper',
            yref='paper',
            text="Estimated performance and participation rates for each overall draft pick (2000–2020)",
            showarrow=False,
            font=dict(size=12, color='gray'),
            xanchor='center',
            yanchor='bottom'
        )],
        xaxis_title="Overall Draft Pick",
        yaxis_title="Player Success Index (1-10)",
        yaxis2=dict(overlaying='y', side='right', title='Fraction of Players Played'),
        barmode='overlay',
        legend=dict(x=1.05, y=1, traceorder="normal")
    )

    # ---------------------------
    # HEATMAP
    # ---------------------------
    max_round = int(df["Draft Round"].max())
    max_pick = int(df["Overall"].max())
    heat_matrix = np.full((max_round, max_pick), np.nan)
    heat_text = np.full((max_round, max_pick), "", dtype=object)

    if selected_year == "all":
        heat_source = df.groupby("Overall")["PSI_1_10"].mean().reset_index()
        for _, row in heat_source.iterrows():
            p = int(row["Overall"]) - 1
            r = ((p) // 31)
            heat_matrix[r, p] = row['PSI_1_10']
            heat_text[r, p] = f"Draft Pick: {p+1}<br>Average PSI: {row['PSI_1_10']:.2f}"
    else:
        for _, row in filtered.iterrows():
            r = int(row["Draft Round"]) - 1
            p = int(row["Overall"]) - 1
            player = row.get("Player", "")
            pos = row.get("Pos", "")
            psi = row["PSI_1_10"]
            gp = int(row["GP"]) if not pd.isna(row["GP"]) else ""
            nat = row.get("Nat.", "")
            year = int(row["Draft Year"])
            heat_matrix[r, p] = psi
            heat_text[r, p] = (
                f"Player: {player} ({pos})<br>"
                f"Draft Year: {year}<br>"
                f"Draft Round: {r+1}<br>"
                f"Overall Pick: {p+1}<br>"
                f"Player Success Index: {psi:.2f}<br>"
                f"Games Played: {gp}<br>"
                f"Nationality: {nat}"
            )

    heat_fig = go.Figure(go.Heatmap(
        z=heat_matrix,
        x=np.arange(1, max_pick + 1),
        y=np.arange(1, max_round + 1),
        text=heat_text,
        hovertemplate="%{text}<extra></extra>",
        colorscale="Viridis"
    ))
    heat_fig.update_layout(
        title={'text': "Value of Pick Position According to Player Success Index", 'x': 0.5},
        annotations=[dict(
            x=0.5,
            y=1.08,
            xref='paper',
            yref='paper',
            text="Shows value of pick according to PSI distribution across draft positions, (2000–2020)",
            showarrow=False,
            font=dict(size=12, color='gray'),
            xanchor='center'
        )],
        xaxis_title="Overall Pick",
        yaxis_title="Draft Round"
    )

    if clicked_player:
        click_overall = clicked_player['points'][0]['x']
        click_round = ((click_overall - 1) // 31 + 1)
        heat_fig.add_trace(go.Scatter(
            x=[click_overall],
            y=[click_round],
            mode="markers",
            marker=dict(color="red", size=12, symbol="star"),
            name="Selected Player"
        ))

    # ---------------------------
    # SCATTER CHART
    # ---------------------------
    scatter_fig = go.Figure()
    for pos in filtered['Pos'].unique():
        pos_data = filtered[filtered['Pos'] == pos]
        scatter_fig.add_trace(go.Scatter(
            x=pos_data['Overall'],
            y=pos_data['PSI_1_10'],
            mode='markers',
            name=pos,
            marker=dict(color=position_colors.get(pos, 'gray'), size=10),
            hovertemplate=(
                "Player: %{customdata[0]}<br>"
                "Draft Year: %{customdata[1]}<br>"
                "Draft Position: %{x}<br>"
                "Player Success Index: %{y:.2f}<br>"
                "Games Played: %{customdata[2]}<br>"
                "Nationality: %{customdata[3]}<extra></extra>"
            ),
            customdata=pos_data[['Player', 'Draft Year', 'GP', 'Nat.']]
        ))

    scatter_fig.update_layout(
        title={'text': "Player Success by Draft Position and Role", 'x': 0.5},
        annotations=[dict(
            x=0.5,
            y=1.08,
            xref='paper',
            yref='paper',
            text="Distribution of PSI for players by position and overall pick, (2000–2020)",
            showarrow=False,
            font=dict(size=12, color='gray'),
            xanchor='center'
        )],
        xaxis_title="Overall Pick",
        yaxis_title="PSI (1-10)",
        width=1400,
        height=800,
    )

    return region_fig, bar_fig, heat_fig, scatter_fig

# ---------------------------
# RUN APP
# ---------------------------
if __name__ == "__main__":
    app.run(debug=True)
