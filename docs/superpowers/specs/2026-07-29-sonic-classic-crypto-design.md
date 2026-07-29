# Sonic Classic (crypto) — Thiết kế

Ngày: 2026-07-29
Trạng thái: chờ duyệt
Người viết: Claude, theo brainstorming với chủ project

Tài liệu tham chiếu:
- [`research/sonic-usage-and-variants.md`](../../../research/sonic-usage-and-variants.md) — quy tắc gốc đã đối chiếu nguồn
- [`research/sonic-implementation-audit.md`](../../../research/sonic-implementation-audit.md) — quyết định triển khai lần trước
- [`README.md`](../../../README.md) — kết quả backtest T16–T20 và stopping rule

---

## 1. Bối cảnh

Project hiện có một chiến lược Sonic R (`core/pure_sonic.py` + `core/trade_setup.py`) đã
được backtest kỹ. Kết luận T16–T20: **không có edge đạt ý nghĩa thống kê**, và đã chốt
stopping rule "dừng tinh chỉnh trên tập dữ liệu này".

Sau đó, việc đọc lại tài liệu gốc (Post #1 ForexFactory #114792, các post được nó dẫn,
5 PDF đính kèm và **source code `.mq4` của TAH**) cho thấy code hiện tại lệch khỏi nguồn
ở một số điểm có ý nghĩa — đáng chú ý nhất là **thiếu hoàn toàn quy tắc loại setup khi SL
quá rộng**, và **WAVE bị thay bằng Dow HH/HL trên khung khác**.

Tài liệu này đặc tả một **biến thể song song**, bám sát nguồn hơn và thích nghi cho crypto
perpetual. Nó **không thay thế** chiến lược hiện tại.

### 1.1. Vì sao việc này không vi phạm stopping rule

Stopping rule cấm **tinh chỉnh tham số trên cùng tập dữ liệu** để tìm số đẹp. Việc ở đây khác:
sửa cho khớp một đặc tả **bên ngoài** (tài liệu gốc), quyết định trước khi nhìn kết quả.

Nhưng nó tạo ra một chiến lược khác. Do đó **mọi baseline T16–T20 không áp dụng cho bản này**,
và bản này phải qua đúng cổng kiểm chứng đã định (mục 9) — chạy một lần, không sweep.

---

## 2. Mục tiêu và phi mục tiêu

**Mục tiêu**

1. Cài đặt Classic setup đúng theo spec-of-record (mục 3), chạy được cho cả LONG và SHORT.
2. Thích nghi cho crypto perpetual: 24/7, đơn vị biến động đa tài sản, phí funding.
3. Bổ sung quy tắc **loại setup** khi SL vượt trần — quy tắc của nguồn mà code hiện chưa có.
4. Ghi lại quan sát PVSRA trên mỗi tín hiệu để phân tích sau, **không** dùng chặn lệnh.
5. Giữ nguyên vẹn chiến lược hiện tại làm đối chứng.

**Phi mục tiêu (không làm trong vòng này)**

| Hạng mục | Vì sao loại |
|---|---|
| Scout trade | Phụ thuộc discretion và PVSRA; nguồn xếp là rủi ro cao hơn Classic |
| Nhồi lệnh / scale-in | Nguồn cho phép khi đang lãi, nhưng làm nó tự động dễ thành nhồi lệnh thua |
| PVSRA làm cổng chặn | Nguồn **không có** quy tắc máy móc để suy ra ý đồ MM. Xem mục 7.4 |
| Biến thể buy-limit tại Level | Mâu thuẫn với cơ chế buy-stop của TAH. Xem mục 3.2 |
| Value Zone / EMA200 | Biến thể của cộng đồng, không thuộc Classic gốc |
| Bộ lọc tin tức | Chưa có feed lịch kinh tế đáng tin cho crypto |
| Mức 00/25/50/75 làm cổng | Cần level service theo tick size. Xem mục 7.3 |

---

## 3. Spec-of-record

Khi các nguồn mâu thuẫn, áp thứ tự này. **Post của Sonic/TAH luôn thắng PDF của cộng đồng.**

| Mảng | Nguồn chuẩn |
|---|---|
| Công thức indicator (Dragon, Trend, PVA) | `.mq4` trong `TAH 03-17-2014 Revised.zip` |
| Quy tắc setup (WAVE, EP, SL, TP) | FF post 5377021, bổ sung sắc thái bằng post 6518525 |
| Bối cảnh PVSRA | FF post 7357031 |
| Tham số định lượng (giờ, góc, MTF) | FF post #5 và #12 của sonicdeejay |

