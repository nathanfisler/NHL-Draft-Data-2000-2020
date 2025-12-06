import pandas as pd
from dash import Dash, html, dcc, Input, Output
import plotly.graph_objects as go

# ---------------------------
# LOAD DATA
# ---------------------------
df_forwards = pd.read_csv("/Users/tess/Documents/nhl_connector/raw/forwards_weighted.csv")
df_defense = pd.read_csv("/Users/tess/Documents/nhl_connector/raw/defencemen_weighted.csv")
df_goalies = pd.read_csv("/Users/tess/Documents/nhl_connector/raw/goalies_weighted.csv")

# Rename WeightedScore to Player Success Index
for df_tmp in [df_forwards, df_defense, df_goalies]:
    df_tmp.rename(columns={"WeightedScore": "Player Success Index"}, inplace=True)
    df_tmp["Draft Year"] = pd.to_numeric(df_tmp["Draft Year"], errors="coerce")

# Concatenate all players
df = pd.concat([df_forwards, df_defense, df_goalies], ignore_index=True)

# ---------------------------
# INIT DASH APP
# ---------------------------
app = Dash(__name__)

# Position colors
position_colors = {
    'C': 'blue',
    'LW': 'green',
    'RW': 'red',
    'D': 'orange',
    'G': 'purple'
}

# ---------------------------
# APP LAYOUT
# ---------------------------
app.layout = html.Div(style={"padding": "20px"}, children=[

    # FILTERS
    html.Div(
        style={
            "display": "flex",
            "gap": "15px",
            "margin-bottom": "20px",
            "flex-wrap": "wrap"
        },
        children=[
            dcc.Dropdown(
                id="year-filter",
                options=
                    [{"label": str(y), "value": y}
                     for y in sorted(df["Draft Year"].dropna().unique())]
                    +
                    [
                        {"label": "2000–2005", "value": "2000_2005"},
                        {"label": "2006–2010", "value": "2006_2010"},
                        {"label": "2011–2015", "value": "2011_2015"},
                        {"label": "2016–2020", "value": "2016_2020"},
                        {"label": "All Years", "value": "all"},
                    ],
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
        ]
    ),

    # Title
    html.H2(id="chart-title", style={"textAlign": "center", "margin-bottom": "10px"}),

    # Chart
    dcc.Graph(id="success-chart")
])

# ---------------------------
# CALLBACK
# ---------------------------
@app.callback(
    Output("success-chart", "figure"),
    Output("chart-title", "children"),
    Input("year-filter", "value"),
    Input("team-filter", "value"),
    Input("country-filter", "value")
)
def update_chart(selected_year, selected_teams, selected_countries):
    filtered = df.copy()

    # ---------------------------
    # APPLY YEAR FILTER (supports: single year, all years, ranges)
    # ---------------------------
    if selected_year != "all":
        if isinstance(selected_year, str) and "_" in selected_year:
            # Range like "2000_2005"
            start, end = selected_year.split("_")
            start, end = int(start), int(end)
            filtered = filtered[
                (filtered["Draft Year"] >= start) &
                (filtered["Draft Year"] <= end)
            ]
        else:
            # Single year
            filtered = filtered[filtered["Draft Year"] == int(selected_year)]

    # Apply team filter
    if selected_teams:
        filtered = filtered[filtered["Team"].isin(selected_teams)]

    # Apply country filter
    if selected_countries:
        filtered = filtered[filtered["Nat."].isin(selected_countries)]

    # Build traces with custom hovertemplate
    traces = []
    for pos in filtered['Pos'].unique():
        pos_data = filtered[filtered['Pos'] == pos]
        traces.append(go.Scatter(
            x=pos_data['Overall'],
            y=pos_data['Player Success Index'],
            mode='markers',
            name=pos,
            marker=dict(color=position_colors.get(pos, 'gray'), size=10),
            hovertemplate=(
                "Player: %{customdata[0]}<br>" +
                "Draft Year: %{customdata[1]}<br>" +
                "Draft Position: %{x}<br>" +
                "Player Success Index: %{y}<br>" +
                "Games Played: %{customdata[2]}<br>" +
                "Nationality: %{customdata[3]}"
        ),
        customdata=pos_data[['Player', 'Draft Year', 'GP', 'Nat.']]
    ))

    # Figure layout
    fig = go.Figure(data=traces)
    fig.update_layout(
        title="Success of NHL Players by Draft Position (2000-2020)",
        xaxis_title="Draft Position",
        yaxis_title="Player Success Index",
        legend_title="Position",
        legend=dict(x=1.02, y=1),
        margin=dict(r=150),
        width=1300,
        height=700
    )

    return fig, "Success of NHL Players by Draft Position (2000-2020)"

# ---------------------------
# RUN APP
# ---------------------------
if __name__ == "__main__":
    app.run(debug=True)
