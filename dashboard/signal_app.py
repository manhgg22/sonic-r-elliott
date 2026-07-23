"""Signal Center: toàn bộ perpetual USDT crypto trên OKX."""

import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import timedelta, timezone
from math import floor
from pathlib import Path
from threading import local

sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import streamlit as st
import ccxt

from core.trade_setup import (
    FILTER_LABELS,
    SHORT_FILTER_LABELS,
    latest_trade_setup,
)
from data.loader import (
    data_quality_check,
    fetch_ohlcv,
    okx_usdt_swap_universe,
)


VN_TZ = timezone(timedelta(hours=7))
THREAD_STATE = local()
SCAN_VERSION = 2

st.set_page_config(page_title="Sonic R Signal Center", page_icon="🐉", layout="wide")
st.title("🐉 Sonic R Signal Center — TOÀN BỘ OKX")
st.caption(
    "Quét LONG và SHORT trên toàn bộ perpetual USDT crypto active. "
    "Chỉ phát tín hiệu từ nến đã đóng."
)


@st.cache_data(ttl=900, show_spinner=False)
def load_universe():
    return okx_usdt_swap_universe()


def scanner_exchange():
    if not hasattr(THREAD_STATE, "exchange"):
        THREAD_STATE.exchange = ccxt.okx({"enableRateLimit": True})
        THREAD_STATE.exchange.load_markets()
    return THREAD_STATE.exchange


def scan_one(meta):
    symbol = meta["symbol"]
    try:
        exchange = scanner_exchange()
        entry = fetch_ohlcv(
            symbol, "15m", 3, exchange_id="okx",
            exchange=exchange, cache_max_age=300, verbose=False,
        )
        main = fetch_ohlcv(
            symbol, "1H", 12, exchange_id="okx",
            exchange=exchange, cache_max_age=300, verbose=False,
        )
        for frame, timeframe in [(entry, "15m"), (main, "1H")]:
            quality = data_quality_check(frame, timeframe)
            if not quality["ok"]:
                raise RuntimeError(f"dữ liệu {timeframe} lỗi")
        return [
            {
                **meta,
                **latest_trade_setup(symbol, entry, main, side=side),
            }
            for side in ("LONG", "SHORT")
        ]
    except Exception as exc:
        return [
            {
                **meta,
                "side": side,
                "status": "ERROR",
                "actionable": False,
                "missing": str(exc),
            }
            for side in ("LONG", "SHORT")
        ]


def run_scan(universe):
    rows = []
    progress = st.progress(0, text="Đang quét OKX...")
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(scan_one, meta) for meta in universe]
        for done, future in enumerate(as_completed(futures), 1):
            rows.extend(future.result())
            progress.progress(done / len(futures), text=f"Đã quét {done}/{len(futures)}")
    progress.empty()
    return pd.DataFrame(rows)


def price(value):
    if pd.isna(value):
        return "-"
    if value >= 1000:
        return f"{value:,.2f}"
    if value >= 1:
        return f"{value:,.4f}"
    return f"{value:.8f}"


with st.sidebar:
    st.header("Quản trị rủi ro")
    capital = st.number_input(
        "Vốn cấp cho mỗi lệnh (USDT)", min_value=10.0, value=1000.0, step=100.0
    )
    risk_pct = st.slider("Rủi ro tối đa mỗi lệnh", 0.25, 1.0, 0.5, 0.25)
    direction_filter = st.selectbox("Hướng hiển thị", ["Tất cả", "LONG", "SHORT"])
    show_no_setup = st.checkbox("Hiện cả coin chưa có setup", value=False)
    coin_query = st.text_input("Tìm coin", placeholder="BTC, ETH...")
    st.caption("Khối lượng hợp đồng chỉ là ước tính, không tự gửi lệnh.")
    scan_clicked = st.button("QUÉT TOÀN BỘ", type="primary", width="stretch")

try:
    universe = load_universe()
except Exception as exc:
    st.error(f"Không tải được universe: {exc}")
    st.stop()

if (
    scan_clicked
    or st.session_state.get("signal_scan_version") != SCAN_VERSION
):
    st.session_state.signal_scan = run_scan(universe)
    st.session_state.signal_scan_at = pd.Timestamp.now(tz=VN_TZ)
    st.session_state.signal_scan_version = SCAN_VERSION
elif "signal_scan_at" not in st.session_state:
    st.session_state.signal_scan_at = pd.Timestamp.now(tz=VN_TZ)

raw_report = st.session_state.signal_scan.copy()
st.caption(
    f"Lần quét: {st.session_state.signal_scan_at:%d/%m/%Y %H:%M:%S} "
    "(giờ Việt Nam) — cache tối đa 5 phút."
)
status_order = {"READY": 0, "WAIT_PA": 1, "WAIT_PULLBACK": 2, "NO_SETUP": 3, "ERROR": 4}
errors = raw_report[raw_report["status"] == "ERROR"].sort_values("rank")
report = raw_report[raw_report["status"] != "ERROR"].copy()
report["_order"] = report["status"].map(status_order).fillna(9)
report = report.sort_values(["_order", "base", "side"]).drop(columns="_order")