### 3.1. Trích dẫn quy tắc gốc

> **WAVE** — L-H-HL starting below Dragon for longs, H-L-LH starting above Dragon for shorts,
> showing "bounce" or "breakthrough" at S&R. Best if WAVE leg #1 crosses thru the Dragon.
>
> **DRAGON** — Must be angled up with PA above it for longs, and angled down with PA below it
> for shorts.
>
> **TREND** — This is a market bias indicator and it is best if PA is above it for longs and
> below it for shorts.
>
> **Placement of EP** — Wait for a WAVE leg #3 candle to break out of the DRAGON, and place your
> entry order at least several pips beyond it.
>
> **Placement of SL** — 1. The SL must be beyond the H/L (for shorts/longs) of the recent large
> scale price swing. 2. The SL must not be more than 100-120 pips from the EP (for EUR/USD).
>
> **Placement of TP** — Select a historic S&R level. Such levels can include whole/half/quarter
> numbers and the middle of consolidation areas.

— FF post 5377021 (traderathome, 2012)

> Enter at least a few pips beyond the end of the candle that first comes out of the Dragon
> (border) on the third/final leg of the wave you are trading.

— FF post 6518525 (traderathome, 2013)

### 3.2. Mâu thuẫn đã biết trong corpus và cách xử lý

| Mâu thuẫn | Nguồn A | Nguồn B | Quyết định |
|---|---|---|---|
| Cơ chế lệnh | TAH: **buy stop** ngoài nến đã đóng | `Sneak Into Classic`: **buy limit** tại Level | Theo TAH (post > PDF cộng đồng) |
| Có SL hay không | TAH: SL bắt buộc, trần 100–120 pip | `Introduction_to_PVSRA`: *"This system do not use an initial SL"* | Theo TAH |
| RR mục tiêu | Không có quy tắc RR trong post gốc | `PVSRA.pdf`: Classic thuần ≈ **1:1**; Classic+PVSRA ≈ 30/70 | Không hard-code RR. TP theo S&R; chế độ `fixed_r` chỉ để đối chứng |

**"RR 3:1" không phải quy tắc của hệ thống.** Nó đến từ nguồn thứ cấp. Số liệu duy nhất trong
corpus là của JRissa: Classic thuần risk 50–100 pip / TP 50–100 pip.

---

## 4. Quyết định đã chốt

| Quyết định | Lựa chọn | Ghi chú |
|---|---|---|
| Hình thức | Biến thể song song | Không sửa `pure_sonic.py` / `trade_setup.py` |
| Phiên giao dịch | **24/7, không lọc phiên, cuối tuần vẫn trade** | Quy tắc cấm phiên Á/cuối tuần của nguồn tồn tại vì **FX đóng cửa** — lý do không còn đúng |
| Ngưỡng PVSRA | **Đo trước rồi quyết** | `tools/measure_pva.py` báo số, chủ project chốt |
| Neo SL | **Cấu trúc** — swing pivot | Đúng nguồn hơn `min(5 nến M15, EMA89 H1)` hiện tại |
| Trần SL | **Bội số ADR** | Xem mục 6.3 |
| Phạm vi | **B — Classic + PVSRA quan sát** | PVSRA ghi lại, không chặn lệnh |
| Phí | Có funding | Xem mục 8 |

---

## 5. Kiến trúc

### 5.1. File mới

| File | Trách nhiệm | Phụ thuộc |
|---|---|---|
| `core/wave.py` | Phát hiện WAVE 3 chân, đánh dấu chân sóng, cờ leg#1 cắt Dragon | `indicators` |
| `core/classic.py` | `SonicClassicConfig` + `build_classic_signals()` — ghép mọi thành phần thành tín hiệu | `indicators`, `wave`, `mtf` |
| `tools/measure_pva.py` | Đo phân phối volume, báo % nến đạt ngưỡng | `indicators` |
| `tests/test_wave.py` | Unit test cho `wave.py` | — |
| `tests/test_classic.py` | Unit test cho `classic.py` | — |

### 5.2. Sửa file có sẵn

