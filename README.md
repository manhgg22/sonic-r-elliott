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

## Night Watch — scanner + paper trading toàn bộ OKX

Monitor quét toàn bộ perpetual USDT crypto active trên OKX sau mỗi lần nến
M15 đóng. Sản phẩm stock/commodity tokenized bị loại bằng `instCategory`, nên
universe chỉ gồm coin có thể LONG và SHORT. Monitor chạy độc lập với trình
duyệt và ghi scan, vị thế paper cùng mọi sự kiện vào SQLite.

```bash
python paper_monitor.py
uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
cd frontend
npm install
npm run dev
```

Realtime market data is delivered through one shared backend connection:

- OKX public WebSocket: tick prices for up to 50 configured instruments.
- OKX business WebSocket: real M15 candle updates, including the live,
  unconfirmed candle.
- Sonic WebSocket endpoint: `ws://localhost:8000/api/v1/market/stream`.
- Live WebSocket console: `http://localhost:8000/api/v1/market/console`.
- Payload reference: [`docs/REALTIME_API.md`](docs/REALTIME_API.md).
- Strategy decisions still use closed candles only; the live candle is for
  monitoring and chart display.

Optional environment variables:

```bash
OKX_WS_URL=wss://ws.okx.com:8443/ws/v5/public
OKX_CANDLE_WS_URL=wss://ws.okx.com:8443/ws/v5/business
SONIC_REALTIME_MAX_INSTRUMENTS=50
SONIC_REALTIME_STALE_SECONDS=10
```

Khi phát triển, mở React tại `http://localhost:5173`. Khi chạy Docker Compose,
mở production frontend tại `http://localhost:8501`. API và tài liệu OpenAPI
chạy tại `http://localhost:8000/docs`. Muốn thử đúng một lượt rồi thoát:

```bash
python paper_monitor.py --once
```

- LONG: EMA34 > EMA89, breakout, Dow HH/HL, hồi Value Zone, bullish PA.
- SHORT: EMA34 < EMA89, breakdown, Dow LL/LH, hồi Value Zone, bearish PA.

Paper engine mở tại giá đóng nến xác nhận, TP1 chốt 50%, TP2 chốt 30% và giữ
20% runner theo EMA34 H1. Dashboard có funnel 5 gate, snapshot scanner, vị thế,
MFE/MAE, lịch sử sự kiện và equity mô hình. Nếu SL/TP cùng chạm trong một nến,
engine ưu tiên SL. Đây là OHLCV paper model, chưa tính funding/slippage/fill.
Ứng dụng không giữ API key và **không gửi lệnh thật**.

Đóng gói Docker:

```bash
docker compose up --build -d
docker compose logs -f frontend
docker compose logs -f backend
docker compose logs -f paper-monitor
```

Cache thị trường được giữ tại `data/cache/`, SQLite và log tại `results/`.
Không mở cổng 8501 ra Internet công khai nếu chưa đặt ứng dụng sau lớp
xác thực/reverse proxy.

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

