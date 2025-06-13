# report.py

import os
import pandas as pd
from datetime import datetime, timedelta

import dash
from dash import Dash, dcc, html, dash_table, callback_context
from dash.dependencies import Input, Output, State
from dash.exceptions import PreventUpdate
import plotly.express as px

# ── CONFIGURATION ───────────────────────────────────────────────────────────────

SUCCESS_CSV = "ai_sms_log.csv"
FAILURE_CSV = "ai_sms_failures.csv"
DASH_PORT = 5001

# ── DATA LOADING / PREPARATION ──────────────────────────────────────────────────

def load_and_merge_data():
    """
    1) Read both CSVs using their built-in header.
    2) Lowercase/strip the column names.
    3) Rename any headers with spaces into underscore form.
    4) Ensure exactly these six columns exist:
       ['timestamp','source','lead_name','message_id','message_text','status']
    5) Convert 'timestamp' → datetime and uppercase 'status'.
    """
    # 1) Load successes (these files already have a header row)
    if os.path.isfile(SUCCESS_CSV) and os.path.getsize(SUCCESS_CSV) > 0:
        df_succ = pd.read_csv(SUCCESS_CSV, dtype=str)
        # If the file did not include a 'status' column, we add it
        if "status" not in df_succ.columns.str.lower():
            df_succ["status"] = "SUCCESS"
    else:
        df_succ = pd.DataFrame(
            columns=["timestamp", "source", "lead_name", "message_id", "message_text", "status"]
        )

    # 2) Load failures (these files already have a header row)
    if os.path.isfile(FAILURE_CSV) and os.path.getsize(FAILURE_CSV) > 0:
        df_fail = pd.read_csv(FAILURE_CSV, dtype=str)
        # If they didn’t include a 'status' column, add it
        if "status" not in df_fail.columns.str.lower():
            df_fail["status"] = "FAILED"
    else:
        df_fail = pd.DataFrame(
            columns=["timestamp", "source", "lead_name", "message_id", "message_text", "status"]
        )

    # 3) Concatenate them
    df_all = pd.concat([df_succ, df_fail], ignore_index=True, sort=False)

    # 4) Lowercase and strip whitespace from every column name
    df_all.columns = df_all.columns.str.strip().str.lower()

    # 5) If any column name has a space, explicitly rename it
    #    so that “lead name”→“lead_name”, “message id”→“message_id”, etc.
    rename_map = {}
    if "lead name" in df_all.columns:
        rename_map["lead name"] = "lead_name"
    if "message id" in df_all.columns:
        rename_map["message id"] = "message_id"
    if "message text" in df_all.columns:
        rename_map["message text"] = "message_text"
    if rename_map:
        df_all = df_all.rename(columns=rename_map)

    # 6) Keep only exactly these six columns (drop any extras):
    expected = ["timestamp", "source", "lead_name", "message_id", "message_text", "status"]
    df_all = df_all.loc[:, [c for c in expected if c in df_all.columns]]

    # 7) If any expected column is missing, add it as empty strings
    for col in expected:
        if col not in df_all.columns:
            df_all[col] = ""

    # 8) Convert 'timestamp' into datetime (coerce errors → NaT)
    df_all["timestamp"] = pd.to_datetime(df_all["timestamp"], errors="coerce")

    # 9) Uppercase 'status'
    df_all["status"] = df_all["status"].fillna("failed").str.upper()

    return df_all





# Load once at startup for date picker defaults
df_initial = load_and_merge_data()

# ── DASHBOARD LAYOUT ───────────────────────────────────────────────────────────

external_stylesheets = [
    "https://cdnjs.cloudflare.com/ajax/libs/normalize/8.0.1/normalize.min.css",
    "https://cdnjs.cloudflare.com/ajax/libs/skeleton/2.0.4/skeleton.min.css",
]
app = Dash(__name__, external_stylesheets=external_stylesheets)
server = app.server