- `core/indicators.py` — thêm `adr(df, period=14)`. Nhỏ và cùng họ `atr()`, không đáng tách file.
- `core/indicators.py` — **chuyển** `find_resistance()` từ `backtest/engine.py` sang đây, kèm
  `find_support()` đối xứng cho SHORT. `backtest/engine.py` import lại từ `core.indicators`.
  Lý do: `core/classic.py` cần hàm này để tính TP, mà `core` không được phụ thuộc `backtest` —
  chiều phụ thuộc phải là `backtest → core`. Đây là refactor thuần tuý, hành vi không đổi;
  test hiện có của engine phải xanh nguyên trạng.
- `backtest/engine.py` — thêm `funding_rate_8h` và `funding_series` vào `Costs`; trừ funding
  theo số kỳ 8h mà lệnh nắm giữ.

### 5.3. Không đụng

`core/pure_sonic.py`, `core/trade_setup.py`, `core/signals.py`, `core/mtf.py`.
Mọi bảng kết quả T16–T20 trong README giữ nguyên hiệu lực.

### 5.4. Vì sao tách `wave.py`

Đây là logic mới khó nhất, và là phần duy nhất có thể sai âm thầm mà backtest vẫn chạy trơn.
Tách riêng thì test được độc lập: cho chuỗi giá dựng sẵn, khẳng định wave nhận đúng chân, đúng
thời điểm, không nhìn trước.

Giao diện cố ý hẹp — `classic.py` không cần biết bên trong dùng pivot kiểu gì:

```python
def detect_waves(
    df: pd.DataFrame,          # OHLC khung entry
    bands: pd.DataFrame,       # output sonic_r_bands(), cùng index
    side: str,                 # "LONG" | "SHORT"
    left: int = 3,
    right: int = 3,
) -> pd.DataFrame:
    """
    Trả về DataFrame cùng index với df:
      wave_valid           bool   — có wave hợp lệ đang mở tại nến này
      leg                  int    — 0 = chưa có, 1/2/3 = chân sóng hiện tại
      leg1_crossed_dragon  bool   — chân #1 có xuyên qua Dragon không
      wave_start_idx       Int64  — vị trí pivot L (LONG) / H (SHORT) mở wave
      pivot_2_idx          Int64  — vị trí pivot H (LONG) / L (SHORT)
      pivot_3_idx          Int64  — vị trí pivot HL (LONG) / LH (SHORT)
      leg3_ready_at        Int64  — nến sớm nhất được phép tìm trigger (= confirmed_at của pivot 3)
    """
```

### 5.5. Luồng dữ liệu

```
OHLCV M15 ──┬──────────────────────────────► pva_signals() ────────┐
            │                                                       │
            ├──► sonic_r_bands() ──► detect_waves() ────────────────┤
            │                                                       │
OHLCV H1  ──┴──► sonic_r_bands() ──► align_htf_to_ltf(shift=1) ────┼──► build_classic_signals()
                        │                                          │
OHLCV D1  ───────────► adr() ──────► align_htf_to_ltf(shift=1) ────┘
                                                                    │
                                                                    ▼
                          entry_trigger · sl · tp · rejected_reason · pvsra_*
```

Hai cơ chế chống look-ahead sẵn có **không bị chạm tới**: `align_htf_to_ltf()` shift 1 nến,
và pivot chỉ dùng qua `confirmed_at`.

**Khung thời gian:** M15 vào lệnh, H1 xác nhận, D1 chỉ để tính ADR.
Nguồn ủng hộ H1 làm khung lớn — `Sneak Into Classic`: *"I do recommended H1 TF, because it shows
the exact day to day price movement picture."*

---

## 6. Quy tắc tín hiệu

Mô tả dưới đây cho **LONG**. SHORT đối xứng hoàn toàn (đảo high/low, trên/dưới, dốc lên/xuống).

### 6.1. Điều kiện bối cảnh (khung H1, đã shift 1 nến)

| Cờ | Điều kiện | Nguồn |
|---|---|---|
| `f_dragon_slope` | `slope(ema_fast_close, n) > 0` | "Must be angled up" |
| `f_price_above_dragon` | `close > ema_fast_high` | "with PA above it for longs" |
| `f_trend` | `close > ema_slow` | "best if PA is above it for longs" |

**Khác với code hiện tại:** `pure_sonic.py` đòi **toàn bộ** Dragon nằm trên EMA89
(`ema_fast_low > ema_slow`). Nguồn chỉ đòi **giá** trên Trend. Bản này theo nguồn — lỏng hơn,
sẽ cho nhiều tín hiệu hơn.

