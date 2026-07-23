# Sonic R + Dow + PA — Trading System & Backtest

Bộ công cụ kiểm chứng Sonic R (EMA 34/89), Dow HH/HL và Price Action trên crypto.
Elliott/Fibo chỉ còn dùng cho mục tiêu chốt lời extension.

---

## Phương pháp được mã hoá

| Khung | Vai trò | Điều kiện |
|---|---|---|
| **D1** | Nền xu hướng | Giá trên cụm EMA 34–89 |
| **H4** | Sóng chính | EMA34 trên EMA89 + ADX + separation + Dow HH/HL |
| **H1** | Vào lệnh | Hồi về Value Zone + Price Action |

`Config()` mặc định dùng mapping D1/H4/H1. Preset `Config.m15_entry()` giữ
mapping cũ H4/H1/M15 để đối chứng regression. Các cặp base→entry và main→entry
đều shift một nến khung lớn trước khi ghép. Vùng hồi Fibo mặc định không lọc
entry; Fibo extension luôn độc lập với entry và chỉ dùng cho TP.

**Thoát lệnh — 3 chế độ chạy song song để so sánh:**

- `fixed_2r` — TP cố định 2R
- `sr_level` — TP tại kháng cự cũ gần nhất
- `fib_extension` — TP1 Fibo 1.618 (50%), TP2 Fibo 2.618 (30%), runner trailing EMA34 khung main

---

## Cài đặt

```bash
pip install -r requirements.txt
```

## Sử dụng

**1. Kiểm chứng core logic (chạy trước tiên):**
```bash
python tests/test_core.py
```
Phải thấy `TẤT CẢ TEST PASS`, đặc biệt là test look-ahead.

**2. Backtest hàng loạt:**
```bash
python run_backtest.py --days 365
python run_backtest.py --days 1095 --tp fib_extension
python run_backtest.py --symbols BTC/USDT ETH/USDT --tp sr_level
```

**3. Dashboard tương tác:**
```bash
streamlit run dashboard/app.py
```

**4. Chẩn đoán funnel và sensitivity sweep:**
```bash
python -m backtest.diagnostics --synthetic --days 90
python -m backtest.diagnostics --symbol BTC/USDT --days 365
python -m backtest.diagnostics --synthetic --days 90 --baseline-sampling
python -m backtest.sweep --symbol BTC/USDT --days 365
python run_backtest.py --days 365 --ablation
python run_backtest.py --days 1095 --tp-matrix
python run_backtest.py --days 1095 --mfe-report
python run_backtest.py --days 365 --pa-breakdown
```
Sweep luôn bật bộ filter strict và lưu CSV vào `results/`. Cấu hình chỉ được
đánh dấu `recommended` khi có ít nhất 100 lệnh, đạt 0.3–2.0 lệnh/ngày và
không nằm ở rìa lưới, đồng thời có hàng xóm cũng đạt gate.

**5. Pine Script:**
Mở `sonic_r_elliott.pine`, copy vào Pine Editor trên TradingView, Add to Chart.
Bật alert "Sonic R BUY Setup" để nhận thông báo về điện thoại.

---

## Cấu trúc

```
core/
  indicators.py   EMA, ATR, ADX, ZigZag (có độ trễ đúng), Fibonacci, Price Action
  mtf.py          Multi-timeframe alignment — CHỐNG LOOK-AHEAD
  signals.py      3 tầng lọc, mỗi filter bật/tắt độc lập
backtest/
  engine.py       Mô phỏng bar-by-bar, 3 chế độ TP, partial exit, trailing
  metrics.py      Winrate, PF, MFE/MAE, Monte Carlo, khoảng tin cậy
  diagnostics.py  Funnel, marginal contribution, overlap, retrace distribution
  sweep.py        Sensitivity grid, gate đủ mẫu và đánh dấu tham số rìa
data/
  loader.py       ccxt → OKX, cache parquet
dashboard/
  app.py          Streamlit + Plotly
sonic_r_elliott.pine   Indicator TradingView
```

