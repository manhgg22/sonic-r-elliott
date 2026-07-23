"""Dashboard scanner và paper trading toàn bộ OKX."""

import sys
from datetime import timedelta, timezone
from math import floor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import plotly.express as px
import streamlit as st

from core.trade_setup import FILTER_LABELS, SHORT_FILTER_LABELS
from paper_monitor import DB_PATH, connect, run_cycle, seconds_to_next_close


VN_TZ = timezone(timedelta(hours=7))
STATUS_ORDER = {
    "READY": 0, "WAIT_PA": 1, "WAIT_PULLBACK": 2, "NO_SETUP": 3, "ERROR": 4
}
FILTERS = ["f_trend", "f_breakout", "f_dow", "f_value_zone", "f_pa"]
FILTER_NAMES = {
    "f_trend": "EMA trend",
    "f_breakout": "Breakout",
    "f_dow": "Dow",
    "f_value_zone": "Value Zone",
    "f_pa": "Price Action",
}

st.set_page_config(
    page_title="Sonic R Night Watch", page_icon="🐉", layout="wide",
    initial_sidebar_state="expanded",
)
st.markdown(
    """
    <style>
    .stApp {
      background:
        radial-gradient(circle at 80% 0%, rgba(16,185,129,.10), transparent 28rem),
        radial-gradient(circle at 10% 15%, rgba(59,130,246,.09), transparent 24rem);
    }
    [data-testid="stMetric"] {
      background: rgba(15,23,42,.035); border: 1px solid rgba(148,163,184,.22);
      padding: .85rem 1rem; border-radius: 14px;
    }
    [data-testid="stMetricValue"] { font-size: 1.65rem; }
    .block-container { padding-top: 2rem; max-width: 1500px; }
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
        with st.spinner("Quét nến M15/H1 đã đóng và cập nhật paper trades..."):
            summary = run_cycle(DB_PATH, progress=update)
        st.session_state.scan_summary = summary
        st.cache_data.clear()
    finally:
        progress.empty()


with st.sidebar:
    st.header("Bộ điều khiển")
    capital = st.number_input(
        "Vốn mô phỏng (USDT)", min_value=100.0, value=10_000.0, step=1_000.0
    )
    risk_pct = st.slider("Risk / lệnh", 0.25, 1.0, 0.5, 0.25)
    direction_filter = st.segmented_control(
        "Hướng", ["Tất cả", "LONG", "SHORT"], default="Tất cả"
    )
    status_filter = st.multiselect(
        "Trạng thái",
        ["READY", "WAIT_PA", "WAIT_PULLBACK", "NO_SETUP"],
        default=["READY", "WAIT_PA", "WAIT_PULLBACK"],
    )
    coin_query = st.text_input("Tìm coin", placeholder="BTC, ETH, SOL...")
    if st.button("QUÉT NGAY", type="primary", width="stretch"):
        run_manual_scan()
    if st.button("LÀM MỚI DASHBOARD", width="stretch"):
        st.cache_data.clear()
        st.rerun()
    st.caption(
        "Monitor độc lập vẫn chạy khi đóng trình duyệt. QUÉT NGAY chỉ ép thêm một lượt."
    )

setups, runs, trades, events = load_data(str(DB_PATH))
last_scan = runs["scanned_at"].max() if not runs.empty else pd.NaT
age_minutes = (
    (pd.Timestamp.now(tz="UTC") - last_scan).total_seconds() / 60
    if pd.notna(last_scan) else float("inf")
)
monitor_ok = age_minutes < 30
next_close = pd.Timestamp.now(tz=VN_TZ) + timedelta(
    seconds=seconds_to_next_close()
)

header_left, header_right = st.columns([4, 1])
with header_left:
    st.title("🐉 Sonic R · Night Watch")
    st.caption(
        "Scanner toàn bộ perpetual USDT crypto trên OKX · LONG + SHORT · "
        "paper trading từ nến M15 đã đóng"
    )
with header_right:
    if monitor_ok:
        st.success("● MONITOR ONLINE")
    else:
        st.error("● MONITOR CHƯA CÓ DỮ LIỆU")
    st.caption(f"Nến kế tiếp: {next_close:%H:%M:%S} VN")

if setups.empty:
    st.warning(
        "Chưa có lượt quét nào trong SQLite. Bấm **QUÉT NGAY** hoặc chạy "
        "`python paper_monitor.py` để bắt đầu theo dõi qua đêm."
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

scan_text = (
    last_scan.tz_convert(VN_TZ).strftime("%d/%m/%Y %H:%M:%S")
    if pd.notna(last_scan) else "—"
)
st.caption(
    f"Lần quét gần nhất: **{scan_text} VN** · {age_minutes:.1f} phút trước · "
    f"paper model: risk cố định {capital * risk_pct / 100:,.2f} USDT / lệnh"
)

k1, k2, k3, k4, k5, k6 = st.columns(6)
k1.metric("Coin quét thành công", success["symbol"].nunique())
k2.metric("LONG READY", int((ready["side"] == "LONG").sum()))
k3.metric("SHORT READY", int((ready["side"] == "SHORT").sum()))
k4.metric("Đang chờ", len(waiting))
k5.metric("Vị thế paper", len(open_trades))
k6.metric("Lỗi dữ liệu", report.loc[report["status"] == "ERROR", "symbol"].nunique())

overview, scanner, positions, history, method = st.tabs(
    ["TỔNG QUAN", "SCANNER", "VỊ THẾ PAPER", "NHẬT KÝ & EQUITY", "QUY TẮC"]
)

with overview:
    st.subheader("Tín hiệu có thể hành động")
    if ready.empty:
        st.info("Chưa có setup READY ở nến gần nhất. Không đủ 5 gate thì không vào.")
    else:
        card_columns = st.columns(2)
        for index, (_, row) in enumerate(ready.iterrows()):
            with card_columns[index % 2]:
                with st.container(border=True):
                    signal_time = row["signal_time"].tz_convert(VN_TZ)
                    badge = "🟢" if row["side"] == "LONG" else "🔴"
                    st.markdown(
                        f"### {badge} {row['side']} · {row['base']}  \n"
                        f"`{row['symbol']}` · xác nhận {signal_time:%d/%m %H:%M} VN"
                    )
                    risk_per_unit = abs(row["entry"] - row["sl"])
                    base_qty = capital * risk_pct / 100 / risk_per_unit
                    raw_contracts = base_qty / row["contract_size"]
                    contracts = (
                        floor(raw_contracts / row["amount_step"]) * row["amount_step"]
                    )
                    actual_risk = contracts * row["contract_size"] * risk_per_unit
                    notional = contracts * row["contract_size"] * row["entry"]
                    a, b, c, d = st.columns(4)
                    a.metric("Entry", price(row["entry"]))
                    b.metric("SL · −1R", price(row["sl"]))
                    c.metric(f"TP1 · {row['tp1_rr']:.2f}R", price(row["tp1"]))
                    d.metric(f"TP2 · {row['tp2_rr']:.2f}R", price(row["tp2"]))
                    st.caption(
                        f"PA **{row['pa']}** · trail H1 **{price(row['trail_h1'])}** · "
                        f"ước tính **{contracts:g} contracts** · "
                        f"notional **{notional:,.2f} USDT** · risk **{actual_risk:.2f} USDT**"
                    )
                    if contracts < row["min_contracts"]:
                        st.warning(
                            f"Khối lượng dưới minimum OKX {row['min_contracts']:g} contracts."
                        )

    left, right = st.columns([3, 2])
    with left:
        st.subheader("Funnel 5 gate")
        funnel = (
            success.groupby("side")[FILTERS].mean().mul(100).reset_index()
            .melt(id_vars="side", var_name="gate", value_name="pass_rate")
        )
        funnel["gate"] = funnel["gate"].map(FILTER_NAMES)
        fig = px.bar(
            funnel, x="gate", y="pass_rate", color="side", barmode="group",
            text_auto=".1f", color_discrete_map={"LONG": "#10b981", "SHORT": "#ef4444"},
            labels={"gate": "", "pass_rate": "% nến pass", "side": "Hướng"},
        )
        fig.update_layout(height=360, margin=dict(l=10, r=10, t=20, b=10))
        st.plotly_chart(fig, width="stretch")
    with right:
        st.subheader("Nhịp scanner gần đây")
        if runs.empty:
            st.info("Chưa có lịch sử scan.")
        else:
            timeline = runs.sort_values("scanned_at").copy()
            timeline["Giờ VN"] = timeline["scanned_at"].dt.tz_convert(VN_TZ)
            fig = px.line(
                timeline, x="Giờ VN", y=["long_ready", "short_ready"],
                markers=True,
                color_discrete_map={
                    "long_ready": "#10b981", "short_ready": "#ef4444"
                },
                labels={"value": "Số tín hiệu", "variable": "", "Giờ VN": ""},
            )
            fig.update_layout(height=360, margin=dict(l=10, r=10, t=20, b=10))
            st.plotly_chart(fig, width="stretch")

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
    view["Coin"] = view["name"] + " (" + view["base"] + ")"
    view["Trạng thái"] = view["status"].replace(
        {
            "READY": "🟢 READY",
            "WAIT_PA": "🟡 Chờ PA",
            "WAIT_PULLBACK": "🔵 Chờ hồi VZ",
            "NO_SETUP": "⚪ Không setup",
            "ERROR": "🔴 Lỗi",
        }
    )
    for source, target in [
        ("f_trend", "EMA"), ("f_breakout", "Breakout"), ("f_dow", "Dow"),
        ("f_value_zone", "VZ"), ("f_pa", "PA"),
    ]:
        view[target] = view[source].map({True: "✓", False: "—"})
    st.dataframe(
        view[
            [
                "rank", "Coin", "side", "Trạng thái", "EMA", "Breakout",
                "Dow", "VZ", "PA", "bar_close", "missing",
            ]
        ],
        hide_index=True,
        width="stretch",
        height=650,
        column_config={
            "rank": st.column_config.NumberColumn("#", format="%d"),
            "bar_close": st.column_config.NumberColumn("Giá đóng", format="%.8f"),
            "missing": "Điều kiện còn thiếu",
        },
    )
    st.download_button(
        "Tải snapshot CSV", report.to_csv(index=False),
        "sonic_r_okx_snapshot.csv", "text/csv",
    )

with positions:
    if open_trades.empty:
        st.info("Chưa có vị thế paper đang mở.")
    else:
        latest_price = success.set_index(["symbol", "side"])["bar_close"].to_dict()
        for _, trade in open_trades.sort_values("opened_at", ascending=False).iterrows():
            current = latest_price.get((trade["symbol"], trade["side"]), trade["entry"])
            direction = 1 if trade["side"] == "LONG" else -1
            floating = (
                trade["realized_r"]
                + trade["remaining"] * (current - trade["entry"]) * direction / trade["risk"]
            )
            with st.container(border=True):
                title, pnl = st.columns([4, 1])
                opened_at = trade["opened_at"].tz_convert(VN_TZ)
                title.markdown(
                    f"### {'🟢' if trade['side'] == 'LONG' else '🔴'} "
                    f"{trade['side']} · {trade['base']}  \n"
                    f"Mở {opened_at:%d/%m %H:%M} VN · #{trade['id']}"
                )
                pnl.metric("R tạm tính", f"{floating:+.2f}R")
                cols = st.columns(7)
                for column, label, value in [
                    (cols[0], "Hiện tại", price(current)),
                    (cols[1], "Entry", price(trade["entry"])),
                    (cols[2], "SL hiện tại", price(trade["current_sl"])),
                    (cols[3], "TP1", "Đạt" if trade["tp1_hit"] else price(trade["tp1"])),
                    (cols[4], "TP2", "Đạt" if trade["tp2_hit"] else price(trade["tp2"])),
                    (cols[5], "MFE", f"{trade['mfe_r']:+.2f}R"),
                    (cols[6], "MAE", f"{trade['mae_r']:+.2f}R"),
                ]:
                    column.metric(label, value)
                st.progress(
                    max(0.0, min(1.0, 1 - trade["remaining"])),
                    text=f"Đã chốt {100 * (1 - trade['remaining']):.0f}% · "
                    f"đã ghi nhận {trade['realized_r']:+.2f}R",
                )

with history:
    risk_usd = capital * risk_pct / 100
    h1, h2, h3, h4 = st.columns(4)
    total_r = closed_trades["total_r"].sum() if not closed_trades.empty else 0.0
    winrate = (
        100 * (closed_trades["total_r"] > 0).mean()
        if not closed_trades.empty else 0.0
    )
    h1.metric("Lệnh đã đóng", len(closed_trades))
    h2.metric("Winrate paper", f"{winrate:.1f}%")
    h3.metric("Tổng R", f"{total_r:+.2f}R")
    h4.metric("PnL mô hình", f"{total_r * risk_usd:+,.2f} USDT")

    if closed_trades.empty:
        st.info("Cần ít nhất một lệnh đóng để vẽ equity.")
    else:
        equity = closed_trades.sort_values("closed_at").copy()
        equity["Equity"] = capital + equity["total_r"].cumsum() * risk_usd
        fig = px.area(
            equity, x="closed_at", y="Equity", markers=True,
            labels={"closed_at": "Thời gian UTC", "Equity": "USDT"},
        )
        fig.update_traces(line_color="#10b981", fillcolor="rgba(16,185,129,.18)")
        fig.update_layout(height=360, margin=dict(l=10, r=10, t=20, b=10))
        st.plotly_chart(fig, width="stretch")
        table = equity[
            [
                "id", "symbol", "side", "opened_at", "closed_at",
                "exit_reason", "total_r", "mfe_r", "mae_r",
            ]
        ].sort_values("closed_at", ascending=False)
        st.dataframe(table, hide_index=True, width="stretch")

    st.subheader("Dòng sự kiện")
    if events.empty:
        st.caption("Chưa có sự kiện.")
    else:
        event_view = events.merge(
            trades[["id", "symbol", "side"]],
            left_on="trade_id", right_on="id", how="left", suffixes=("", "_trade"),
        )
        event_view["Giờ VN"] = event_view["event_at"].dt.tz_convert(VN_TZ)
        st.dataframe(
            event_view[
                ["Giờ VN", "trade_id", "symbol", "side", "event", "price", "delta_r"]
            ],
            hide_index=True, width="stretch",
        )

with method:
    st.subheader("Một tín hiệu đi qua hệ thống như thế nào")
    steps = [
        ("1", "EMA H1", "Xác định hướng 34/89"),
        ("2", "Breakout", "Phá vùng 20 nến, hiệu lực 30 nến"),
        ("3", "Cấu trúc Dow", "LONG HH/HL · SHORT LL/LH"),
        ("4", "Value Zone", "Giá hồi về vùng EMA"),
        ("5", "PA M15", "Engulfing hoặc pinbar đã đóng"),
    ]
    for column, (number, title, text) in zip(st.columns(5), steps):
        with column:
            with st.container(border=True):
                st.markdown(f"### {number} · {title}")
                st.caption(text)
    st.markdown(
        """
        **Mô phỏng khớp lệnh**

        - Mở tại giá đóng nến M15 làm đủ 5 gate; không đuổi giá intrabar.
        - SL ban đầu: swing 5 nến/EMA89 cộng buffer 0.5 ATR.
        - TP1 chốt 50%, dời SL phần còn lại về hòa vốn; TP2 chốt thêm 30%.
        - 20% runner thoát khi M15 đóng xuyên trail EMA34 H1.
        - Nếu một nến đồng thời chạm SL và TP, mô phỏng ưu tiên SL để không tô hồng.
        """
    )
    st.warning(
        "Đây là paper trading theo OHLCV, chưa mô hình hóa funding, trượt giá và "
        "độ trễ khớp lệnh. Hệ thống không có API key và không gửi lệnh thật."
    )
    with st.expander("Năm gate chính xác"):
        st.write("**LONG:** " + " → ".join(FILTER_LABELS.values()))
        st.write("**SHORT:** " + " → ".join(SHORT_FILTER_LABELS.values()))