**3. Analytical Terminal realtime (React + TypeScript + Ant Design):**
```bash
uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
cd frontend
npm install
npm run dev
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
python run_backtest.py --days 1095 --regime-report
python run_backtest.py --pure-sonic --exchange binance --top 50 --days 1095
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
  pure_sonic.py   Bản thuần: trend, breakout, Value Zone, PA
  signal_scanner.py Scanner OKX dùng chung cho monitor và dashboard
  trade_setup.py  Setup triển khai: Pure Sonic + Dow, chỉ dùng nến đã đóng
  signals.py      3 tầng lọc, mỗi filter bật/tắt độc lập
backtest/
  engine.py       Mô phỏng bar-by-bar, 3 chế độ TP, partial exit, trailing
  metrics.py      Winrate, PF, MFE/MAE, Monte Carlo, khoảng tin cậy
  diagnostics.py  Funnel, marginal contribution, overlap, retrace distribution
  regime.py       BTC MA200/quarterly/ADX regime, gắn theo entry không look-ahead
  sweep.py        Sensitivity grid, gate đủ mẫu và đánh dấu tham số rìa
data/
  loader.py       CoinGecko market cap + ccxt Binance/OKX, cache parquet
backend/
  app/
    api/                 FastAPI routers + dependencies
    core/                Cấu hình môi trường
    repositories/        Truy cập SQLite
    schemas/             Hợp đồng Pydantic
    services/            Nghiệp vụ dashboard + OKX
frontend/
  src/                   React + TypeScript + Ant Design Terminal B1-B5
  package.json           Vite toolchain và frontend dependencies
  nginx.conf             Production proxy REST + WebSocket
  Dockerfile             Node build stage + Nginx runtime
paper_monitor.py  Scheduler M15 + SQLite paper engine, không gửi lệnh thật
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
| Edge chỉ có trong regime? | BTC MA200, return 90 ngày và ADX D1 |

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

**Quyết định T16–T18:** không giao dịch hệ thống này bằng tiền thật và không
sweep thêm. Regime analysis dưới đây là kiểm tra cuối cùng đã định trước.

---

## Kết luận T19–T20 — Regime analysis, 2026-07-23

**Kết quả B: không có regime nào đạt tiêu chuẩn edge.** Báo cáo dùng top-10,
ba năm, cấu hình D1/H4/H1 mặc định và cả ba chế độ TP. Ba định nghĩa tạo 21
nhóm kết quả (9 cặp định nghĩa × TP); `EDGE` chỉ đúng khi `n >= 100`,
`expectancy_r > 0` và `wilson_ci_low > 0`.

| Định nghĩa | Regime | TP | n | WR | Wilson edge CI | Exp R | PF | Max DD | EDGE |
|---|---|---|---:|---:|---:|---:|---:|---:|---|
| BTC MA200 | Bull | 2R | 235 | 39.57% | [−5.37; +7.04] | +0.016 | 1.022 | 24.45% | Không |
| BTC MA200 | Bear | 2R | 1 | 0.00% | N/A | −0.076 | 0.000 | 0.07% | Thiếu mẫu |
| BTC MA200 | Bull | SR | 808 | 88.12% | [−5.47; −1.01] | −0.035 | 0.715 | 29.59% | Không |
| BTC MA200 | Bear | SR | 1 | 100.00% | N/A | +0.108 | ∞ | 0.00% | Thiếu mẫu |
| BTC MA200 | Bull | Fibo | 218 | 34.40% | [−5.09; +7.42] | +0.025 | 1.031 | 28.62% | Không |
| BTC MA200 | Bear | Fibo | 1 | 0.00% | N/A | −0.076 | 0.000 | 0.07% | Thiếu mẫu |
| BTC quarterly | Bull | 2R | 163 | 41.72% | [−5.07; +9.90] | +0.051 | 1.090 | 16.53% | Không |
| BTC quarterly | Bear | 2R | 0 | N/A | N/A | N/A | N/A | N/A | Thiếu mẫu |
| BTC quarterly | Sideway | 2R | 73 | 34.25% | [−12.30; +8.98] | −0.064 | 0.893 | 12.96% | Không |
| BTC quarterly | Bull | SR | 604 | 89.74% | [−4.69; +0.16] | −0.023 | 0.784 | 15.11% | Không |
| BTC quarterly | Bear | SR | 0 | N/A | N/A | N/A | N/A | N/A | Thiếu mẫu |
| BTC quarterly | Sideway | SR | 205 | 83.41% | [−11.67; −1.51] | −0.070 | 0.592 | 14.96% | Không |
| BTC quarterly | Bull | Fibo | 155 | 39.35% | [−0.44; +14.76] | +0.194 | 1.332 | 15.21% | Không |
| BTC quarterly | Bear | Fibo | 0 | N/A | N/A | N/A | N/A | N/A | Thiếu mẫu |
| BTC quarterly | Sideway | Fibo | 64 | 21.88% | [−23.05; −3.12] | −0.387 | 0.489 | 26.94% | Không |
| ADX D1 | Trending | 2R | 122 | 45.90% | [−3.19; +14.22] | +0.116 | 1.253 | 9.98% | Không |
| ADX D1 | Ranging | 2R | 114 | 32.46% | [−11.36; +5.58] | −0.092 | 0.841 | 26.11% | Không |
| ADX D1 | Trending | SR | 483 | 90.68% | [−4.75; +0.45] | −0.020 | 0.787 | 11.63% | Không |
| ADX D1 | Ranging | SR | 326 | 84.36% | [−9.13; −1.24] | −0.056 | 0.653 | 20.95% | Không |
| ADX D1 | Trending | Fibo | 118 | 42.37% | [−0.43; +17.12] | +0.209 | 1.397 | 14.26% | Không |
| ADX D1 | Ranging | Fibo | 101 | 24.75% | [−13.42; +3.21] | −0.191 | 0.735 | 24.38% | Không |

- Hai ứng viên mạnh nhất vẫn chứa 0: quarterly bull × Fibo `+0.194R`,
  CI low `−0.44`; ADX trending × Fibo `+0.209R`, CI low `−0.43`.
- MA200 bear chỉ có 1 trade và quarterly bear không có trade trong cửa sổ này.
  Các nhóm đó không đủ mẫu để kết luận riêng; chúng không được coi là edge.
- Cả ba regime dùng BTC D1 có thêm 250 ngày warmup và shift một nến trước khi
  gắn tại `entry_time`. Mỗi verifier kiểm tra 673 timestamp: **0 vi phạm**;
  không trade nào nhận regime `NaN`.
- T21 không chạy vì T20 không tìm thấy hàng nào qua gate. Việc tách năm/coin
  hoặc dịch ngưỡng lúc này chỉ là khai thác thêm cùng dữ liệu, trái stopping rule.

**Quyết định cuối giai đoạn backtest:** chưa có bằng chứng thống kê để giao
dịch hệ thống bằng tiền thật. Dừng tinh chỉnh trên tập dữ liệu này.

---

## Sonic R thuần — Binance TOP50, không phí, 2026-07-23

Giả thuyết kiểm tra: bảy filter cũ làm entry quá muộn. Bản thuần chỉ dùng đúng
bốn điều kiện: trend EMA34/89, breakout 20 nến còn hiệu lực 30 nến, Value Zone
và engulfing/pinbar. Dữ liệu là top 50 cặp USDT theo volume Binance tại thời
điểm chạy, tối đa 1.095 ngày; stablecoin và leveraged token đã bị loại.

Theo yêu cầu, **toàn bộ bảng này không tính fee hoặc slippage**. Max DD dùng
vốn gộp 500.000 USD (10.000 USD cấp độc lập cho mỗi coin), không phải chia PnL
của 50 coin cho một tài khoản 10.000 USD.

### Ba chế độ TP

| TP | Trades | WR | Wilson edge CI | Exp R | PF | Max DD | Avg win/loss R | Trades/ngày | MFE winner | Chạm 2R / 3R | Stat edge |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| Fixed 2R | 10.010 | 33.27% | [−1.54; +0.31] | −0.018 | 0.978 | 9.41% | +1.932 / −0.990 | 9.142 | 2.28R | 31.5% / 1.7% | Không |
| SR level | 25.228 | 76.67% | [−1.05; 0.00] | −0.007 | 0.975 | 5.03% | +0.295 / −0.999 | 23.039 | 0.44R | 0.9% / 0.2% | Không |
| Fibo extension | 7.582 | 20.84% | [+0.21; +2.04] | +0.056 | 1.101 | 6.36% | +4.043 / −0.994 | 6.924 | 8.38R | 31.9% / 23.2% | **Có** |

### Ablation trên Fibo extension

| Cấu hình | Trades | Exp R | Wilson edge CI | PF | Max DD | MFE winner | Chạm 3R | Stat edge |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| Đầy đủ 4 bước | 7.582 | +0.056 | [+0.21; +2.04] | 1.101 | 6.36% | 8.38R | 23.2% | Có |
| Bỏ breakout | 8.848 | +0.064 | [+0.41; +2.09] | 1.113 | 6.25% | 8.75R | 23.6% | Có |
| Bỏ Price Action | 9.233 | +0.067 | [+0.49; +2.14] | 1.099 | 7.84% | 8.57R | 23.1% | Có |
| Chỉ trend + Value Zone | 10.465 | +0.064 | [+0.48; +2.03] | 1.089 | 8.82% | 8.63R | 23.5% | Có |

### Đối chứng entry với cùng fixed 2R

| Hệ thống | Trades | Exp R | MFE winner | Chạm 3R | Max DD |
|---|---:|---:|---:|---:|---:|
| Sonic R thuần | 10.010 | −0.018 | 2.28R | 1.7% | 9.41% |
| Hệ thống 7-filter | 2.936 | +0.035 | 2.21R | 1.5% | 2.49% |

**Kết luận:**

- Bản thuần **không tốt hơn** 7-filter khi dùng cùng fixed 2R: expectancy thấp
  hơn và MFE winner chỉ tăng 0.07R, không phải cải thiện rõ rệt.
- Fibo extension là chế độ duy nhất đạt `stat_edge`. Vì fixed 2R và SR đều âm,
  phát hiện này gắn với cách thoát Fibo, không chứng minh bốn filter entry tạo edge.
- Breakout và Price Action không đóng góp dương: bỏ từng bước hoặc bỏ cả hai
  đều làm expectancy tăng. Thành phần có giá trị trong mẫu này là trend +
  Value Zone kết hợp Fibo exit.
- Không tham số nào được sweep hoặc chỉnh sau khi thấy kết quả.
- Universe có 3.394.156 nến M15; 25/50 coin đủ ít nhất 90% cửa sổ ba năm,
  coin còn lại dùng lịch sử thật từ ngày niêm yết. Việc chọn top volume hôm nay
  tạo survivorship/listing bias, và kết quả không phí không đại diện PnL thực tế.
- Test Pure Sonic kiểm tra main→entry `0/508` vi phạm look-ahead và xác nhận
  chỉ tồn tại bốn cột `f_trend`, `f_breakout`, `f_value_zone`, `f_pa`.

Snapshot universe: `AAVE`, `ADA`, `AERO`, `AVAX`, `BANK`, `BNB`, `BTC`, `DEXE`,
`DOGE`, `ENA`, `ERA`, `ETH`, `GRAM`, `HBAR`, `KAITO`, `KITE`, `LINK`, `LISTA`,
`LTC`, `MIRA`, `MUB`, `NEAR`, `ONDO`, `OPN`, `PAXG`, `PEPE`, `PUMP`, `RE`,
`RIF`, `SNDKB`, `SOL`, `SPCXB`, `SUI`, `SYN`, `TAO`, `TON`, `TRUMP`, `TRX`,
`U`, `UNI`, `UTK`, `VANA`, `WLD`, `WLFI`, `XAUT`, `XLM`, `XRP`, `ZAMA`,
`ZEC`, `币安人生` — tất cả ghép `/USDT`.

---

## Bước tiếp theo

- [ ] Đối chiếu tín hiệu Pine Script vs Python
- [x] Thêm SELL setup và scanner toàn bộ OKX
- [x] Bắt đầu paper trading không dùng tiền thật, ghi SQLite qua đêm
- [ ] Thu thập paper log 2–3 tháng và đối chiếu với backtest cùng kỳ