---

## Metrics kiểm chứng từng niềm tin

| Niềm tin trong phương pháp | Metric |
|---|---|
| "Winrate cực cao" | Winrate + khoảng tin cậy Wilson 95% |
| "Sideway cực kì dễ toang" | Winrate tách theo ADX < 25 vs ≥ 25 |
| "Cả ngày chỉ 1–2 entry" | `trades_per_day`, `pct_days_no_trade` |
| "Ăn sóng dài" đáng không? | MFE trung bình, % lệnh chạm 2R/3R/5R |
| "PA đẹp thì vào" | Winrate theo engulfing / pinbar / BOS |
| Filter nào tạo giá trị? | Ablation test — bỏ từng filter, đo chênh lệch |

---

## CẢNH BÁO KỸ THUẬT

**1. Look-ahead bias — đã xử lý, nhưng phải hiểu**

Nến khung lớn chỉ được dùng sau khi đóng. Module `mtf.py` shift 1 nến
trước khi ghép xuống entry. Hàm `verify_no_lookahead()` kiểm tra tự động cho
cả base→entry và main→entry.
Nếu bạn sửa code, chạy lại test này.

ZigZag cũng vậy: pivot tại nến `i` chỉ được xác nhận tại `i + right`.
Cột `confirmed_at` ghi nhận điều này. Đây là lỗi phổ biến nhất khiến
mọi backtest Elliott/ZigZag đẹp giả.

**2. Survivorship bias — chưa xử lý**

Danh sách TOP10 trong `data/loader.py` là top market cap *hôm nay*.
Backtest 3 năm bằng danh sách này = chọn những coin đã sống sót.
Kết quả sẽ tốt hơn thực tế. Muốn nghiêm túc: cần danh sách top 10
theo từng quý trong quá khứ.

**3. Mẫu nhỏ**

Hệ thống này ít lệnh — đó là đặc điểm thiết kế, không phải lỗi.
Nhưng dưới 100 lệnh thì winrate gần như vô nghĩa: khoảng tin cậy quá rộng.
Dashboard cảnh báo khi mẫu chưa đủ. Cách khắc phục: gộp nhiều coin,
kéo dài thời gian, hoặc chấp nhận nới lỏng filter.

**4. Chi phí giao dịch**

Đã trừ taker 0.05% + slippage 0.02% mỗi chiều. Đối chứng H1 bên dưới xác nhận
SL rộng hơn làm chi phí theo R giảm rõ. Engine tự bỏ qua lệnh có SL < 0.1% giá.

**5. Kết quả có thể là "không có edge"**

Đây là kết quả hợp lệ và có giá trị. Công cụ này tồn tại để biết sự thật
trước khi vào tiền thật, không phải để xác nhận niềm tin có sẵn.

---

## Kết luận T16–T18 — H1 entry, 2026-07-23

**Kết quả B: giả thuyết chi phí đúng, nhưng hệ thống vẫn chưa có edge có ý
nghĩa thống kê.** Kết luận áp dụng cho chiến lược BUY hiện tại trên top-10,
dữ liệu OKX ba năm và chi phí mặc định; không phải tuyên bố về mọi chiến lược.

Wilson CI là khoảng tin cậy 95% của **winrate vượt ngưỡng hòa vốn**. Edge chỉ
được chấp nhận khi `expectancy_r > 0`, `n_trades >= 150` và `CI_low > 0`.

