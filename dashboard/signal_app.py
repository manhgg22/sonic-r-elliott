"""Signal Center: top-20 vốn hóa có spot USDT trên OKX."""

import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import streamlit as st

from core.trade_setup import FILTER_LABELS, latest_trade_setup
from data.loader import data_quality_check, fetch_ohlcv, top_market_cap_universe


VN_TZ = timezone(timedelta(hours=7))

st.set_page_config(page_title="Sonic R Signal Center", page_icon="🐉", layout="wide")
st.title("🐉 Sonic R Signal Center — OKX TOP20")
st.caption(
    "BUY khi đủ Dow + EMA34/89 + breakout + hồi Value Zone + Price Action. "
    "Chỉ dùng nến đã đóng."
)


@st.cache_data(ttl=900, show_spinner=False)
def load_universe():
    # Lấy dư ứng viên vì market active đôi khi chưa có đủ lịch sử nến.
    return top_market_cap_universe("okx", 30)


def scan_one(meta):
    symbol = meta["symbol"]
    try:
        entry = fetch_ohlcv(
            symbol, "15m", 14, exchange_id="okx",
            cache_max_age=300, verbose=False,
        )
        main = fetch_ohlcv(
            symbol, "1H", 120, exchange_id="okx",
            cache_max_age=300, verbose=False,
        )
        for frame, timeframe in [(entry, "15m"), (main, "1H")]:
            quality = data_quality_check(frame, timeframe)
            if not quality["ok"]:
                raise RuntimeError(f"dữ liệu {timeframe} lỗi")
        return {**meta, **latest_trade_setup(symbol, entry, main)}
    except Exception as exc:
        return {
            **meta,
            "status": "ERROR",
            "actionable": False,
            "missing": str(exc),
        }


def run_scan(universe):
    rows = []
    progress = st.progress(0, text="Đang quét OKX...")
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(scan_one, meta) for meta in universe]
        for done, future in enumerate(as_completed(futures), 1):
            rows.append(future.result())
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
    st.caption("Khối lượng chỉ là ước tính spot, không tự gửi lệnh.")
    scan_clicked = st.button("QUÉT LẠI", type="primary", width="stretch")

try:
    universe = load_universe()
except Exception as exc:
    st.error(f"Không tải được universe: {exc}")
    st.stop()

if scan_clicked or "signal_scan" not in st.session_state:
    st.session_state.signal_scan = run_scan(universe)
    st.session_state.signal_scan_at = pd.Timestamp.now(tz=VN_TZ)
elif "signal_scan_at" not in st.session_state:
    st.session_state.signal_scan_at = pd.Timestamp.now(tz=VN_TZ)

raw_report = st.session_state.signal_scan.copy()
st.caption(
    f"Lần quét: {st.session_state.signal_scan_at:%d/%m/%Y %H:%M:%S} "
    "(giờ Việt Nam) — cache tối đa 5 phút."
)
status_order = {"READY": 0, "WAIT_PA": 1, "WAIT_PULLBACK": 2, "NO_SETUP": 3, "ERROR": 4}
errors = raw_report[raw_report["status"] == "ERROR"].sort_values("rank")
report = (
    raw_report[raw_report["status"] != "ERROR"]
    .sort_values("rank")
    .head(20)
    .copy()
)
report["rank"] = range(1, len(report) + 1)
report["_order"] = report["status"].map(status_order).fillna(9)
report = report.sort_values(["_order", "rank"]).drop(columns="_order")

ready = report[report["status"] == "READY"]
wait = report[report["status"].isin(["WAIT_PA", "WAIT_PULLBACK"])]
c1, c2, c3, c4 = st.columns(4)
c1.metric("Universe", f"{len(report)} coin")
c2.metric("BUY READY", len(ready))
c3.metric("Đang chờ", len(wait))
c4.metric("Ứng viên bị bỏ", len(errors))
if len(report) < 20:
    st.error(f"Chỉ có {len(report)}/20 coin đủ dữ liệu để quét.")
elif not errors.empty:
    st.caption(
        "Đã thay ứng viên thiếu dữ liệu: "
        + ", ".join(errors["symbol"].head(10))
    )

st.subheader("Tín hiệu có thể hành động")
if ready.empty:
    st.info("Hiện chưa có BUY READY. Không đủ setup thì không giao dịch.")
else:
    for _, row in ready.iterrows():
        risk_per_unit = row["entry"] - row["sl"]
        qty = min(
            capital / row["entry"],
            capital * risk_pct / 100 / risk_per_unit,
        )
        actual_risk = qty * risk_per_unit
        signal_time = pd.Timestamp(row["signal_time"]).tz_convert(VN_TZ)
        st.success(
            f"BUY {row['symbol']} — nến xác nhận {signal_time:%d/%m %H:%M} VN"
        )
        cols = st.columns(7)
        for column, label, value in [
            (cols[0], "Entry", price(row["entry"])),
            (cols[1], "SL", price(row["sl"])),
            (cols[2], f"TP1 50% ({row['tp1_rr']}R)", price(row["tp1"])),
            (cols[3], f"TP2 30% ({row['tp2_rr']}R)", price(row["tp2"])),
            (cols[4], "Trail 20%", price(row["trail_h1"])),
            (cols[5], "Khối lượng ~", f"{qty:.6f}"),
            (cols[6], "Risk thực ~", f"{actual_risk:.2f} USDT"),
        ]:
            column.metric(label, value)
        st.caption(f"PA: {row['pa']}. Runner thoát khi M15 đóng dưới EMA34-low H1.")

st.subheader("Bảng quét TOP20")
view = report.copy()
view["Coin"] = view["name"] + " (" + view["base"] + ")"
view["Vốn hóa"] = view["market_cap_usd"].map(
    lambda value: "-" if pd.isna(value) else f"${value / 1_000_000_000:,.2f}B"
)
view["Tín hiệu"] = view["status"].replace({
    "READY": "🟢 BUY READY",
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
    "rank", "Coin", "Vốn hóa", "symbol", "Tín hiệu",
    "EMA", "Breakout", "Dow", "VZ", "PA", "Thiếu",
]
st.dataframe(
    view[columns],
    hide_index=True,
    width="stretch",
    column_config={"rank": st.column_config.NumberColumn("Top OKX", format="%d")},
)
st.download_button(
    "Tải bảng quét CSV",
    report.drop(columns=[column for column in report if column.startswith("_")])
    .to_csv(index=False),
    "sonic_r_okx_top20_signals.csv",
    "text/csv",
)

with st.expander("Quy tắc cố định của setup"):
    for label in FILTER_LABELS.values():
        st.write(f"- {label}")
    st.write(
        "- TP1: chốt 50% tại Fibo 1.618; TP2: chốt 30% tại 2.618; "
        "20% còn lại trailing EMA34-low H1."
    )
    st.write("- Chỉ BUY sau khi nến M15 xác nhận. Không có READY thì không vào lệnh.")
    st.warning(
        "Universe lấy theo vốn hóa hiện tại nên có survivorship bias. "
        "Ứng dụng là signal/paper-trading, không phải cam kết lợi nhuận."
    )
