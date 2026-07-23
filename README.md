# Sonic R + Dow + PA — Trading System & Backtest

Bộ công cụ kiểm chứng Sonic R (EMA 34/89), Dow HH/HL và Price Action trên crypto.
Elliott/Fibo chỉ còn dùng cho mục tiêu chốt lời extension.

---

## Phương pháp được mã hoá

| Khung | Vai trò | Điều kiện |
|---|---|---|
| **H4** | Nền xu hướng | Giá trên cụm EMA 34–89; D1 chỉ để tham khảo/ablation |
| **H1** | Sóng chính | EMA34 trên EMA89 + ADX + separation + Dow HH/HL |
| **M15** | Vào lệnh | Hồi về Value Zone + Price Action |

`Config()` và dashboard mặc định bật H4, H1 cross/ADX/separation, Dow,
Value Zone và PA. D1 và vùng hồi Fibo vẫn được tính để chẩn đoán nhưng mặc
định không lọc entry. Fibo extension luôn độc lập với entry và chỉ dùng cho TP.
Preset `Config.baseline_sampling()` chỉ dùng để lấy mẫu khi debug.

**Thoát lệnh — 3 chế độ chạy song song để so sánh:**

- `fixed_2r` — TP cố định 2R
- `sr_level` — TP tại kháng cự cũ gần nhất
- `fib_extension` — TP1 Fibo 1.618 (50%), TP2 Fibo 2.618 (30%), runner trailing EMA34 H1

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
python run_backtest.py --days 365 --tp-matrix
python run_backtest.py --days 365 --mfe-report
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

Nến H1 mở lúc 10:00 chỉ được dùng từ 11:00. Module `mtf.py` shift 1 nến
trước khi ghép xuống M15. Hàm `verify_no_lookahead()` kiểm tra tự động.
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

Đã trừ taker 0.05% + slippage 0.02% mỗi chiều. Trên M15 với SL sát,
chi phí có thể ăn phần lớn edge. Engine tự bỏ qua lệnh có SL < 0.1% giá.

**5. Kết quả có thể là "không có edge"**

Đây là kết quả hợp lệ và có giá trị. Công cụ này tồn tại để biết sự thật
trước khi vào tiền thật, không phải để xác nhận niềm tin có sẵn.

---

## Kết luận edge — 2026-07-23

**Không tìm thấy edge có ý nghĩa thống kê trong 9 cấu hình đã định trước.**
Kết luận áp dụng cho chiến lược BUY hiện tại trên top-10 universe, dữ liệu OKX
M15 và chi phí mặc định; không phải tuyên bố về mọi chiến lược có thể tồn tại.

Wilson CI dưới đây là khoảng tin cậy 95% của **winrate vượt ngưỡng hòa vốn**
(Wilson winrate trừ breakeven theo `avg_win_r`/`avg_loss_r`). Edge chỉ được
chấp nhận khi `expectancy_r > 0`, có ít nhất 150 trade và `CI_low > 0`.

| Config | TP | Trades 3 năm | Expectancy | Wilson edge CI |
|---|---|---:|---:|---:|
| Đầy đủ mới | fixed 2R | 998 | −0.042R | [−4.39; +1.56] |
| Đầy đủ mới | SR level | 2,624 | −0.085R | [−8.24; −5.17] |
| Đầy đủ mới | Fibo extension | 771 | +0.021R | [−2.55; +3.86] |
| Bỏ PA | fixed 2R | 1,099 | −0.035R | [−4.03; +1.66] |
| Bỏ PA | SR level | 3,630 | −0.071R | [−6.95; −4.40] |
| Bỏ PA | Fibo extension | 832 | −0.011R | [−3.29; +2.89] |
| Thêm Fibo entry | fixed 2R | 816 | −0.029R | [−4.25; +2.33] |
| Thêm Fibo entry | SR level | 1,887 | −0.076R | [−7.88; −4.32] |
| Thêm Fibo entry | Fibo extension | 631 | +0.024R | [−2.76; +4.24] |

Kiểm định 365 ngày cũng chỉ có một ô dương cô lập: đầy đủ mới × Fibo
extension đạt `+0.018R` với 167 trade nhưng CI `[−5.94; +7.82]` chứa 0; hai ô
lân cận cùng TP đều âm. Kéo dài lên 3 năm không làm CI loại được 0.
Hai ứng viên Fibo dương trên mẫu gộp cũng không ổn định theo thời gian: các
năm đầy đủ 2024/2025 lần lượt là `−0.013R/−0.089R` (đầy đủ mới) và
`−0.047R/−0.005R` (thêm Fibo entry); không năm nào có `CI_low > 0`.

- MFE/MAE 3 năm: winner đạt MFE trung bình 2.18R, chỉ 1.5% trade đạt 3R,
  MAE winner −0.44R. TP 2R là vừa và SL không quá sát.
- PA 3 năm: BOS tệ nhất (−0.129R), nhưng bỏ BOS vẫn −0.049R; chỉ engulfing
  −0.093R; không PA −0.035R. Không có một pattern đơn lẻ che giấu edge.
- Test multi-timeframe ghi nhận 0 vi phạm look-ahead.

**Quyết định:** không giao dịch hệ thống này bằng tiền thật ở trạng thái hiện
tại. Chỉ mở lại đánh giá khi có giả thuyết chiến lược mới được xác định trước,
không tiếp tục chỉnh tham số trên cùng mẫu dữ liệu.

---

## Bước tiếp theo

- [ ] Walk-forward: train 6 tháng → test 2 tháng, lăn qua 3 năm
- [ ] Elliott Tầng 2: wave counting đầy đủ (cẩn thận vấn đề redraw)
- [ ] Đối chiếu tín hiệu Pine Script vs Python
- [ ] Thêm SELL setup (hiện chỉ có BUY)
- [ ] Paper trading trước khi vào tiền thật