| Config | TP | n | WR | Wilson edge CI | Exp R | Max DD | Avg win R | Avg loss R | Cost %R | PF | M15 Exp R | M15 Avg loss R |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Đầy đủ mới | fixed 2R | 236 | 39.41% | [−5.37; +7.00] | +0.015 | 24.51% | +1.452 | −0.919 | −8.1% | 1.021 | −0.042 | −1.066 |
| Đầy đủ mới | SR level | 809 | 88.13% | [−5.46; −1.00] | −0.035 | 29.49% | +0.100 | −1.037 | +3.7% | 0.716 | −0.085 | −1.099 |
| Đầy đủ mới | Fibo extension | 219 | 34.25% | [−5.09; +7.38] | +0.024 | 28.67% | +1.859 | −0.931 | −6.9% | 1.030 | +0.021 | −1.078 |
| Bỏ PA | fixed 2R | 277 | 38.99% | [−5.94; +5.48] | −0.009 | 35.14% | +1.435 | −0.932 | −6.8% | 0.977 | −0.035 | −1.061 |
| Bỏ PA | SR level | 1,256 | 89.41% | [−4.03; −0.63] | −0.025 | 35.03% | +0.095 | −1.038 | +3.8% | 0.772 | −0.071 | −1.091 |
| Bỏ PA | Fibo extension | 257 | 34.24% | [−5.24; +6.29] | +0.008 | 30.48% | +1.850 | −0.951 | −4.9% | 1.004 | −0.011 | −1.080 |
| Thêm Fibo | fixed 2R | 195 | 38.46% | [−7.24; +6.29] | −0.017 | 22.34% | +1.457 | −0.938 | −6.2% | 0.960 | −0.029 | −1.064 |
| Thêm Fibo | SR level | 582 | 87.97% | [−6.34; −1.05] | −0.039 | 23.92% | +0.098 | −1.045 | +4.5% | 0.685 | −0.076 | −1.097 |
| Thêm Fibo | Fibo extension | 182 | 31.32% | [−11.05; +2.30] | −0.126 | 33.26% | +1.687 | −0.952 | −4.8% | 0.801 | +0.024 | −1.076 |

- `CI_low > 0`: **0/9**. Ba ô expectancy dương đều còn chứa 0 trong CI, nên
  chưa thể tách edge khỏi nhiễu.
- `avg_loss_r` H1 nằm trong `[−1.045; −0.919]`, cải thiện rõ so với M15
  `[−1.099; −1.061]`. Riêng full/SR đạt `−1.037R`, đúng vùng dự đoán
  `−1.02R` đến `−1.04R`.
- `cost_pct_of_r` âm ở một số ô không có nghĩa là phí âm: timeout có thể đóng
  lỗ trước SL. Ở full/fixed, 120 lệnh SL trung bình `−1.044R`, còn 23 timeout
  trung bình `−0.267R`; chỉ số tổng hợp vì vậy là `−0.919R`.
- T18 đạt ngay cấu hình định trước: full/fixed có 236 trade, nên không nới
  `adx_min=18` hay `separation_min=0.35`.
- MFE/MAE H1 full/fixed: winner MFE trung bình `1.85R`; tỷ lệ chạm
  2R/3R/5R là `25.0%/0.4%/0.0%`; MAE winner `−0.40R`. TP 2R là vừa và dữ
  liệu không ủng hộ chỉnh `sl_buffer_atr` hoặc `tp_r_multiple`, nên không dùng
  vòng tinh chỉnh được phép chỉ để tìm số đẹp.
- Regression M15 giữ nguyên 30 tín hiệu và 4 trade trên fixture; D1→H1 và
  H4→H1 đều ghi nhận 0 vi phạm look-ahead.

**Quyết định:** không giao dịch hệ thống này bằng tiền thật ở trạng thái hiện
tại và dừng tối ưu cùng bộ tín hiệu. Bước nghiên cứu hợp lệ tiếp theo phải là
một giả thuyết regime được xác định định lượng trước, không phải sweep thêm.

---

## Bước tiếp theo

- [ ] Regime analysis, chỉ chạy sau khi ghi trước giả thuyết và ngưỡng định lượng
- [ ] Đối chiếu tín hiệu Pine Script vs Python
- [ ] Thêm SELL setup (hiện chỉ có BUY)
- [ ] Chỉ paper trade sau khi một cấu hình vượt đủ gate edge