ready = report[report["status"] == "READY"]
wait = report[report["status"].isin(["WAIT_PA", "WAIT_PULLBACK"])]
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Coin đã quét", report["symbol"].nunique())
c2.metric("LONG READY", len(ready[ready["side"] == "LONG"]))
c3.metric("SHORT READY", len(ready[ready["side"] == "SHORT"]))
c4.metric("Đang chờ", len(wait))
c5.metric("Coin lỗi dữ liệu", errors["symbol"].nunique())
if not errors.empty:
    st.caption(
        "Không đủ dữ liệu: "
        + ", ".join(errors["base"].drop_duplicates().head(20))
    )

st.subheader("Tín hiệu có thể hành động")
if ready.empty:
    st.info("Hiện chưa có LONG/SHORT READY. Không đủ setup thì không giao dịch.")
else:
    for _, row in ready.iterrows():
        risk_per_unit = abs(row["entry"] - row["sl"])
        base_qty = capital * risk_pct / 100 / risk_per_unit
        raw_contracts = base_qty / row["contract_size"]
        contracts = floor(raw_contracts / row["amount_step"]) * row["amount_step"]
        below_minimum = contracts < row["min_contracts"]
        actual_risk = contracts * row["contract_size"] * risk_per_unit
        notional = contracts * row["contract_size"] * row["entry"]
        signal_time = pd.Timestamp(row["signal_time"]).tz_convert(VN_TZ)
        alert = st.success if row["side"] == "LONG" else st.error
        alert(
            f"{row['side']} {row['symbol']} — "
            f"nến xác nhận {signal_time:%d/%m %H:%M} VN"
        )
        cols = st.columns(8)
        for column, label, value in [
            (cols[0], "Entry", price(row["entry"])),
            (cols[1], "SL", price(row["sl"])),
            (cols[2], f"TP1 50% ({row['tp1_rr']}R)", price(row["tp1"])),
            (cols[3], f"TP2 30% ({row['tp2_rr']}R)", price(row["tp2"])),
            (cols[4], "Trail 20%", price(row["trail_h1"])),
            (cols[5], "Hợp đồng ~", f"{contracts:g}"),
            (cols[6], "Notional ~", f"{notional:,.2f} USDT"),
            (cols[7], "Risk thực ~", f"{actual_risk:.2f} USDT"),
        ]:
            column.metric(label, value)
        trail_rule = "dưới EMA34-low" if row["side"] == "LONG" else "trên EMA34-high"
        st.caption(f"PA: {row['pa']}. Runner thoát khi M15 đóng {trail_rule} H1.")
        if below_minimum:
            st.warning(
                f"Vốn/risk hiện tại nhỏ hơn minimum {row['min_contracts']:g} "
                "hợp đồng OKX; không vào lệnh này."
            )

st.subheader("Bảng quét toàn bộ OKX")
view = report.copy()
if direction_filter != "Tất cả":
    view = view[view["side"] == direction_filter]
if not show_no_setup:
    view = view[view["status"] != "NO_SETUP"]
if coin_query.strip():
    query = coin_query.strip().upper()
    view = view[view["base"].str.contains(query, regex=False)]
view["Coin"] = view["name"] + " (" + view["base"] + ")"
view["Tín hiệu"] = view["status"].replace({
    "READY": "🟢 READY",
    "WAIT_PA": "🟡 Chờ PA",
    "WAIT_PULLBACK": "🔵 Chờ hồi VZ",
    "NO_SETUP": "⚪ Không setup",
    "ERROR": "🔴 Lỗi",
})
for source, target in [
    ("f_trend", "EMA"),
    ("f_breakout", "Breakout"),
    ("f_dow", "Dow"),
    ("f_value_zone", "VZ"),
    ("f_pa", "PA"),
]:
    values = (
        view[source].astype("boolean").fillna(False).astype(bool)
        if source in view
        else pd.Series(False, index=view.index)
    )
    view[target] = values.map({True: "✓", False: "—"})
view["Thiếu"] = view["missing"]
columns = [
    "rank", "Coin", "side", "symbol", "Tín hiệu",
    "EMA", "Breakout", "Dow", "VZ", "PA", "Thiếu",
]
st.dataframe(
    view[columns],
    hide_index=True,
    width="stretch",
    column_config={"rank": st.column_config.NumberColumn("#", format="%d")},
)
st.download_button(
    "Tải bảng quét CSV",
    report.drop(columns=[column for column in report if column.startswith("_")])
    .to_csv(index=False),
    "sonic_r_okx_all_signals.csv",
    "text/csv",
)

with st.expander("Quy tắc cố định của setup"):
    st.write("**LONG**")
    st.write(", ".join(FILTER_LABELS.values()))
    st.write("**SHORT**")
    st.write(", ".join(SHORT_FILTER_LABELS.values()))
    st.write(
        "- TP1: chốt 50% tại Fibo 1.618; TP2: chốt 30% tại 2.618; "
        "20% còn lại trailing EMA34-low/high H1 theo hướng lệnh."
    )
    st.write("- Chỉ vào LONG/SHORT sau khi nến M15 xác nhận.")
    st.warning(
        "Perpetual có đòn bẩy và rủi ro thanh lý. Ứng dụng là signal/paper-trading, "
        "không tự đặt lệnh và không phải cam kết lợi nhuận."
    )
