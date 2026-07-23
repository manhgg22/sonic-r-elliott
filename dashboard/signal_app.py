"""Professional command center cho scanner và paper trading OKX."""

import sys
from datetime import timedelta, timezone
from html import escape
from math import floor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import plotly.express as px
import streamlit as st

from core.trade_setup import FILTER_LABELS, SHORT_FILTER_LABELS
from paper_monitor import DB_PATH, connect, run_cycle, seconds_to_next_close


VN_TZ = timezone(timedelta(hours=7))
GREEN, RED, CYAN, MUTED = "#2dd4bf", "#fb7185", "#38bdf8", "#7f8ea3"
STATUS_ORDER = {
    "READY": 0, "WAIT_PA": 1, "WAIT_PULLBACK": 2, "NO_SETUP": 3, "ERROR": 4
}
FILTERS = ["f_trend", "f_breakout", "f_dow", "f_value_zone", "f_pa"]
FILTER_NAMES = {
    "f_trend": "EMA trend",
    "f_breakout": "Breakout",
    "f_dow": "Dow structure",
    "f_value_zone": "Value Zone",
    "f_pa": "Price Action",
}

st.set_page_config(
    page_title="Sonic R · Trading Command Center",
    page_icon="◈",
    layout="wide",
    initial_sidebar_state="expanded",
)
st.markdown(
    """
    <style>
    :root {
      --bg: #07111f; --panel: #0c1726; --panel-2: #101d2e;
      --line: #1d2b3e; --muted: #7f8ea3; --text: #e7eef8;
      --green: #2dd4bf; --red: #fb7185; --cyan: #38bdf8; --amber: #fbbf24;
    }
    html, body, [class*="css"] { font-family: Inter, ui-sans-serif, system-ui, sans-serif; }
    .stApp {
      background:
        radial-gradient(circle at 92% -10%, rgba(45,212,191,.08), transparent 28rem),
        radial-gradient(circle at 15% 15%, rgba(56,189,248,.045), transparent 24rem),
        var(--bg);
    }
    [data-testid="stHeader"] { background: transparent; }
    [data-testid="stToolbar"], #MainMenu, footer { display:none; }
    [data-testid="stSidebar"] {
      background: #081321; border-right: 1px solid var(--line);
    }
    [data-testid="stSidebar"] .block-container { padding-top: 1.25rem; }
    .block-container { padding: 1.4rem 2rem 3rem; max-width: 1600px; }
    h1, h2, h3 { letter-spacing: -.025em; }
    p { color: #a8b4c5; }
    hr { border-color: var(--line); }

    .side-brand { display:flex; gap:.75rem; align-items:center; margin:0 0 1.4rem; }
    .brand-mark {
      display:grid; place-items:center; width:38px; height:38px; border-radius:10px;
      color:#06131d; font-weight:900; letter-spacing:-.08em;
      background:linear-gradient(135deg, var(--green), var(--cyan));
      box-shadow:0 0 28px rgba(45,212,191,.18);
    }
    .side-brand strong { color:var(--text); font-size:.92rem; letter-spacing:.08em; }
    .side-brand span { color:var(--muted); font-size:.68rem; letter-spacing:.12em; }
    .control-label {
      color:#64748b; font-size:.65rem; font-weight:800; letter-spacing:.14em;
      margin:.85rem 0 .35rem;
    }

    .terminal-header {
      display:flex; align-items:center; justify-content:space-between; gap:1rem;
      padding:1.15rem 1.3rem; border:1px solid var(--line); border-radius:16px;
      background:linear-gradient(125deg, rgba(16,29,46,.96), rgba(8,19,33,.94));
      box-shadow:0 18px 50px rgba(0,0,0,.18); margin-bottom:.65rem;
    }
    .terminal-title { display:flex; align-items:center; gap:1rem; }
    .terminal-title .brand-mark { width:46px; height:46px; border-radius:12px; }
    .eyebrow {
      color:var(--green); font-size:.67rem; font-weight:800; letter-spacing:.16em;
      text-transform:uppercase; margin-bottom:.28rem;
    }
    .terminal-title h1 { color:var(--text); font-size:1.55rem; margin:0; line-height:1.05; }
    .terminal-title p { color:var(--muted); font-size:.78rem; margin:.35rem 0 0; }
    .live-stack { text-align:right; }
    .live-pill {
      display:inline-flex; align-items:center; gap:.45rem; border-radius:999px;
      padding:.38rem .7rem; font-size:.68rem; font-weight:800; letter-spacing:.08em;
      border:1px solid rgba(45,212,191,.28); color:var(--green);
      background:rgba(45,212,191,.07);
    }
    .live-pill.offline {
      color:var(--red); border-color:rgba(251,113,133,.28);
      background:rgba(251,113,133,.07);
    }
    .pulse-dot { width:7px; height:7px; border-radius:50%; background:currentColor; }
    .live-stack small { display:block; color:var(--muted); margin-top:.42rem; }

    .context-strip {
      display:grid; grid-template-columns:repeat(4, 1fr); gap:1px; overflow:hidden;
      border:1px solid var(--line); border-radius:12px; background:var(--line);
      margin-bottom:1rem;
    }
    .context-cell { background:#091522; padding:.65rem .9rem; }
    .context-cell span {
      display:block; color:#607086; font-size:.58rem; font-weight:800;
      letter-spacing:.12em; text-transform:uppercase;
    }
    .context-cell strong {
      display:block; color:#cdd8e8; font-size:.78rem; margin-top:.18rem;
      font-variant-numeric:tabular-nums;
    }

    .metric-card {
      position:relative; min-height:96px; overflow:hidden;
      background:linear-gradient(145deg, rgba(16,29,46,.95), rgba(11,23,38,.95));
      border:1px solid var(--line); border-radius:14px; padding:.9rem 1rem;
    }
    .metric-card:before {
      content:""; position:absolute; left:0; top:0; bottom:0; width:2px;
      background:var(--tone, var(--cyan));
    }
    .metric-card .label {
      color:#718198; font-size:.62rem; font-weight:800; letter-spacing:.11em;
      text-transform:uppercase;
    }
    .metric-card .value {
      color:var(--text); font-size:1.48rem; line-height:1.2; font-weight:720;
      margin-top:.45rem; font-variant-numeric:tabular-nums;
    }
    .metric-card .detail { color:#627188; font-size:.67rem; margin-top:.18rem; }

    .section-head {
      display:flex; justify-content:space-between; align-items:end; gap:1rem;
      margin:1.25rem 0 .7rem;
    }
    .section-head h2 { color:var(--text); font-size:1rem; margin:.15rem 0 0; }
    .section-head .meta { color:var(--muted); font-size:.7rem; text-align:right; }

    .signal-card, .position-card, .empty-card {
      border:1px solid var(--line); border-radius:14px; padding:1rem;
      background:linear-gradient(145deg, rgba(16,29,46,.94), rgba(10,22,36,.94));
      margin-bottom:.8rem; box-shadow:0 12px 28px rgba(0,0,0,.12);
    }
    .signal-card.long, .position-card.long { border-top:2px solid var(--green); }
    .signal-card.short, .position-card.short { border-top:2px solid var(--red); }
    .card-head { display:flex; justify-content:space-between; align-items:center; }
    .side-pill {
      display:inline-block; border-radius:5px; padding:.24rem .46rem;
      font-size:.58rem; font-weight:900; letter-spacing:.1em;
    }
    .side-pill.long { color:var(--green); background:rgba(45,212,191,.1); }
    .side-pill.short { color:var(--red); background:rgba(251,113,133,.1); }
    .card-time { color:#64748b; font-size:.65rem; }
    .asset-name {
      color:var(--text); font-size:1.25rem; font-weight:750; margin:.8rem 0 .1rem;
    }
    .asset-symbol { color:#68788f; font-size:.66rem; }
    .level-grid {
      display:grid; grid-template-columns:repeat(4,1fr); gap:.45rem;
      margin:.85rem 0 .7rem;
    }
    .level {
      background:rgba(5,14,25,.58); border:1px solid #19283a;
      border-radius:8px; padding:.48rem .55rem;
    }
    .level span {
      display:block; color:#65758b; font-size:.55rem; font-weight:800;
      letter-spacing:.08em; text-transform:uppercase;
    }
    .level strong {
      display:block; color:#dbe6f5; font-size:.73rem; margin-top:.24rem;
      font-variant-numeric:tabular-nums;
    }
    .card-foot {
      display:flex; justify-content:space-between; gap:.6rem; color:#718198;
      font-size:.62rem; padding-top:.65rem; border-top:1px solid #182638;
    }
    .positive { color:var(--green) !important; }
    .negative { color:var(--red) !important; }
    .progress-track {
      height:4px; border-radius:999px; overflow:hidden; background:#172538;
      margin:.75rem 0 .45rem;
    }
    .progress-fill {
      height:100%; background:linear-gradient(90deg,var(--green),var(--cyan));
    }
    .empty-card { color:#708096; text-align:center; padding:2.2rem 1rem; }
    .empty-card strong { color:#bcc9da; display:block; margin-bottom:.3rem; }

    .playbook {
      display:grid; grid-template-columns:repeat(5,1fr); gap:.7rem; margin-top:.8rem;
    }
    .play-step {
      position:relative; min-height:126px; border:1px solid var(--line);
      border-radius:12px; background:var(--panel); padding:.9rem;
    }
    .play-step .num { color:var(--green); font-size:.65rem; font-weight:900; }
    .play-step strong { display:block; color:var(--text); margin:.65rem 0 .35rem; }
    .play-step span { color:var(--muted); font-size:.7rem; line-height:1.45; }

    div[data-testid="stVerticalBlockBorderWrapper"] {
      border-color:var(--line); background:rgba(12,23,38,.65); border-radius:14px;
    }
    .stButton button, .stDownloadButton button {
      border-radius:8px; border:1px solid #26364b; font-size:.72rem;
      font-weight:800; letter-spacing:.04em; min-height:2.45rem;
    }
    .stButton button[kind="primary"] {
      color:#041218; border:0;
      background:linear-gradient(135deg,var(--green),var(--cyan));
    }
    .stButton button[kind="primary"] p { color:#041218 !important; }
    div[data-baseweb="tab-list"] {
      gap:.2rem; background:#091522; border:1px solid var(--line);
      border-radius:10px; padding:.25rem; margin-top:.9rem;
    }
    button[data-baseweb="tab"] {
      border-radius:7px; color:#75859a; height:2.55rem; padding:0 1.05rem;
      font-size:.65rem; font-weight:850; letter-spacing:.08em;
    }
    button[data-baseweb="tab"][aria-selected="true"] {
      color:#e7eef8; background:#142237;
    }
    [data-testid="stDataFrame"] {
      border:1px solid var(--line); border-radius:12px; overflow:hidden;
    }
    [data-testid="stPlotlyChart"] {
      border:1px solid var(--line); border-radius:14px;
      background:rgba(10,22,36,.74); overflow:hidden;
    }
    @media (max-width: 900px) {
      .context-strip, .playbook { grid-template-columns:1fr 1fr; }
      .terminal-header { align-items:flex-start; }
      .level-grid { grid-template-columns:1fr 1fr; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def price(value):
    if value is None or pd.isna(value):
        return "—"
    if abs(value) >= 1000:
        return f"{value:,.2f}"
    if abs(value) >= 1:
        return f"{value:,.4f}"
    return f"{value:.8f}"


def metric_card(column, label, value, detail, tone=CYAN):
    column.markdown(
        f"""
        <div class="metric-card" style="--tone:{tone}">
          <div class="label">{escape(str(label))}</div>
          <div class="value">{escape(str(value))}</div>
          <div class="detail">{escape(str(detail))}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def section_head(kicker, title, meta=""):
    st.markdown(
        f"""
        <div class="section-head">
          <div><div class="eyebrow">{escape(kicker)}</div><h2>{escape(title)}</h2></div>
          <div class="meta">{escape(meta)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def style_plot(fig, height=340):
    fig.update_layout(
        template="plotly_dark",
        height=height,
        margin=dict(l=16, r=16, t=22, b=16),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#8fa0b6", size=11),
        legend=dict(orientation="h", yanchor="bottom", y=1.01, xanchor="right", x=1),
        hoverlabel=dict(bgcolor="#101d2e", bordercolor="#26364b"),
    )
    fig.update_xaxes(gridcolor="#182638", zerolinecolor="#182638")
    fig.update_yaxes(gridcolor="#182638", zerolinecolor="#182638")
    return fig


@st.cache_data(ttl=8, show_spinner=False)
def load_data(db_name):
    conn = connect(db_name)
    try:
        setups = pd.read_sql_query("SELECT * FROM latest_setups", conn)
        runs = pd.read_sql_query(
            "SELECT * FROM scan_runs ORDER BY id DESC LIMIT 96", conn
        )
        trades = pd.read_sql_query(
            "SELECT * FROM paper_trades ORDER BY id DESC", conn
        )
        events = pd.read_sql_query(
            "SELECT * FROM paper_events ORDER BY id DESC LIMIT 500", conn
        )
    finally:
        conn.close()
    for frame, columns in [
        (setups, ["signal_time"]),
        (runs, ["scanned_at"]),
        (trades, ["opened_at", "last_bar_time", "closed_at"]),
        (events, ["event_at"]),
    ]:
        for column in columns:
            if column in frame:
                frame[column] = pd.to_datetime(frame[column], utc=True, errors="coerce")
    return setups, runs, trades, events


def run_manual_scan():
    progress = st.progress(0, text="Đang tải universe OKX...")

    def update(done, total):
        progress.progress(done / total, text=f"Đã quét {done}/{total} coin")

    try:
        with st.spinner("Đang quét nến M15/H1 đã đóng..."):
            summary = run_cycle(DB_PATH, progress=update)
        st.session_state.scan_summary = summary
        st.cache_data.clear()
    finally:
        progress.empty()


with st.sidebar:
    st.markdown(
        """
        <div class="side-brand">
          <div class="brand-mark">SR</div>
          <div><strong>SONIC R</strong><br><span>EXECUTION DESK</span></div>
        </div>
        <div class="control-label">RISK MODEL</div>
        """,
        unsafe_allow_html=True,
    )
    capital = st.number_input(
        "Paper capital · USDT", min_value=100.0, value=10_000.0, step=1_000.0
    )
    risk_pct = st.slider("Risk per trade · %", 0.25, 1.0, 0.5, 0.25)
    st.markdown('<div class="control-label">SIGNAL FILTERS</div>', unsafe_allow_html=True)
    direction_filter = st.segmented_control(
        "Direction", ["Tất cả", "LONG", "SHORT"], default="Tất cả"
    )
    status_filter = st.multiselect(
        "Setup state",
        ["READY", "WAIT_PA", "WAIT_PULLBACK", "NO_SETUP"],
        default=["READY", "WAIT_PA", "WAIT_PULLBACK"],
    )
    coin_query = st.text_input("Asset search", placeholder="BTC, ETH, SOL...")
    st.markdown('<div class="control-label">OPERATIONS</div>', unsafe_allow_html=True)
    if st.button("RUN FULL SCAN", type="primary", width="stretch"):
        run_manual_scan()
    if st.button("REFRESH DATA", width="stretch"):
        st.cache_data.clear()
        st.rerun()
    st.caption(
        "Paper-only execution. Monitor runs independently when this page is closed."
    )

setups, runs, trades, events = load_data(str(DB_PATH))
last_scan = runs["scanned_at"].max() if not runs.empty else pd.NaT
age_minutes = (
    (pd.Timestamp.now(tz="UTC") - last_scan).total_seconds() / 60
    if pd.notna(last_scan) else float("inf")
)
monitor_ok = age_minutes < 30
next_close = pd.Timestamp.now(tz=VN_TZ) + timedelta(seconds=seconds_to_next_close())
scan_text = (
    last_scan.tz_convert(VN_TZ).strftime("%d/%m/%Y · %H:%M:%S")
    if pd.notna(last_scan) else "NO DATA"
)
risk_usd = capital * risk_pct / 100

st.markdown(
    f"""
    <div class="terminal-header">
      <div class="terminal-title">
        <div class="brand-mark">SR</div>
        <div>
          <div class="eyebrow">OKX PERPETUAL INTELLIGENCE</div>
          <h1>Trading Command Center</h1>
          <p>Multi-timeframe scanner · paper execution · portfolio telemetry</p>
        </div>
      </div>
      <div class="live-stack">
        <div class="live-pill {'online' if monitor_ok else 'offline'}">
          <span class="pulse-dot"></span>
          {'MONITOR ONLINE' if monitor_ok else 'MONITOR STALE'}
        </div>
        <small>Next M15 close · {next_close:%H:%M:%S} VN</small>
      </div>
    </div>
    <div class="context-strip">
      <div class="context-cell"><span>Last synchronized</span><strong>{scan_text} VN</strong></div>
      <div class="context-cell"><span>Execution mode</span><strong>PAPER · OHLCV</strong></div>
      <div class="context-cell"><span>Risk allocation</span><strong>{risk_usd:,.2f} USDT / TRADE</strong></div>
      <div class="context-cell"><span>Venue / cadence</span><strong>OKX · M15 CLOSE</strong></div>
    </div>
    """,
    unsafe_allow_html=True,
)

if setups.empty:
    st.markdown(
        """
        <div class="empty-card">
          <strong>No scanner snapshot</strong>
          Run a full scan or start <code>python paper_monitor.py</code>.
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.stop()

report = setups.copy()
for column in ["actionable", *FILTERS]:
    report[column] = report[column].fillna(0).astype(bool)
report["_order"] = report["status"].map(STATUS_ORDER).fillna(9)
report = report.sort_values(["_order", "rank", "side"]).drop(columns="_order")
success = report[report["status"] != "ERROR"]
ready = success[success["status"] == "READY"]
waiting = success[success["status"].isin(["WAIT_PA", "WAIT_PULLBACK"])]
open_trades = trades[trades["status"] == "OPEN"].copy()
closed_trades = trades[trades["status"] == "CLOSED"].copy()
data_errors = report.loc[report["status"] == "ERROR", "symbol"].nunique()

metric_columns = st.columns(6)
metric_card(
    metric_columns[0], "Market universe", success["symbol"].nunique(),
    "USDT perpetuals", CYAN,
)
metric_card(
    metric_columns[1], "Long ready", int((ready["side"] == "LONG").sum()),
    "actionable now", GREEN,
)
metric_card(
    metric_columns[2], "Short ready", int((ready["side"] == "SHORT").sum()),
    "actionable now", RED,
)
metric_card(metric_columns[3], "Setup queue", len(waiting), "awaiting confirmation", "#fbbf24")
metric_card(metric_columns[4], "Open exposure", len(open_trades), "paper positions", "#a78bfa")
metric_card(
    metric_columns[5], "Data integrity", "PASS" if data_errors == 0 else data_errors,
    "0 errors" if data_errors == 0 else "symbols degraded",
    GREEN if data_errors == 0 else RED,
)

command, scanner, positions, history, method = st.tabs(
    ["COMMAND CENTER", "SIGNAL MATRIX", "OPEN POSITIONS", "PERFORMANCE", "PLAYBOOK"]
)

with command:
    execution, state = st.columns([3, 2])
    with execution:
        section_head(
            "EXECUTION QUEUE", "Actionable signals",
            f"{len(ready)} setup(s) passed all 5 gates",
        )
        if ready.empty:
            st.markdown(
                """
                <div class="empty-card">
                  <strong>No executable setup</strong>
                  The desk stays flat until a closed M15 candle passes all gates.
                </div>
                """,
                unsafe_allow_html=True,
            )
        else:
            signal_columns = st.columns(2)
            for index, (_, row) in enumerate(ready.iterrows()):
                risk_per_unit = abs(row["entry"] - row["sl"])
                base_qty = risk_usd / risk_per_unit
                raw_contracts = base_qty / row["contract_size"]
                contracts = floor(raw_contracts / row["amount_step"]) * row["amount_step"]
                actual_risk = contracts * row["contract_size"] * risk_per_unit
                notional = contracts * row["contract_size"] * row["entry"]
                signal_time = row["signal_time"].tz_convert(VN_TZ)
                side = row["side"].lower()
                minimum = (
                    f" · below min {row['min_contracts']:g}"
                    if contracts < row["min_contracts"] else ""
                )
                signal_columns[index % 2].markdown(
                    f"""
                    <div class="signal-card {side}">
                      <div class="card-head">
                        <span class="side-pill {side}">{escape(row['side'])}</span>
                        <span class="card-time">{signal_time:%d/%m · %H:%M} VN</span>
                      </div>
                      <div class="asset-name">{escape(str(row['base']))}</div>
                      <div class="asset-symbol">{escape(str(row['symbol']))} · {escape(str(row['pa']).upper())}</div>
                      <div class="level-grid">
                        <div class="level"><span>Entry</span><strong>{price(row['entry'])}</strong></div>
                        <div class="level"><span>Stop · 1R</span><strong>{price(row['sl'])}</strong></div>
                        <div class="level"><span>TP1 · {row['tp1_rr']:.2f}R</span><strong>{price(row['tp1'])}</strong></div>
                        <div class="level"><span>TP2 · {row['tp2_rr']:.2f}R</span><strong>{price(row['tp2'])}</strong></div>
                      </div>
                      <div class="card-foot">
                        <span>{contracts:g} contracts{escape(minimum)}</span>
                        <span>{notional:,.0f} notional · {actual_risk:.2f} risk</span>
                      </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
    with state:
        section_head(
            "MARKET STATE", "Setup distribution",
            f"{len(success):,} direction rows",
        )
        status_counts = (
            success["status"]
            .replace(
                {
                    "WAIT_PULLBACK": "WAIT VZ",
                    "WAIT_PA": "WAIT PA",
                    "NO_SETUP": "NO SETUP",
                }
            )
            .value_counts()
            .rename_axis("state")
            .reset_index(name="count")
        )
        colors = {
            "READY": GREEN, "WAIT PA": "#fbbf24",
            "WAIT VZ": CYAN, "NO SETUP": "#27364a",
        }
        fig = px.pie(
            status_counts, names="state", values="count", hole=.72,
            color="state", color_discrete_map=colors,
        )
        fig.update_traces(
            textinfo="percent", textfont_size=10,
            marker=dict(line=dict(color="#07111f", width=2)),
        )
        fig.add_annotation(
            text=f"<b>{len(success):,}</b><br><span>SETUPS</span>",
            x=.5, y=.5, showarrow=False, font=dict(size=15, color="#dce7f5"),
        )
        style_plot(fig, 330)
        fig.update_layout(showlegend=True)
        st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})

    funnel_col, pulse_col = st.columns([3, 2])
    with funnel_col:
        section_head("FILTER TELEMETRY", "Five-gate pass rate", "LONG vs SHORT")
        funnel = (
            success.groupby("side")[FILTERS].mean().mul(100).reset_index()
            .melt(id_vars="side", var_name="gate", value_name="pass_rate")
        )
        funnel["gate"] = funnel["gate"].map(FILTER_NAMES)
        fig = px.bar(
            funnel, x="pass_rate", y="gate", color="side", barmode="group",
            orientation="h", text_auto=".1f",
            color_discrete_map={"LONG": GREEN, "SHORT": RED},
            labels={"gate": "", "pass_rate": "Pass rate · %", "side": ""},
        )
        fig.update_traces(textposition="outside", cliponaxis=False)
        style_plot(fig, 360)
        fig.update_xaxes(range=[0, max(105, funnel["pass_rate"].max() + 8)])
        fig.update_yaxes(categoryorder="array", categoryarray=list(FILTER_NAMES.values())[::-1])
        st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
    with pulse_col:
        section_head("SCANNER PULSE", "Signals per scan", "last 96 cycles")
        if runs.empty:
            st.markdown('<div class="empty-card">No scan history</div>', unsafe_allow_html=True)
        else:
            timeline = runs.sort_values("scanned_at").copy()
            timeline["Time"] = timeline["scanned_at"].dt.tz_convert(VN_TZ)
            fig = px.line(
                timeline, x="Time", y=["long_ready", "short_ready"], markers=True,
                color_discrete_map={"long_ready": GREEN, "short_ready": RED},
                labels={"value": "Ready signals", "variable": "", "Time": ""},
            )
            fig.update_traces(line_width=2.2, marker_size=5)
            style_plot(fig, 360)
            st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})

with scanner:
    view = report.copy()
    if direction_filter != "Tất cả":
        view = view[view["side"] == direction_filter]
    if status_filter:
        view = view[view["status"].isin(status_filter)]
    if coin_query.strip():
        view = view[
            view["base"].str.contains(coin_query.strip(), case=False, regex=False)
        ]
    view["Asset"] = view["base"] + "  ·  " + view["name"]
    view["State"] = view["status"].replace(
        {
            "READY": "READY",
            "WAIT_PA": "WAIT · PA",
            "WAIT_PULLBACK": "WAIT · VALUE ZONE",
            "NO_SETUP": "NO SETUP",
            "ERROR": "DATA ERROR",
        }
    )
    view["Gate score"] = view[FILTERS].sum(axis=1)
    view["Last"] = view["bar_close"]
    section_head(
        "SIGNAL MATRIX", "Full universe scanner",
        f"{len(view)} rows visible · snapshot {scan_text} VN",
    )
    st.dataframe(
        view[
            ["rank", "Asset", "side", "State", "Gate score", "Last", "pa", "missing"]
        ],
        hide_index=True,
        width="stretch",
        height=690,
        column_config={
            "rank": st.column_config.NumberColumn("#", format="%d", width="small"),
            "Asset": st.column_config.TextColumn("ASSET", width="medium"),
            "side": st.column_config.TextColumn("SIDE", width="small"),
            "State": st.column_config.TextColumn("SETUP STATE", width="medium"),
            "Gate score": st.column_config.ProgressColumn(
                "GATES", min_value=0, max_value=5, format="%d / 5", width="small"
            ),
            "Last": st.column_config.NumberColumn("LAST CLOSE", format="%.8f"),
            "pa": st.column_config.TextColumn("PRICE ACTION"),
            "missing": st.column_config.TextColumn("BLOCKER", width="large"),
        },
    )
    download, note = st.columns([1, 4])
    download.download_button(
        "EXPORT SNAPSHOT", report.to_csv(index=False),
        "sonic_r_okx_snapshot.csv", "text/csv", width="stretch",
    )
    note.caption(
        "Gate score is diagnostic only. Execution still requires all five gates on a closed M15 candle."
    )

with positions:
    latest_price = success.set_index(["symbol", "side"])["bar_close"].to_dict()

    def floating_r(trade):
        current = latest_price.get((trade["symbol"], trade["side"]), trade["entry"])
        direction = 1 if trade["side"] == "LONG" else -1
        return (
            trade["realized_r"]
            + trade["remaining"] * (current - trade["entry"]) * direction / trade["risk"]
        )

    if not open_trades.empty:
        open_trades["floating_r"] = open_trades.apply(floating_r, axis=1)
    long_open = int((open_trades["side"] == "LONG").sum()) if not open_trades.empty else 0
    short_open = int((open_trades["side"] == "SHORT").sum()) if not open_trades.empty else 0
    total_float = open_trades["floating_r"].sum() if not open_trades.empty else 0.0
    exposure_metrics = st.columns(4)
    metric_card(exposure_metrics[0], "Open positions", len(open_trades), "paper book", "#a78bfa")
    metric_card(exposure_metrics[1], "Directional mix", f"{long_open}L / {short_open}S", "active exposure", CYAN)
    metric_card(
        exposure_metrics[2], "Mark-to-model", f"{total_float:+.2f}R",
        f"{total_float * risk_usd:+,.2f} USDT", GREEN if total_float >= 0 else RED,
    )
    metric_card(
        exposure_metrics[3], "Risk at entry", f"{len(open_trades) * risk_usd:,.2f}",
        "USDT gross allocation", "#fbbf24",
    )
    section_head("PAPER BOOK", "Open execution ledger", "mark based on latest closed M15")
    if open_trades.empty:
        st.markdown(
            '<div class="empty-card"><strong>Flat book</strong>No paper positions are open.</div>',
            unsafe_allow_html=True,
        )
    else:
        position_columns = st.columns(2)
        for index, (_, trade) in enumerate(
            open_trades.sort_values("opened_at", ascending=False).iterrows()
        ):
            current = latest_price.get(
                (trade["symbol"], trade["side"]), trade["entry"]
            )
            closed_pct = max(0, min(100, 100 * (1 - trade["remaining"])))
            opened_at = trade["opened_at"].tz_convert(VN_TZ)
            side = trade["side"].lower()
            pnl_class = "positive" if trade["floating_r"] >= 0 else "negative"
            tp1 = "FILLED" if trade["tp1_hit"] else price(trade["tp1"])
            tp2 = "FILLED" if trade["tp2_hit"] else price(trade["tp2"])
            position_columns[index % 2].markdown(
                f"""
                <div class="position-card {side}">
                  <div class="card-head">
                    <span class="side-pill {side}">{escape(trade['side'])}</span>
                    <span class="card-time">#{trade['id']} · {opened_at:%d/%m %H:%M} VN</span>
                  </div>
                  <div class="card-head">
                    <div>
                      <div class="asset-name">{escape(str(trade['base']))}</div>
                      <div class="asset-symbol">{escape(str(trade['symbol']))}</div>
                    </div>
                    <div class="asset-name {pnl_class}">{trade['floating_r']:+.2f}R</div>
                  </div>
                  <div class="level-grid">
                    <div class="level"><span>Mark</span><strong>{price(current)}</strong></div>
                    <div class="level"><span>Entry</span><strong>{price(trade['entry'])}</strong></div>
                    <div class="level"><span>Stop</span><strong>{price(trade['current_sl'])}</strong></div>
                    <div class="level"><span>Trail H1</span><strong>{price(trade['trail_h1'])}</strong></div>
                    <div class="level"><span>TP1</span><strong>{tp1}</strong></div>
                    <div class="level"><span>TP2</span><strong>{tp2}</strong></div>
                    <div class="level"><span>MFE</span><strong>{trade['mfe_r']:+.2f}R</strong></div>
                    <div class="level"><span>MAE</span><strong>{trade['mae_r']:+.2f}R</strong></div>
                  </div>
                  <div class="progress-track"><div class="progress-fill" style="width:{closed_pct:.0f}%"></div></div>
                  <div class="card-foot">
                    <span>{closed_pct:.0f}% realized</span>
                    <span>{trade['realized_r']:+.2f}R booked · {trade['remaining']:.0%} remaining</span>
                  </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

with history:
    total_r = closed_trades["total_r"].sum() if not closed_trades.empty else 0.0
    winrate = (
        100 * (closed_trades["total_r"] > 0).mean()
        if not closed_trades.empty else 0.0
    )
    avg_r = closed_trades["total_r"].mean() if not closed_trades.empty else 0.0
    performance_metrics = st.columns(4)
    metric_card(performance_metrics[0], "Closed trades", len(closed_trades), "paper sample", CYAN)
    metric_card(performance_metrics[1], "Win rate", f"{winrate:.1f}%", "closed trades only", GREEN)
    metric_card(
        performance_metrics[2], "Net expectancy", f"{avg_r:+.2f}R",
        f"total {total_r:+.2f}R", GREEN if avg_r >= 0 else RED,
    )
    metric_card(
        performance_metrics[3], "Model P&L", f"{total_r * risk_usd:+,.2f}",
        "USDT · fixed risk", GREEN if total_r >= 0 else RED,
    )
    equity_col, events_col = st.columns([3, 2])
    with equity_col:
        section_head("PERFORMANCE", "Paper equity curve", "fixed-risk model")
        if closed_trades.empty:
            st.markdown(
                '<div class="empty-card"><strong>Awaiting exits</strong>Equity starts after the first paper trade closes.</div>',
                unsafe_allow_html=True,
            )
        else:
            equity = closed_trades.sort_values("closed_at").copy()
            equity["Equity"] = capital + equity["total_r"].cumsum() * risk_usd
            fig = px.area(
                equity, x="closed_at", y="Equity", markers=True,
                labels={"closed_at": "", "Equity": "USDT"},
            )
            fig.update_traces(line_color=GREEN, fillcolor="rgba(45,212,191,.12)")
            style_plot(fig, 350)
            st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
    with events_col:
        section_head("AUDIT TRAIL", "Execution events", f"latest {min(500, len(events))}")
        if events.empty:
            st.markdown('<div class="empty-card">No execution events</div>', unsafe_allow_html=True)
        else:
            event_view = events.merge(
                trades[["id", "symbol", "side"]],
                left_on="trade_id", right_on="id", how="left", suffixes=("", "_trade"),
            )
            event_view["Time"] = event_view["event_at"].dt.tz_convert(VN_TZ)
            st.dataframe(
                event_view[["Time", "symbol", "side", "event", "price", "delta_r"]],
                hide_index=True, width="stretch", height=350,
                column_config={
                    "Time": st.column_config.DatetimeColumn("TIME · VN", format="DD/MM HH:mm"),
                    "symbol": "SYMBOL", "side": "SIDE", "event": "EVENT",
                    "price": st.column_config.NumberColumn("PRICE", format="%.8f"),
                    "delta_r": st.column_config.NumberColumn("DELTA", format="%+.2fR"),
                },
            )
    if not closed_trades.empty:
        section_head("TRADE LEDGER", "Closed positions", f"{len(closed_trades)} records")
        st.dataframe(
            closed_trades[
                [
                    "id", "symbol", "side", "opened_at", "closed_at",
                    "exit_reason", "total_r", "mfe_r", "mae_r",
                ]
            ].sort_values("closed_at", ascending=False),
            hide_index=True, width="stretch",
        )

with method:
    section_head(
        "SYSTEM PLAYBOOK", "From market context to execution",
        "fixed logic · closed candles only",
    )
    steps = [
        ("01", "EMA regime", "H1 EMA34/89 defines the permitted direction."),
        ("02", "Range break", "20-bar breakout remains valid for 30 H1 candles."),
        ("03", "Dow structure", "LONG needs HH/HL; SHORT mirrors with LL/LH."),
        ("04", "Value Zone", "Price retraces into the Sonic R EMA band."),
        ("05", "M15 trigger", "Closed engulfing or pinbar authorizes entry."),
    ]
    cards = "".join(
        f'<div class="play-step"><div class="num">{number}</div>'
        f"<strong>{escape(title)}</strong><span>{escape(text)}</span></div>"
        for number, title, text in steps
    )
    st.markdown(f'<div class="playbook">{cards}</div>', unsafe_allow_html=True)

    execution_rule, controls = st.columns(2)
    with execution_rule:
        section_head("EXECUTION MODEL", "Position lifecycle")
        st.markdown(
            """
            - Enter at the confirming M15 close; never chase an intrabar signal.
            - Initial stop uses the 5-bar swing / EMA89 plus a 0.5 ATR buffer.
            - TP1 realizes 50%, then the remaining stop moves to breakeven.
            - TP2 realizes another 30%; the final 20% follows the H1 EMA34 trail.
            - If SL and TP touch in the same candle, the simulator resolves SL first.
            """
        )
    with controls:
        section_head("RISK CONTROLS", "What this terminal will not do")
        st.markdown(
            """
            - No exchange credentials and no live order submission.
            - No entry from an unfinished M15 or H1 candle.
            - No hidden parameter tuning after observing a favorable result.
            - Paper P&L excludes funding, slippage and real fill latency.
            - A READY signal is a model event, not a promise of profit.
            """
        )
    with st.expander("Exact gate definitions"):
        st.write("**LONG:** " + " → ".join(FILTER_LABELS.values()))
        st.write("**SHORT:** " + " → ".join(SHORT_FILTER_LABELS.values()))