app.layout = html.Div(
    style={"margin": "20px", "fontFamily": "Arial"},
    children=[
        html.H2("📊 SMS Success/Failure Dashboard", style={"textAlign": "center"}),

        # ── Summary Banner ───────────────────────────────────────────────
        html.Div(
            id="summary-banner",
            style={
                "display": "flex",
                "justifyContent": "space-between",
                "alignItems": "center",
                "marginBottom": "20px",
            },
            children=[
                html.Div(id="total-rows", style={"fontWeight": "bold"}),
                html.Div(id="total-success", style={"color": "green", "fontWeight": "bold"}),
                html.Div(id="total-fail", style={"color": "red", "fontWeight": "bold"}),
            ],
        ),

        # ── Controls: Quick Date + From / To + Apply ────────────────────
        html.Div(
            style={
                "display": "flex",
                "alignItems": "center",
                "gap": "15px",
                "flexWrap": "wrap",
                "marginBottom": "25px",
            },
            children=[
                # Quick Date Buttons
                html.Div(
                    style={"display": "flex", "gap": "10px", "alignItems": "center"},
                    children=[
                        html.Label("Quick Date:", style={"fontWeight": "bold"}),
                        html.Button("Today", id="btn-today", n_clicks=0),
                        html.Button("Last 7 Days", id="btn-7days", n_clicks=0),
                        html.Button("Last 30 Days", id="btn-30days", n_clicks=0),
                    ],
                ),

                # From‐Date Picker
                html.Div(
                    style={"display": "flex", "flexDirection": "column"},
                    children=[
                        html.Label("From:", style={"fontWeight": "bold"}),
                        dcc.DatePickerSingle(
                            id="date-from",
                            min_date_allowed=(
                                df_initial["timestamp"].min().date()
                                if not df_initial["timestamp"].isna().all()
                                else datetime.today().date()
                            ),
                            max_date_allowed=(
                                df_initial["timestamp"].max().date()
                                if not df_initial["timestamp"].isna().all()
                                else datetime.today().date()
                            ),
                            date=(datetime.today().date() - timedelta(days=7)),
                            display_format="YYYY-MM-DD",
                            style={"width": "130px"},
                        ),
                    ],
                ),

                # To‐Date Picker
                html.Div(
                    style={"display": "flex", "flexDirection": "column"},
                    children=[
                        html.Label("To:", style={"fontWeight": "bold"}),
                        dcc.DatePickerSingle(
                            id="date-to",
                            min_date_allowed=(
                                df_initial["timestamp"].min().date()
                                if not df_initial["timestamp"].isna().all()
                                else datetime.today().date()
                            ),
                            max_date_allowed=(
                                df_initial["timestamp"].max().date()
                                if not df_initial["timestamp"].isna().all()
                                else datetime.today().date()
                            ),
                            date=datetime.today().date(),
                            display_format="YYYY-MM-DD",
                            style={"width": "130px"},
                        ),
                    ],
                ),

                # Apply Filter
                html.Div(
                    style={"marginTop": "22px"},
                    children=[html.Button("Apply Filter", id="btn-apply", n_clicks=0)],
                ),
            ],
        ),

        # ── Time Series Chart ─────────────────────────────────────────────
        dcc.Graph(
            id="time-series-chart",
            config={"displayModeBar": False},
            style={"marginBottom": "30px"},
        ),

        html.Hr(),

        # ── Download Button ───────────────────────────────────────────────
        html.Div(
            html.Button("⬇️ Download Filtered CSV", id="btn-download", n_clicks=0),
            style={"marginBottom": "15px"},
        ),

        # ── Data Table ────────────────────────────────────────────────────
        dash_table.DataTable(
            id="log-table",
            columns=[
                {"name": "Timestamp", "id": "timestamp", "type": "datetime"},
                {"name": "Source", "id": "source", "type": "text"},
                {"name": "Lead Name", "id": "lead_name", "type": "text"},
                {"name": "Message ID", "id": "message_id", "type": "text"},
                {"name": "Message Text", "id": "message_text", "type": "text"},
                {"name": "Status", "id": "status", "type": "text"},
            ],
            data=[],
            filter_action="native",
            sort_action="native",
            sort_mode="multi",
            page_action="native",
            page_current=0,
            page_size=25,
            style_table={"overflowX": "auto"},
            style_cell={
                "whiteSpace": "pre-line",
                "textAlign": "left",
                "padding": "5px",
                "fontFamily": "Arial",
                "fontSize": "13px",
            },
            style_header={"backgroundColor": "#f2f2f2", "fontWeight": "bold"},
        ),

        dcc.Download(id="download-dataframe-csv"),
    ],
)

