"""
Dashboard Streamlit — Sonic R + Dow + PA Backtest

Chạy:  streamlit run dashboard/app.py

Điểm mạnh: bật/tắt từng filter để xem filter nào THỰC SỰ tạo giá trị,
thay vì tin vào cảm giác.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from core.signals import Config, build_signals
from core.mtf import align_htf_to_ltf, map_timeframes
from core import indicators as ind
from backtest.engine import run_backtest
from backtest.diagnostics import ablation_variants
from backtest import metrics as mt
from data.loader import fetch_ohlcv, TOP10


st.set_page_config(page_title="Sonic R + Dow + PA", layout="wide")
st.title("Sonic R + Dow + PA — Backtest Dashboard")


# ------------------------------------------------------------------ SIDEBAR
with st.sidebar:
    st.header("Cấu hình")

    symbol = st.selectbox("Coin", TOP10, index=0)
    days = st.slider("Số ngày lịch sử", 90, 1095, 365, step=30)

    st.subheader("Tầng 1 — Nền")
    use_base = st.checkbox("D1 trên 34-89", True)

    st.subheader("Tầng 2 — Sóng chính H4")
    use_cross = st.checkbox("EMA34 cắt lên EMA89", True)
    cross_mode = st.selectbox("Chế độ EMA cross", ["state", "event"])
    cross_bars = st.slider("Cú cắt hiệu lực (nến)", 10, 300, 50)
    use_adx = st.checkbox("ADX filter", True)
    adx_min = st.slider("ADX tối thiểu", 10.0, 35.0, 18.0)
    use_sep = st.checkbox("EMA separation", True)
    sep_min = st.slider("Separation / ATR", 0.0, 2.0, 0.35)
    use_dow = st.checkbox("Dow HH+HL", True)

    st.subheader("Elliott / Fibo")
    use_fib = st.checkbox("Lọc vùng hồi Fibo", False)
    fib_lo, fib_hi = st.slider("Vùng Fibo", 0.0, 1.0, (0.30, 0.75))
    swing_max_age = st.slider("Tuổi swing tối đa (H4)", 50, 500, 100, step=50)

    st.subheader("Price Action")
    require_pa = st.checkbox("Bắt buộc có PA", True)

    st.subheader("Risk / TP")
    tp_mode = st.selectbox("Chế độ TP",
                           ["fixed_2r", "sr_level", "fib_extension"])
    risk_pct = st.slider("Risk mỗi lệnh (%)", 0.25, 3.0, 1.0, step=0.25)

    run = st.button("CHẠY BACKTEST", type="primary", use_container_width=True)


@st.cache_data(ttl=3600)
def load_data(sym, n_days):
    m15 = fetch_ohlcv(sym, "15m", n_days, verbose=False)
    return None if m15.empty else m15


def build_cfg():
    return Config(
        cross_mode=cross_mode,
        cross_valid_bars=cross_bars,
        adx_min=adx_min,
        separation_min=sep_min,
        fib_lo=fib_lo,
        fib_hi=fib_hi,
        swing_max_age=swing_max_age,
        require_pa=require_pa,
        risk_pct=risk_pct,
        tp_mode=tp_mode,
        use_d1_filter=False,
        use_h4_filter=use_base,
        use_cross_filter=use_cross,
        use_adx_filter=use_adx,
        use_separation_filter=use_sep,
        use_dow_filter=use_dow,
        use_fib_filter=use_fib,
    )


if run:
    with st.spinner("Đang tải dữ liệu..."):
        data = load_data(symbol, days)

    if data is None:
        st.error("Không tải được dữ liệu. Kiểm tra kết nối mạng / OKX API.")
        st.stop()

    m15 = data
    cfg = build_cfg()
    entry, main, base = map_timeframes(
        m15, cfg.tf_entry, cfg.tf_main, cfg.tf_base
    )
    st.caption(
        f"{len(entry)} nến {cfg.tf_entry} | "
        f"{entry.index[0].date()} → {entry.index[-1].date()} | "
        f"mapping {cfg.tf_base}/{cfg.tf_main}/{cfg.tf_entry}"
    )
    sig = build_signals(entry, main, base, cfg)

    main_bands = ind.sonic_r_bands(main)
    trail = align_htf_to_ltf(
        main_bands[["ema_fast_low"]], entry.index
    )["ema_fast_low"]

    trades = run_backtest(
        sig,
        entry,
        symbol=symbol,
        tp_mode=tp_mode,
        risk_pct=risk_pct,
        max_bars=cfg.max_bars,
        trail_ema=trail,
    )

    if trades.empty:
        st.warning("Không có lệnh nào. Thử nới lỏng filter.")
        st.stop()

    rep = mt.full_report(trades, entry.index)
    b, f = rep["basic"], rep["frequency"]

    # ---------------- KPI
    c = st.columns(6)
    c[0].metric("Số lệnh", b["n_trades"])
    c[1].metric("Winrate", f"{b['winrate']}%")
    c[2].metric("Profit Factor", b["profit_factor"])
    c[3].metric("Expectancy", f"{b['expectancy_r']}R")
    c[4].metric("Max DD", f"{b['max_drawdown_pct']}%")
    c[5].metric("Lệnh/ngày", f["trades_per_day"])

    # ---------------- Equity
    st.subheader("Equity Curve")
    eq = 10000 + trades["pnl"].cumsum()
    dd = (eq - eq.cummax()) / eq.cummax() * 100

    fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                        row_heights=[0.7, 0.3], vertical_spacing=0.05)
    fig.add_trace(go.Scatter(x=trades["exit_time"], y=eq, name="Equity",
                             line=dict(color="#00cc96")), row=1, col=1)
    fig.add_trace(go.Scatter(x=trades["exit_time"], y=dd, name="Drawdown",
                             fill="tozeroy", line=dict(color="#ef553b")),
                  row=2, col=1)
    fig.update_layout(height=450, showlegend=False, template="plotly_dark")
    st.plotly_chart(fig, use_container_width=True)

    # ---------------- Tabs
    t1, t2, t3, t4, t5 = st.tabs(
        ["Chẩn đoán", "Ablation", "Trade Log", "Monte Carlo", "Chart"]
    )

    with t1:
        col1, col2 = st.columns(2)

        with col1:
            st.markdown("**Tần suất — kiểm chứng 'ít lệnh'**")
            st.json(f)
            st.markdown("**Độ tin cậy winrate**")
            ci = rep["winrate_ci"]
            st.write(f"Winrate: {ci['winrate_point']}% "
                     f"(khoảng 95%: {ci['winrate_ci_low']}–{ci['winrate_ci_high']}%)")
            if not ci["reliable"]:
                st.warning(f"Chỉ {ci['sample_size']} lệnh — chưa đủ tin cậy. "
                           "Cần tối thiểu 100 lệnh.")

        with col2:
            st.markdown("**Sideway vs Trending**")
            sw = rep["sideway_vs_trend"]
            if sw:
                st.write(f"ADX < 25: {sw['sideway_n']} lệnh, "
                         f"WR {sw['sideway_winrate']}%, exp {sw['sideway_expectancy']}R")
                st.write(f"ADX ≥ 25: {sw['trending_n']} lệnh, "
                         f"WR {sw['trending_winrate']}%, exp {sw['trending_expectancy']}R")

            st.markdown("**MFE/MAE — gồng dài có đáng?**")
            st.json(rep["mfe_mae"])

        st.markdown("**Pattern nào work?**")
        pa_df = mt.pa_breakdown(trades)
        if not pa_df.empty:
            st.dataframe(pa_df, use_container_width=True)

    with t2:
        st.markdown("### Ablation Test — filter nào thực sự tạo giá trị?")
        st.caption("Bỏ từng filter, xem kết quả thay đổi thế nào.")

        if st.button("Chạy Ablation"):
            rows = []
            variants = ablation_variants(build_cfg())

            prog = st.progress(0)
            for i, (label, cfg_i) in enumerate(variants):
                sig_i = build_signals(entry, main, base, cfg_i)
                tr_i = run_backtest(
                    sig_i,
                    entry,
                    symbol=symbol,
                    tp_mode=tp_mode,
                    risk_pct=risk_pct,
                    max_bars=cfg_i.max_bars,
                    trail_ema=trail,
                )
                if tr_i.empty:
                    rows.append({"config": label, "n_trades": 0})
                else:
                    m_i = mt.basic_metrics(tr_i)
                    rows.append({
                        "config": label,
                        "n_trades": m_i["n_trades"],
                        "winrate": m_i["winrate"],
                        "expectancy_r": m_i["expectancy_r"],
                        "max_dd": m_i["max_drawdown_pct"],
                    })
                prog.progress((i + 1) / len(variants))

            st.dataframe(pd.DataFrame(rows), use_container_width=True)

    with t3:
        st.dataframe(trades, use_container_width=True)
        st.download_button("Tải CSV", trades.to_csv(index=False),
                           f"trades_{symbol.replace('/','_')}.csv")

    with t4:
        mc = rep["monte_carlo"]
        if mc:
            st.json(mc)
            st.caption("Xáo thứ tự lệnh 1000 lần — drawdown tệ nhất có thể gặp.")

    with t5:
        n = st.slider("Số nến hiển thị", 200, 3000, 800)
        view = entry.iloc[-n:]
        sig_v = sig.iloc[-n:]

        fig2 = go.Figure()
        fig2.add_trace(go.Candlestick(
            x=view.index, open=view["open"], high=view["high"],
            low=view["low"], close=view["close"], name="Price"))
        fig2.add_trace(go.Scatter(x=sig_v.index, y=sig_v["vz_top"],
                                  name="VZ Top", line=dict(color="cyan", width=1)))
        fig2.add_trace(go.Scatter(x=sig_v.index, y=sig_v["vz_bot"],
                                  name="VZ Bot", line=dict(color="orange", width=2),
                                  fill="tonexty", fillcolor="rgba(0,150,255,0.1)"))

        entries = trades[trades["entry_time"] >= view.index[0]]
        if not entries.empty:
            fig2.add_trace(go.Scatter(
                x=entries["entry_time"], y=entries["entry_price"],
                mode="markers", name="Entry",
                marker=dict(symbol="triangle-up", size=12, color="lime")))

        fig2.update_layout(height=600, template="plotly_dark",
                           xaxis_rangeslider_visible=False)
        st.plotly_chart(fig2, use_container_width=True)

else:
    st.info("Chọn cấu hình bên trái và bấm CHẠY BACKTEST.")
    st.markdown("""
    ### Hệ thống này kiểm chứng điều gì?

    | Niềm tin | Metric kiểm chứng |
    |---|---|
    | "Winrate cực cao" | Winrate + khoảng tin cậy 95% |
    | "Sideway cực kì dễ toang" | Winrate tách theo ADX |
    | "Cả ngày chỉ 1-2 entry" | Số lệnh/ngày thực tế |
    | "Ăn sóng dài" | So sánh 2R vs Fibo extension |
    | "PA đẹp thì vào" | Winrate theo từng loại pattern |
    | Filter nào đáng giá? | Ablation test |
    """)