**Không dùng ADX, không dùng Donchian breakout.** Cả hai đều không có trong nguồn, và ablation
trong README cho thấy bỏ breakout làm expectancy **tăng**.

Về góc Dragon: nguồn nói "1–2 giờ cho long, tránh 3 giờ", nghĩa là có yêu cầu về **độ lớn** chứ
không chỉ dấu. Nhưng "góc" phụ thuộc tỉ lệ hiển thị chart nên không dịch sang số được một cách
trung thực. Bản này chỉ dùng dấu, và ghi `dragon_slope` ra output để phân tích sau xem có nên
đặt ngưỡng độ lớn không.

### 6.2. WAVE (khung M15)

> **Dragon nào?** WAVE và nến trigger đều dùng **Dragon của khung entry (M15)**, vì nguồn nói
> hệ thống *"trades on the M15 chart"* — sóng và điểm vào đều đọc trên chính chart giao dịch.
> Dragon/Trend khung **H1** chỉ dùng cho ba cờ bối cảnh ở mục 6.1. Đây là hai bộ band khác nhau,
> đừng lẫn.

Thuật toán, dùng pivot đã xác nhận từ `zigzag_confirmed(left, right)` trên M15:

1. Lấy 3 pivot xác nhận gần nhất, yêu cầu mẫu `low → high → low`.
   Gọi là `L`, `H`, `HL`.
2. **`HL.price > L.price`** — nếu không thì không phải higher low, wave không hợp lệ.
3. **Wave phải bắt đầu dưới Dragon**: tại `L.idx`, `close < ema_fast_low` (M15).
4. **`leg1_crossed_dragon`** = tại `L.idx` giá dưới Dragon **và** tại `H.idx` giá trên Dragon
   (`close > ema_fast_high`, M15). Nguồn nói "best if" — nên đây là **cờ ghi lại**, mặc định
   *không* bắt buộc. Có config để bật thành điều kiện cứng, dùng cho ablation.
5. Chân sóng hiện tại = 3 khi nến đang xét ở sau `HL.confirmed_at`.

**Độ trễ xác nhận là có thật và phải chấp nhận.** Pivot `HL` chỉ được biết sau `right` nến.
Nến trigger vì vậy bắt buộc có index `>= HL.confirmed_at`. Nếu giá đã thoát Dragon trước khi
`HL` được xác nhận thì cơ hội đó bị mất — đúng như thực tế giao dịch, không phải lỗi.
`right = 3` (thay vì 5 như code hiện tại) để giảm trễ; đây là tham số cần đo, không phải số
lấy từ nguồn.

### 6.3. Entry

**Nến trigger** = nến đầu tiên có index `>= leg3_ready_at` thoả `close > ema_fast_high` **của
Dragon M15**. Đây là "the candle that first comes out of the Dragon (border) on the third/final leg".

**Khác với code hiện tại:** `f_value_zone` trong `pure_sonic.py` chỉ đòi `close > ema_slow`
(trên EMA89), nên một nến hồi vào Dragon rồi đóng **bên trong** Dragon vẫn qua. Bản này đòi
đóng **trên đỉnh Dragon**.

```
entry_trigger = trigger_bar.high + entry_buffer_atr * ATR(entry, 14)
```

Lệnh **buy stop**, không phải market, không phải limit — post #12 của Sonic:
*"Wait till that break-thru candle close, and we put buy stop/sell stop few pips above or below it."*