# ── HELPERS ─────────────────────────────────────────────────────────────────────

def filter_dataframe(df: pd.DataFrame, start_date: datetime.date, end_date: datetime.date) -> pd.DataFrame:
    """
    Filter df to rows whose timestamp is between start_date (00:00) and end_date (23:59:59).
    """
    if df["timestamp"].isna().all():
        return df.copy()

    mask = (
        (df["timestamp"] >= pd.to_datetime(start_date))
        & (df["timestamp"] <= pd.to_datetime(end_date) + pd.Timedelta(hours=23, minutes=59, seconds=59))
    )
    return df.loc[mask].sort_values("timestamp", ascending=False)

# ── CALLBACKS ────────────────────────────────────────────────────────────────────

@app.callback(
    [Output("date-from", "date"), Output("date-to", "date")],
    [Input("btn-today", "n_clicks"), Input("btn-7days", "n_clicks"), Input("btn-30days", "n_clicks")],
)
def set_quick_date(n_today, n_7, n_30):
    ctx = callback_context
    if not ctx.triggered:
        raise PreventUpdate

    button_id = ctx.triggered[0]["prop_id"].split(".")[0]
    today = datetime.today().date()

    if button_id == "btn-today":
        return today, today
    elif button_id == "btn-7days":
        return today - timedelta(days=7), today
    elif button_id == "btn-30days":
        return today - timedelta(days=30), today
    else:
        raise PreventUpdate

@app.callback(
    [
        Output("total-rows", "children"),
        Output("total-success", "children"),
        Output("total-fail", "children"),
        Output("time-series-chart", "figure"),
        Output("log-table", "data"),
    ],
    [
        Input("btn-apply", "n_clicks"),
        Input("date-from", "date"),
        Input("date-to", "date"),
    ]
)
def update_report(n_apply, date_from, date_to):
    try:
        df_master = load_and_merge_data()
        print("COLUMNS:", list(df_master.columns))
        print("HEAD:\n", df_master.head(5).to_dict("records"))

        # temporarily ignore date filter:
        filtered = df_master.copy()

        total_rows = len(filtered)
        total_succ = filtered["status"].str.upper().value_counts().get("SUCCESS", 0)
        total_fail = filtered["status"].str.upper().value_counts().get("FAILED", 0)

        banner_total = f"Total Rows: {total_rows}"
        banner_succ = f"Successes: {total_succ}"
        banner_fail = f"Failures: {total_fail}"

        # build a trivial empty figure so Dash won’t error
        fig = {}
        display_df = filtered.copy()
        display_df["timestamp"] = display_df["timestamp"].dt.strftime("%Y-%m-%d %H:%M:%S")
        table_data = display_df.to_dict("records")

        return banner_total, banner_succ, banner_fail, fig, table_data

    except Exception as e:
        print("ERROR in update_report():", e)
        empty_fig = px.bar(
            pd.DataFrame({"date_only": [], "status": [], "count": []}),
            x="date_only", y="count", color="status"
        )
        return "", "", "", empty_fig, []


@app.callback(
    Output("download-dataframe-csv", "data"),
    [Input("btn-download", "n_clicks")],
    [State("date-from", "date"), State("date-to", "date")],
    prevent_initial_call=True,
)
def download_filtered_csv(n_clicks, date_from, date_to):
    df_master = load_and_merge_data()

    if date_from is None or date_to is None:
        today = datetime.today().date()
        start = today - timedelta(days=7)
        end = today
    else:
        start = pd.to_datetime(date_from).date()
        end = pd.to_datetime(date_to).date()

    df_to_download = filter_dataframe(df_master, start, end)
    df_to_download["timestamp"] = df_to_download["timestamp"].dt.strftime("%Y-%m-%d %H:%M:%S")

    return dcc.send_data_frame(df_to_download.to_csv, filename="sms_report_filtered.csv", index=False)

if __name__ == "__main__":
    app.run(port=DASH_PORT, debug=True)
