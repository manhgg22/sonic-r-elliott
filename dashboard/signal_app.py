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
from dashboard.backend import DashboardBackend
from paper_monitor import DB_PATH, run_cycle, seconds_to_next_close


VN_TZ = timezone(timedelta(hours=7))
GREEN, RED, CYAN, MUTED = "#2dd4bf", "#fb7185", "#38bdf8", "#7f8ea3"
STATUS_ORDER = {
    "READY": 0, "WAIT_PA": 1, "WAIT_PULLBACK": 2, "NO_SETUP": 3, "ERROR": 4
}
FILTERS = ["f_trend", "f_breakout", "f_dow", "f_value_zone", "f_pa"]
FILTER_NAMES = {
    "f_trend": "Xu hướng EMA",
    "f_breakout": "Phá vỡ biên",
    "f_dow": "Cấu trúc Dow",
    "f_value_zone": "Vùng giá trị",
    "f_pa": "Hành động giá",
}

st.set_page_config(
    page_title="Sonic R · Bảng tín hiệu",
    page_icon="S",
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

# Giao diện "bàn phân tích": sáng, phẳng và ưu tiên khả năng quét dữ liệu.
st.markdown(
    """
    <style>
    :root {
      --bg:#f2f4f1; --panel:#ffffff; --panel-2:#f7f8f5;
      --line:#d7dcd5; --muted:#667069; --text:#17201b;
      --green:#087f5b; --red:#c92a2a; --cyan:#1769aa; --amber:#d97706;
    }
    .stApp { background:#f2f4f1; }
    [data-testid="stHeader"] { background:#f2f4f1; }
    [data-testid="stSidebar"] {
      background:#ffffff; border-right:1px solid #d7dcd5;
    }
    .block-container { max-width:1680px; padding-top:1rem; }
    p { color:#667069; }
    .brand-mark {
      color:#fff; background:#087f5b; box-shadow:none;
      border-radius:3px;
    }
    .side-brand strong, .terminal-title h1, .section-head h2,
    .asset-name, .play-step strong { color:#17201b; }
    .side-brand span, .terminal-title p, .section-head .meta,
    .card-time, .asset-symbol { color:#667069; }
    .control-label, .eyebrow { color:#087f5b; }
    .terminal-header {
      border:0; border-radius:4px; background:#17201b;
      box-shadow:none; padding:1rem 1.15rem;
    }
    .terminal-header .terminal-title h1 { color:#fff; }
    .terminal-header .terminal-title p { color:#aeb8b1; }
    .terminal-header .brand-mark {
      color:#17201b; background:#d9f99d;
    }
    .terminal-header .eyebrow { color:#86efac; }
    .live-pill {
      border-radius:3px; color:#86efac;
      border-color:#3f5e4d; background:#263a30;
    }
    .live-pill.offline {
      color:#fecaca; border-color:#713f3f; background:#442727;
    }
    .context-strip {
      border-radius:0; border-color:#cdd3cc; background:#cdd3cc;
    }
    .context-cell { background:#fff; }
    .context-cell span { color:#78817b; }
    .context-cell strong { color:#25302a; }
    .metric-card {
      min-height:88px; border-radius:3px; box-shadow:none;
      background:#fff; border-color:#d7dcd5;
    }
    .metric-card .label, .metric-card .detail { color:#667069; }
    .metric-card .value { color:#17201b; }
    .signal-card, .position-card, .empty-card {
      border-radius:3px; background:#fff; box-shadow:none;
      border-color:#d7dcd5;
    }
    .level {
      border-radius:2px; background:#f4f6f3; border-color:#e0e4df;
    }
    .level span { color:#737d76; }
    .level strong { color:#17201b; }
    .card-foot { color:#667069; border-color:#e0e4df; }
    .side-pill { border-radius:2px; }
    .play-step {
      border-radius:3px; background:#fff; border-color:#d7dcd5;
    }
    div[data-baseweb="tab-list"] {
      border-radius:3px; background:#fff; border-color:#d7dcd5;
    }
    button[data-baseweb="tab"] { border-radius:2px; color:#667069; }
    button[data-baseweb="tab"][aria-selected="true"] {
      color:#fff; background:#17201b;
    }
    .stButton button, .stDownloadButton button {
      border-radius:3px; border-color:#bfc7c0;
    }
    .stButton button[kind="primary"] {
      color:#fff; background:#087f5b;
    }
    .stButton button[kind="primary"] p { color:#fff !important; }
    [data-testid="stDataFrame"], [data-testid="stPlotlyChart"] {
      border-radius:3px; border-color:#d7dcd5; background:#fff;
    }
    .live-grid {
      display:grid; grid-template-columns:repeat(4,minmax(0,1fr));
      gap:.55rem; margin:.55rem 0 1rem;
    }
    .live-quote {
      background:#17201b; border-left:3px solid #667069;
      padding:.75rem .8rem; min-width:0;
    }
    .live-quote.up { border-left-color:#22c55e; }
    .live-quote.down { border-left-color:#ef4444; }
    .live-quote .quote-head {
      display:flex; justify-content:space-between; gap:.5rem;
      color:#aeb8b1; font-size:.66rem; font-weight:700;
    }
    .live-quote .quote-price {
      color:#fff; font-size:1.08rem; font-weight:750;
      margin:.4rem 0 .18rem; font-variant-numeric:tabular-nums;
    }
    .live-quote .quote-pnl {
      font-size:.72rem; font-weight:750; font-variant-numeric:tabular-nums;
    }
    .live-quote.up .quote-pnl { color:#86efac; }
    .live-quote.down .quote-pnl { color:#fca5a5; }
    .live-stamp {
      display:flex; align-items:center; gap:.4rem; color:#667069;
      font-size:.66rem; margin-bottom:.35rem;
    }
    .live-stamp i {
      width:7px; height:7px; border-radius:50%; background:#22c55e;
      box-shadow:0 0 0 3px rgba(34,197,94,.14);
    }
    @media (max-width: 1100px) {
      .live-grid { grid-template-columns:1fr 1fr; }
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
        template="plotly_white",
        height=height,
        margin=dict(l=16, r=16, t=22, b=16),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#667069", size=11),
        legend=dict(orientation="h", yanchor="bottom", y=1.01, xanchor="right", x=1),
        hoverlabel=dict(bgcolor="#ffffff", bordercolor="#d7dcd5"),
    )
    fig.update_xaxes(gridcolor="#e7ebe6", zerolinecolor="#d7dcd5")
    fig.update_yaxes(gridcolor="#e7ebe6", zerolinecolor="#d7dcd5")
    return fig


@st.cache_resource
def get_backend(db_name):
    return DashboardBackend(db_name)


@st.fragment(run_every="2s")
def live_position_quotes(open_positions, risk_per_trade):
    """Định giá trực tiếp, không thay đổi trạng thái giao dịch trong SQLite."""
    if open_positions.empty:
        return

    try:
        backend = get_backend(str(DB_PATH))
        live_positions = backend.live_positions(
            open_positions.sort_values("opened_at", ascending=False),
            backend.fetch_swap_prices(),
        )
    except (RuntimeError, ValueError, KeyError, OSError):
        st.warning("Tạm thời chưa lấy được giá trực tiếp từ OKX. Dữ liệu nến M15 vẫn hoạt động.")
        return

    previous = st.session_state.setdefault("okx_previous_quotes", {})
    cards = []
    total_live_r = 0.0
    for position in live_positions:
        inst_id = position["inst_id"]
        last = position["last"]
        live_r = position["live_r"]
        total_live_r += live_r
        old = previous.get(inst_id, last)
        side_class = "up" if live_r >= 0 else "down"
        arrow = "▲" if last > old else "▼" if last < old else "•"
        cards.append(
            f'<div class="live-quote {side_class}">'
            f'<div class="quote-head"><span>{escape(str(position["base"]))} · '
            f'{escape(str(position["side"]))}</span><span>{arrow} OKX</span></div>'
            f'<div class="quote-price">{price(last)}</div>'
            f'<div class="quote-pnl">{live_r:+.2f}R · '
            f'{live_r * risk_per_trade:+,.2f} USDT</div></div>'
        )
        previous[inst_id] = last

    if not cards:
        st.warning("OKX chưa trả về giá cho các hợp đồng đang mở.")
        return

    now = pd.Timestamp.now(tz=VN_TZ)
    html = (
        '<div class="live-stamp"><i></i>'
        f'<span>Giá trực tiếp OKX · cập nhật mỗi 2 giây · {now:%H:%M:%S}</span>'
        f'<strong>Danh mục {total_live_r:+.2f}R · '
        f'{total_live_r * risk_per_trade:+,.2f} USDT</strong></div>'
        f'<div class="live-grid">{"".join(cards)}</div>'
    )
    st.markdown(html, unsafe_allow_html=True)


@st.cache_data(ttl=8, show_spinner=False)
def load_data(db_name):
    return get_backend(db_name).load()


def run_manual_scan():
    progress = st.progress(0, text="Đang tải danh sách thị trường OKX...")

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
          <div><strong>SONIC R</strong><br><span>BÀN TÍN HIỆU</span></div>
        </div>
        <div class="control-label">MÔ HÌNH RỦI RO</div>
        """,
        unsafe_allow_html=True,
    )
    capital = st.number_input(
        "Vốn mô phỏng · USDT", min_value=100.0, value=10_000.0, step=1_000.0
    )
    risk_pct = st.slider("Rủi ro mỗi lệnh · %", 0.25, 1.0, 0.5, 0.25)
    st.markdown('<div class="control-label">BỘ LỌC TÍN HIỆU</div>', unsafe_allow_html=True)
    direction_filter = st.segmented_control(
        "Hướng", ["Tất cả", "LONG", "SHORT"], default="Tất cả"
    )
    status_filter = st.multiselect(
        "Trạng thái thiết lập",
        ["READY", "WAIT_PA", "WAIT_PULLBACK", "NO_SETUP"],
        default=["READY", "WAIT_PA", "WAIT_PULLBACK"],
    )
    coin_query = st.text_input("Tìm đồng coin", placeholder="BTC, ETH, SOL...")
    st.markdown('<div class="control-label">THAO TÁC</div>', unsafe_allow_html=True)
    if st.button("QUÉT TOÀN BỘ", type="primary", width="stretch"):
        run_manual_scan()
    if st.button("LÀM MỚI DỮ LIỆU", width="stretch"):
        st.cache_data.clear()
        st.rerun()
    st.caption(
        "Chỉ mô phỏng, không đặt lệnh thật. Monitor vẫn chạy khi đóng trang."
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
    if pd.notna(last_scan) else "CHƯA CÓ DỮ LIỆU"
)
risk_usd = capital * risk_pct / 100

st.markdown(
    f"""
    <div class="terminal-header">
      <div class="terminal-title">
        <div class="brand-mark">SR</div>
        <div>
          <div class="eyebrow">BỘ QUÉT HỢP ĐỒNG VĨNH CỬU OKX</div>
          <h1>Bảng điều khiển tín hiệu</h1>
          <p>Quét đa khung thời gian · giao dịch mô phỏng · theo dõi danh mục</p>
        </div>
      </div>
      <div class="live-stack">
        <div class="live-pill {'online' if monitor_ok else 'offline'}">
          <span class="pulse-dot"></span>
          {'MONITOR ĐANG CHẠY' if monitor_ok else 'DỮ LIỆU ĐÃ CŨ'}
        </div>
        <small>Nến M15 tiếp theo · {next_close:%H:%M:%S} VN</small>
      </div>
    </div>
    <div class="context-strip">
      <div class="context-cell"><span>Lần đồng bộ cuối</span><strong>{scan_text} VN</strong></div>
      <div class="context-cell"><span>Chế độ thực thi</span><strong>MÔ PHỎNG · OHLCV</strong></div>
      <div class="context-cell"><span>Rủi ro phân bổ</span><strong>{risk_usd:,.2f} USDT / LỆNH</strong></div>
      <div class="context-cell"><span>Sàn / chu kỳ</span><strong>OKX · ĐÓNG NẾN M15</strong></div>
    </div>
    """,
    unsafe_allow_html=True,
)

if setups.empty:
    st.markdown(
        """
        <div class="empty-card">
          <strong>Chưa có dữ liệu quét</strong>
          Hãy quét toàn bộ hoặc chạy <code>python paper_monitor.py</code>.
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
    metric_columns[0], "Thị trường", success["symbol"].nunique(),
    "hợp đồng USDT", CYAN,
)
metric_card(
    metric_columns[1], "LONG sẵn sàng", int((ready["side"] == "LONG").sum()),
    "có thể hành động", GREEN,
)
metric_card(
    metric_columns[2], "SHORT sẵn sàng", int((ready["side"] == "SHORT").sum()),
    "có thể hành động", RED,
)
metric_card(metric_columns[3], "Đang chờ", len(waiting), "chờ xác nhận", "#d97706")
metric_card(metric_columns[4], "Vị thế mở", len(open_trades), "lệnh mô phỏng", "#1769aa")
metric_card(
    metric_columns[5], "Chất lượng dữ liệu", "TỐT" if data_errors == 0 else data_errors,
    "không có lỗi" if data_errors == 0 else "mã bị lỗi",
    GREEN if data_errors == 0 else RED,
)

command, scanner, positions, history, method = st.tabs(
    ["TỔNG QUAN", "BỘ QUÉT", "VỊ THẾ MỞ", "HIỆU SUẤT", "PHƯƠNG PHÁP"]
)

with command:
    execution, state = st.columns([3, 2])
    with execution:
        section_head(
            "DANH SÁCH HÀNH ĐỘNG", "Tín hiệu sẵn sàng",
            f"{len(ready)} thiết lập vượt qua đủ 5 điều kiện",
        )
        if ready.empty:
            st.markdown(
                """
                <div class="empty-card">
                  <strong>Chưa có tín hiệu đủ điều kiện</strong>
                  Hệ thống tiếp tục chờ đến khi một nến M15 đã đóng vượt qua đủ 5 điều kiện.
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
                    f" · dưới mức tối thiểu {row['min_contracts']:g}"
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
                        <div class="level"><span>Điểm vào</span><strong>{price(row['entry'])}</strong></div>
                        <div class="level"><span>Dừng lỗ · 1R</span><strong>{price(row['sl'])}</strong></div>
                        <div class="level"><span>TP1 · {row['tp1_rr']:.2f}R</span><strong>{price(row['tp1'])}</strong></div>
                        <div class="level"><span>TP2 · {row['tp2_rr']:.2f}R</span><strong>{price(row['tp2'])}</strong></div>
                      </div>
                      <div class="card-foot">
                        <span>{contracts:g} hợp đồng{escape(minimum)}</span>
                        <span>Giá trị {notional:,.0f} · rủi ro {actual_risk:.2f}</span>
                      </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
    with state:
        section_head(
            "TRẠNG THÁI THỊ TRƯỜNG", "Phân bổ thiết lập",
            f"{len(success):,} dòng tín hiệu",
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
            text=f"<b>{len(success):,}</b><br><span>THIẾT LẬP</span>",
            x=.5, y=.5, showarrow=False, font=dict(size=15, color="#dce7f5"),
        )
        style_plot(fig, 330)
        fig.update_layout(showlegend=True)
        st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})

    funnel_col, pulse_col = st.columns([3, 2])
    with funnel_col:
        section_head("BỘ LỌC", "Tỷ lệ vượt qua 5 điều kiện", "LONG so với SHORT")
        funnel = (
            success.groupby("side")[FILTERS].mean().mul(100).reset_index()
            .melt(id_vars="side", var_name="gate", value_name="pass_rate")
        )
        funnel["gate"] = funnel["gate"].map(FILTER_NAMES)
        fig = px.bar(
            funnel, x="pass_rate", y="gate", color="side", barmode="group",
            orientation="h", text_auto=".1f",
            color_discrete_map={"LONG": GREEN, "SHORT": RED},
            labels={"gate": "", "pass_rate": "Tỷ lệ đạt · %", "side": ""},
        )
        fig.update_traces(textposition="outside", cliponaxis=False)
        style_plot(fig, 360)
        fig.update_xaxes(range=[0, max(105, funnel["pass_rate"].max() + 8)])
        fig.update_yaxes(categoryorder="array", categoryarray=list(FILTER_NAMES.values())[::-1])
        st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
    with pulse_col:
        section_head("NHỊP QUÉT", "Tín hiệu qua từng lần quét", "96 chu kỳ gần nhất")
        if runs.empty:
            st.markdown('<div class="empty-card">Chưa có lịch sử quét</div>', unsafe_allow_html=True)
        else:
            timeline = runs.sort_values("scanned_at").copy()
            timeline["Time"] = timeline["scanned_at"].dt.tz_convert(VN_TZ)
            fig = px.line(
                timeline, x="Time", y=["long_ready", "short_ready"], markers=True,
                color_discrete_map={"long_ready": GREEN, "short_ready": RED},
                labels={"value": "Tín hiệu sẵn sàng", "variable": "", "Time": ""},
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
            "READY": "SẴN SÀNG",
            "WAIT_PA": "CHỜ · PA",
            "WAIT_PULLBACK": "CHỜ · VÙNG GIÁ TRỊ",
            "NO_SETUP": "CHƯA CÓ",
            "ERROR": "LỖI DỮ LIỆU",
        }
    )
    view["Gate score"] = view[FILTERS].sum(axis=1)
    view["Last"] = view["bar_close"]
    section_head(
        "MA TRẬN TÍN HIỆU", "Bộ quét toàn thị trường",
        f"Đang hiển thị {len(view)} dòng · dữ liệu {scan_text} VN",
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
            "Asset": st.column_config.TextColumn("TÀI SẢN", width="medium"),
            "side": st.column_config.TextColumn("HƯỚNG", width="small"),
            "State": st.column_config.TextColumn("TRẠNG THÁI", width="medium"),
            "Gate score": st.column_config.ProgressColumn(
                "ĐIỀU KIỆN", min_value=0, max_value=5, format="%d / 5", width="small"
            ),
            "Last": st.column_config.NumberColumn("GIÁ ĐÓNG GẦN NHẤT", format="%.8f"),
            "pa": st.column_config.TextColumn("HÀNH ĐỘNG GIÁ"),
            "missing": st.column_config.TextColumn("ĐIỀU KIỆN CÒN THIẾU", width="large"),
        },
    )
    download, note = st.columns([1, 4])
    download.download_button(
        "XUẤT DỮ LIỆU CSV", report.to_csv(index=False),
        "sonic_r_okx_snapshot.csv", "text/csv", width="stretch",
    )
    note.caption(
        "Điểm điều kiện chỉ dùng để chẩn đoán. Tín hiệu chỉ hợp lệ khi nến M15 đã đóng đạt đủ năm điều kiện."
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
    metric_card(exposure_metrics[0], "Vị thế mở", len(open_trades), "sổ lệnh mô phỏng", "#1769aa")
    metric_card(exposure_metrics[1], "Phân bổ hướng", f"{long_open}L / {short_open}S", "vị thế đang chạy", CYAN)
    metric_card(
        exposure_metrics[2], "Lãi/lỗ tạm tính", f"{total_float:+.2f}R",
        f"{total_float * risk_usd:+,.2f} USDT", GREEN if total_float >= 0 else RED,
    )
    metric_card(
        exposure_metrics[3], "Rủi ro ban đầu", f"{len(open_trades) * risk_usd:,.2f}",
        "USDT phân bổ gộp", "#d97706",
    )
    section_head(
        "GIÁ TRỰC TIẾP", "Định giá vị thế theo OKX",
        "chỉ hiển thị · không thay đổi quy tắc đóng lệnh",
    )
    live_position_quotes(open_trades, risk_usd)
    section_head("SỔ LỆNH MÔ PHỎNG", "Các vị thế đang mở", "định giá theo nến M15 đã đóng gần nhất")
    if open_trades.empty:
        st.markdown(
            '<div class="empty-card"><strong>Chưa có vị thế</strong>Không có lệnh mô phỏng nào đang mở.</div>',
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
                    <div class="level"><span>Giá hiện tại</span><strong>{price(current)}</strong></div>
                    <div class="level"><span>Điểm vào</span><strong>{price(trade['entry'])}</strong></div>
                    <div class="level"><span>Dừng lỗ</span><strong>{price(trade['current_sl'])}</strong></div>
                    <div class="level"><span>Bám EMA H1</span><strong>{price(trade['trail_h1'])}</strong></div>
                    <div class="level"><span>TP1</span><strong>{tp1}</strong></div>
                    <div class="level"><span>TP2</span><strong>{tp2}</strong></div>
                    <div class="level"><span>MFE</span><strong>{trade['mfe_r']:+.2f}R</strong></div>
                    <div class="level"><span>MAE</span><strong>{trade['mae_r']:+.2f}R</strong></div>
                  </div>
                  <div class="progress-track"><div class="progress-fill" style="width:{closed_pct:.0f}%"></div></div>
                  <div class="card-foot">
                    <span>Đã chốt {closed_pct:.0f}%</span>
                    <span>Đã ghi nhận {trade['realized_r']:+.2f}R · còn {trade['remaining']:.0%}</span>
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
    metric_card(performance_metrics[0], "Lệnh đã đóng", len(closed_trades), "mẫu mô phỏng", CYAN)
    metric_card(performance_metrics[1], "Tỷ lệ thắng", f"{winrate:.1f}%", "chỉ tính lệnh đã đóng", GREEN)
    metric_card(
        performance_metrics[2], "Kỳ vọng ròng", f"{avg_r:+.2f}R",
        f"tổng {total_r:+.2f}R", GREEN if avg_r >= 0 else RED,
    )
    metric_card(
        performance_metrics[3], "Lãi/lỗ mô phỏng", f"{total_r * risk_usd:+,.2f}",
        "USDT · rủi ro cố định", GREEN if total_r >= 0 else RED,
    )
    equity_col, events_col = st.columns([3, 2])
    with equity_col:
        section_head("HIỆU SUẤT", "Đường vốn mô phỏng", "mô hình rủi ro cố định")
        if closed_trades.empty:
            st.markdown(
                '<div class="empty-card"><strong>Đang chờ đóng lệnh</strong>Đường vốn bắt đầu sau khi lệnh mô phỏng đầu tiên đóng.</div>',
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
        section_head("NHẬT KÝ", "Sự kiện thực thi", f"{min(500, len(events))} sự kiện gần nhất")
        if events.empty:
            st.markdown('<div class="empty-card">Chưa có sự kiện thực thi</div>', unsafe_allow_html=True)
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
                    "Time": st.column_config.DatetimeColumn("THỜI GIAN · VN", format="DD/MM HH:mm"),
                    "symbol": "MÃ", "side": "HƯỚNG", "event": "SỰ KIỆN",
                    "price": st.column_config.NumberColumn("GIÁ", format="%.8f"),
                    "delta_r": st.column_config.NumberColumn("THAY ĐỔI", format="%+.2fR"),
                },
            )
    if not closed_trades.empty:
        section_head("SỔ GIAO DỊCH", "Các vị thế đã đóng", f"{len(closed_trades)} bản ghi")
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
        "QUY TRÌNH HỆ THỐNG", "Từ bối cảnh thị trường đến điểm vào",
        "logic cố định · chỉ dùng nến đã đóng",
    )
    steps = [
        ("01", "Xu hướng EMA", "EMA34/89 trên H1 xác định hướng giao dịch được phép."),
        ("02", "Phá vỡ biên", "Phá vỡ biên 20 nến có hiệu lực trong 30 nến H1."),
        ("03", "Cấu trúc Dow", "LONG cần HH/HL; SHORT cần LL/LH."),
        ("04", "Vùng giá trị", "Giá hồi về vùng EMA của Sonic R."),
        ("05", "Kích hoạt M15", "Nến engulfing hoặc pinbar đã đóng xác nhận điểm vào."),
    ]
    cards = "".join(
        f'<div class="play-step"><div class="num">{number}</div>'
        f"<strong>{escape(title)}</strong><span>{escape(text)}</span></div>"
        for number, title, text in steps
    )
    st.markdown(f'<div class="playbook">{cards}</div>', unsafe_allow_html=True)

    execution_rule, controls = st.columns(2)
    with execution_rule:
        section_head("MÔ HÌNH THỰC THI", "Vòng đời vị thế")
        st.markdown(
            """
            - Vào tại giá đóng của nến M15 xác nhận; không dùng tín hiệu khi nến chưa đóng.
            - Dừng lỗ ban đầu dùng swing 5 nến hoặc EMA89 cộng vùng đệm 0,5 ATR.
            - TP1 chốt 50%, sau đó dời dừng lỗ phần còn lại về hòa vốn.
            - TP2 chốt thêm 30%; 20% cuối bám theo EMA34 trên H1.
            - Nếu SL và TP cùng chạm trong một nến, mô phỏng ưu tiên xử lý SL.
            """
        )
    with controls:
        section_head("KIỂM SOÁT RỦI RO", "Giới hạn của hệ thống")
        st.markdown(
            """
            - Không lưu thông tin đăng nhập sàn và không gửi lệnh thật.
            - Không vào lệnh từ nến M15 hoặc H1 chưa hoàn tất.
            - Không tinh chỉnh tham số sau khi đã quan sát kết quả thuận lợi.
            - Lãi/lỗ mô phỏng chưa tính funding, trượt giá và độ trễ khớp lệnh thật.
            - Tín hiệu SẴN SÀNG là kết quả mô hình, không phải cam kết lợi nhuận.
            """
        )
    with st.expander("Định nghĩa chính xác của từng điều kiện"):
        st.write("**LONG:** " + " → ".join(FILTER_LABELS.values()))
        st.write("**SHORT:** " + " → ".join(SHORT_FILTER_LABELS.values()))