Lệnh chờ hết hiệu lực sau `pending_expiry_bars` nến (mặc định 4, giữ parity với paper engine
hiện tại). Sonic để lệnh không khớp rồi đặt lại ở breakout sau (post #14) — nên hết hạn là
hợp lý, dù nguồn không nêu con số.

### 6.4. Stop loss

**Neo:** `sl_raw = HL.price` — đáy của swing gần nhất. Đây là *"the H/L of the recent large
scale price swing"*.

```
sl = sl_raw - sl_buffer_atr * ATR(entry, 14)
risk = entry_trigger - sl
```

**Cổng loại setup** — quy tắc mà code hiện tại **không có**:

```
if risk > sl_max_adr * ADR:   reject("SL_TOO_WIDE")
if risk < sl_min_adr * ADR:   reject("SL_TOO_TIGHT")
```

Setup bị loại **không** được nới SL để lọt. Nguồn nói rõ là bỏ lệnh.

**Vì sao ADR chứ không phải ATR:** ADR là đại lượng bản địa của hệ thống — `Sonic_4 Access
Panel.mq4` tự tính "the daily average range" để vẽ RDH/RDL.

⚠️ **Suy luận, không phải quy tắc thành văn:** nguồn viết trần là "100–120 pip cho EUR/USD".
EURUSD giai đoạn 2012–2014 có biên độ ngày trung bình khoảng 100–120 pip. Từ hai dữ kiện trùng
nhau này, tôi đặt mặc định `sl_max_adr = 1.0`. Nguồn **không** viết "SL ≤ 1 ADR". Ai đọc spec
này cần biết đó là diễn giải.

Sàn `sl_min_adr = 0.25` đến từ Sonic M: *"I do not want you to put anything less than 50 pips.
It is almost certain that you will get washout."* 50/120 ≈ 0.4; đặt 0.25 để nới hơn một chút
vì crypto có ATR intraday khác FX. Cả hai số đều cần đo lại, không phải hằng số thiêng.

Giữ nguyên guard sẵn có của engine: bỏ lệnh có SL < 0.1% giá.

**Cách tính ADR** (theo Access Panel): trung bình `high - low` của `adr_period` ngày gần nhất
trên khung D1, **bỏ qua các nến ngày có biên độ bằng 0** (ngày thiếu dữ liệu). Crypto không có
phiên Chủ Nhật ngắn nên phần xử lý đó của bản gốc không cần.

### 6.5. Take profit

Ba chế độ, chạy song song để so sánh — theo đúng cách `backtest/engine.py` đang làm:

| Chế độ | Định nghĩa | Nguồn |
|---|---|---|
| `sr_level` (mặc định) | Kháng cự lịch sử gần nhất phía trên entry (LONG) / hỗ trợ gần nhất phía dưới (SHORT) | "Select a historic S&R level" |
| `rdh_rdl` | LONG chốt tại `RDH = session_low + ADR`; SHORT chốt tại `RDL = session_high − ADR` | "restrict to only such levels within the day range (ref: RDH, RDL) for quicker in/out" |
| `fixed_r` | `entry + tp_r * risk`. Đối chứng | Không có trong nguồn; `tp_r` mặc định **1.0** theo số liệu JRissa cho Classic thuần |

**RDH/RDL — định nghĩa chính xác** (User Notes của `Sonic_4 Access Panel.mq4`):

> The RDH/RWH line is the computed average range distance **above the session Low**.
> The RDL/RWL line is the computed average range distance **below the session high**.
> The lines will move as new highs/lows are achieved during the session.

Tức đây là **mức chiếu**, không phải đỉnh/đáy thật của ngày, và nó **di chuyển** khi phiên tạo
đỉnh/đáy mới. "Session" với crypto = ngày UTC.

Khi `sr_level` không tìm được mức hợp lệ phía trên entry → rơi về `fixed_r` với `tp_r = 1.0`
và đánh dấu `tp_source = "fallback"` để tách ra khi phân tích.

### 6.6. Không lọc phiên

`f_session` luôn `True`. Config `session_filter: str = "none"` với lựa chọn `"sonic_ny"`
(01:00–04:00 và 07:00–11:00 New York, T2–T6) giữ lại **chỉ để ablation**, không dùng mặc định.

---

## 7. PVSRA — quan sát, không chặn lệnh

### 7.1. Công thức (đã đúng trong code hiện tại)

`indicators.pva_signals()` khớp chính xác `Sonic_2 PVA Candles.mq4`. Dùng lại nguyên vẹn,
**không sửa**. Điểm mấu chốt đã kiểm chứng: cửa sổ trung bình là **10 nến trước, không gồm
nến hiện tại** (`.shift(1)`), đúng như vòng lặp `for(j = i+1; j <= i+10; j++)` trong mq4.

### 7.2. Script đo ngưỡng — `tools/measure_pva.py`

Chạy trên universe và khoảng thời gian thật của project. Xuất bảng:

| Cột | Ý nghĩa |
|---|---|
| `symbol`, `timeframe` | định danh |
| `pct_rising` | % nến đạt `volume >= 1.5 × avg10` |
| `pct_climax` | % nến đạt climax (một trong hai đường) |
| `pct_climax_by_volume` | % nến climax **chỉ do** volume ≥ 200% |
| `pct_climax_by_spread` | % nến climax **chỉ do** `spread × volume` đạt cực trị |
| `p50/p90/p95/p99_ratio` | phân vị của `volume / avg10` |

**Tiêu chí quyết định, đặt trước khi chạy:**

- Nếu `pct_climax` nằm trong khoảng **3–12%** → giữ nguyên 150/200, không chỉnh.
- Nếu ngoài khoảng đó → báo cáo số liệu, chủ project chốt ngưỡng mới. Ngưỡng mới phải là
  **một con số cho toàn universe**, không tinh chỉnh theo từng coin.

Khoảng 3–12% đến từ đâu: đây là ước lượng của tôi về "đủ hiếm để có nghĩa, đủ nhiều để đọc
được cụm", **không** phải con số từ nguồn. Ghi rõ để sau này không ai tưởng nó thiêng.

### 7.3. Quan sát ghi vào mỗi tín hiệu

Chỉ ghi **đại lượng quan sát được**, không ghi suy diễn:

| Cột | Định nghĩa |
|---|---|
| `pva_state` | trạng thái nến trigger: `bull_climax` / `bear_rising` / `normal` / … |
| `pva_ratio` | `volume / avg10` của nến trigger |
| `pva_climax_count_20` | số nến climax trong 20 nến gần nhất |
| `pva_climax_at_highs_20` | số nến climax nằm ở **1/3 trên** của biên độ 20 nến |
| `pva_climax_at_lows_20` | số nến climax nằm ở **1/3 dưới** của biên độ 20 nến |

Hai cột cuối là dạng số hoá được của gợi ý trong `Introduction_to_PVSRA`: *"If you see repeatedly
the volume increasing at the tops, that could mean MM's are bears."*

**Hoãn sang giai đoạn sau:** khoảng cách tới mức 00/25/50/75. Cần level service theo tick size,
mà giá crypto trải từ `0.000001` tới `100000` nên không có định nghĩa "số tròn" dùng chung. Đây
là vấn đề chưa giải, không nên đoán bừa.

### 7.4. Vì sao không dùng làm cổng chặn

Nguồn **không có** quy tắc máy móc nào để suy ra MM là bull hay bear. Chính TAH viết:
*"Becoming proficient with PVSRA is like becoming proficient with an art."*

Mọi cách mã hoá đều là diễn giải của người viết code, không phải quy tắc của Sonic. Cắm thẳng
vào đường vào lệnh = thêm một tầng chủ quan không truy nguồn được, và rất khó gỡ khi kết quả xấu.

**Đường nâng cấp:** sau khi có ≥150 lệnh, chạy phân tích hậu nghiệm xem các cột trên có tương
quan với kết quả không. Chỉ khi có bằng chứng mới bàn tới việc biến thành cổng chặn.

---

## 8. Chi phí

`Costs` hiện có taker 0.05% + slippage 0.02%. Thêm funding:

```python
@dataclass
class Costs:
    taker_fee: float = 0.0005
    slippage: float = 0.0002
    funding_rate_8h: float = 0.0001        # 0.01% mỗi 8h — giả định
    funding_series: dict | None = None     # {symbol: pd.Series} lãi suất thật nếu có
```

- Kỳ funding: 00:00, 08:00, 16:00 UTC.
- Chi phí = tổng lãi suất của các kỳ **đi qua** trong thời gian giữ lệnh.
- Dấu: LONG trả khi rate dương, nhận khi âm. SHORT ngược lại.
- Nếu `funding_series` có dữ liệu cho symbol → dùng số thật; không thì dùng `funding_rate_8h`.

⚠️ Mặc định 0.01%/8h là **giả định**, không phải số đo. Nó xấp xỉ mức trung tính dài hạn của
perp lớn, nhưng funding thật biến động mạnh và có thể vượt xa con số này trong xu hướng mạnh.
Kết quả backtest dùng giá trị giả định phải được ghi nhãn rõ. Ưu tiên nạp `funding_series` thật.

---

## 9. Giao thức kiểm chứng

**Đăng ký trước, chạy một lần, không sweep.**

Cổng chấp nhận edge — dùng lại đúng tiêu chuẩn README:

```
expectancy_r > 0   AND   n_trades >= 150   AND   wilson_ci_low > 0
```

**Chạy chính**

| Nhánh | Mô tả |
|---|---|
| Đối chứng | `pure_sonic` hiện tại, cùng universe / khoảng thời gian / chi phí |
| Bản mới | `classic`, 3 chế độ TP |

**Ablation đã định trước** (chạy sau lần chính, không dùng để chọn tham số cho lần chính):

1. Bắt buộc `leg1_crossed_dragon` bật/tắt
2. Cổng trần SL bật/tắt — đo trực tiếp giá trị của quy tắc mà nguồn có mà code cũ thiếu
3. `session_filter = "none"` vs `"sonic_ny"` — đo xem quy tắc phiên FX còn ý nghĩa với crypto không
4. `right = 3` vs `right = 5` cho pivot — đo chi phí của độ trễ xác nhận

**Bắt buộc báo cáo cùng kết quả**

- `pct_rejected_sl_too_wide` và `pct_rejected_sl_too_tight` — bao nhiêu setup bị cổng loại
- Phân bố `tp_source` (`sr_level` thật vs `fallback`)
- Tổng funding trả, tính theo %R
- Số lệnh mở vào cuối tuần và expectancy của riêng nhóm đó

Hai chỉ số cuối tồn tại để trả lời trực tiếp hai quyết định "biến tấu crypto" — nếu lệnh cuối
tuần tệ hơn hẳn thì quyết định 24/7 sai và phải xem lại.

**Nếu không qua cổng:** đó là kết quả hợp lệ. Không sweep thêm trên cùng dữ liệu. Ghi kết luận
vào README như các vòng T16–T20 đã làm.

---

## 10. Config

```python
@dataclass
class SonicClassicConfig:
    # Indicator — từ .mq4, KHÔNG đổi
    ema_fast: int = 34
    ema_slow: int = 89

    # Khung
    tf_entry: str = "15m"
    tf_main: str = "1H"
    tf_adr: str = "1D"

    # Wave
    pivot_left: int = 3
    pivot_right: int = 3
    require_leg1_cross: bool = False     # nguồn nói "best if", không phải bắt buộc

    # Entry
    entry_buffer_atr: float = 0.05
    pending_expiry_bars: int = 4

    # SL
    sl_buffer_atr: float = 0.5
    sl_max_adr: float = 1.0              # suy luận, xem 6.4
    sl_min_adr: float = 0.25             # suy luận, xem 6.4
    adr_period: int = 14

    # TP
    tp_mode: str = "sr_level"            # sr_level | rdh_rdl | fixed_r
    tp_r: float = 1.0                    # chỉ dùng cho fixed_r và fallback

    # PVSRA — quan sát
    pva_lookback: int = 10               # từ .mq4, KHÔNG đổi
    pva_rising_mult: float = 1.5         # từ .mq4, chỉ đổi sau khi đo
    pva_climax_mult: float = 2.0         # từ .mq4, chỉ đổi sau khi đo

    # Phiên
    session_filter: str = "none"         # none | sonic_ny

    # Slope
    slope_lookback: int = 5
```

**Quy ước:** tham số có ghi "từ .mq4" là hằng số của hệ thống gốc. Đổi chúng nghĩa là không còn
chạy Sonic R nữa — phải ghi rõ trong báo cáo nếu đổi.

---

## 11. Kiểm thử

### 11.1. `tests/test_wave.py`

| Test | Khẳng định |
|---|---|
| Wave hợp lệ | Chuỗi dựng sẵn L-H-HL → `wave_valid == True`, `leg == 3` sau `HL.confirmed_at` |
| HL thấp hơn L | → `wave_valid == False` |
| Wave bắt đầu **trên** Dragon (LONG) | → `wave_valid == False` |
| `leg1_crossed_dragon` | Dựng hai chuỗi, một có cắt Dragon một không → cờ đúng cho cả hai |
| **Không look-ahead** | Với mọi `i`, kết quả tại `i` chỉ phụ thuộc `df[:i+1]`. Kiểm bằng cách chạy lại trên tiền tố và so khớp |
| SHORT đối xứng | Lật dấu chuỗi giá → kết quả SHORT phản chiếu LONG |

Test look-ahead là quan trọng nhất. Nó phải chạy trên chuỗi ngẫu nhiên có seed cố định, không
chỉ trên fixture dựng tay.

### 11.2. `tests/test_classic.py`

| Test | Khẳng định |
|---|---|
| Trigger đúng nến | Nến trigger là nến **đầu tiên** sau `leg3_ready_at` đóng trên đỉnh Dragon |
| Không trigger trước xác nhận | Nến có index `< leg3_ready_at` không bao giờ được chọn |
| Cổng SL rộng | `risk > sl_max_adr * ADR` → `rejected_reason == "SL_TOO_WIDE"`, không sinh entry |
| Cổng SL hẹp | Tương tự với `SL_TOO_TIGHT` |
| SL neo đúng | `sl` nằm dưới `HL.price` đúng `sl_buffer_atr * ATR` |
| TP fallback | Không có kháng cự phía trên → `tp_source == "fallback"`, `tp == entry + 1.0 * risk` |
| 24/7 | Tín hiệu vẫn sinh vào thứ Bảy và Chủ Nhật |
| SHORT đối xứng | Mọi test trên, phiên bản SHORT |

### 11.3. `tests/test_indicators.py` (bổ sung)

- `adr()` trên chuỗi biên độ đã biết → giá trị đúng; nến biên độ 0 bị loại khỏi trung bình.

### 11.4. Backtest engine

- Funding: lệnh giữ 25 giờ với rate cố định → đi qua đúng 3 kỳ → chi phí đúng.
- Funding: LONG rate dương trả tiền; SHORT rate dương nhận tiền.
- Parity: cùng bộ tín hiệu, backtest và paper engine cho cùng entry/SL/TP.

### 11.5. Look-ahead toàn tuyến

Mở rộng `verify_no_lookahead()` cho H1→M15 và D1→M15 trong đường `classic`. **Phải 0 vi phạm.**

---

## 12. Rủi ro và giả định

| # | Rủi ro / giả định | Ảnh hưởng | Giảm thiểu |
|---|---|---|---|
| 1 | `sl_max_adr = 1.0` là **suy luận**, không phải quy tắc thành văn | Cổng loại setup có thể quá chặt hoặc quá lỏng | Ablation #2 đo trực tiếp; báo cáo `pct_rejected_*` |
| 2 | Ngưỡng PVSRA hiệu chỉnh cho **đếm tick** FX, crypto là volume thật | Màu có thể mất ý nghĩa | Đo trước (7.2), tiêu chí quyết định đặt sẵn |
| 3 | Bỏ lọc phiên là **quyết định của chủ project**, không từ nguồn | Có thể mất một bộ lọc thật sự có giá trị | Ablation #3; tách expectancy cuối tuần |
| 4 | Độ trễ xác nhận pivot làm mất cơ hội | Ít lệnh hơn, có thể vào muộn | Ablation #4 (`right` 3 vs 5) |
| 5 | Funding mặc định là giả định, không phải số đo | Chi phí thật có thể cao hơn nhiều | Ưu tiên nạp `funding_series` thật; ghi nhãn khi dùng giả định |
| 6 | Survivorship / listing bias trong universe | Kết quả lạc quan hơn thực tế | Đã ghi trong README; không giải trong vòng này |
| 7 | Corpus nguồn **tự mâu thuẫn** (SL vs no-SL, stop vs limit) | Có thể cài "sai" so với cách một nhánh cộng đồng vẫn chạy | Đã ghi thứ tự ưu tiên ở 3.2; ghi rõ nhánh nào bị bỏ |
| 8 | Không có tài liệu nào chứng minh Sonic R sinh lời | Có thể tốn công cho một hệ thống không có edge | Cổng kiểm chứng ở mục 9; "không có edge" là kết quả hợp lệ |

---

## 13. Định nghĩa hoàn thành

- [ ] `core/wave.py` + test đầy đủ, gồm test không-look-ahead trên chuỗi ngẫu nhiên
- [ ] `core/classic.py` LONG và SHORT + test đầy đủ
- [ ] `indicators.adr()` + test
- [ ] `find_resistance()` / `find_support()` đã chuyển sang `core/indicators.py`, test engine cũ vẫn xanh
- [ ] `tools/measure_pva.py` chạy được, đã báo cáo số liệu, đã chốt ngưỡng
- [ ] Funding trong `backtest/engine.py` + test
- [ ] `verify_no_lookahead()` 0 vi phạm trên đường `classic`
- [ ] Backtest chính + 4 ablation đã chạy, kết quả ghi vào README
- [ ] `pure_sonic.py` / `trade_setup.py` **không có thay đổi nào** (kiểm bằng `git diff`)
