# Sonic Classic (crypto) — Thiết kế

Ngày: 2026-07-29
Trạng thái: chờ duyệt
Người viết: Claude, theo brainstorming với chủ project
Review kỹ thuật: Codex, 2026-07-29

Tài liệu tham chiếu:
- [`research/sonic-usage-and-variants.md`](../../../research/sonic-usage-and-variants.md) — quy tắc gốc đã đối chiếu nguồn
- [`research/sonic-implementation-audit.md`](../../../research/sonic-implementation-audit.md) — quyết định triển khai lần trước
- [`README.md`](../../../README.md) — kết quả backtest T16–T20 và stopping rule

Các PDF/`.mq4` gốc đang là spec-of-record nhưng chưa nằm trong repo. Trước implementation, tạo
`research/sources/sonic/manifest.md` ghi filename, URL gốc, ngày tải và SHA-256. Nếu giấy phép và
chính sách repo cho phép thì lưu cả artifact (ưu tiên Git LFS nếu file lớn); nếu không, lưu artifact
ở kho bền vững riêng và giữ manifest/hash trong Git. Không để nguồn duy nhất ở scratchpad tạm.

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

1. Cài đặt phần Classic đã được cơ giới hoá trong tài liệu này, truy vết được về spec-of-record
   (mục 3), chạy được cho cả LONG và SHORT.
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
| “Bounce/breakthrough at S&R” và độ mượt của WAVE làm cổng | Nguồn mô tả nhưng không cho tolerance/công thức máy móc; vòng này chỉ ghi rõ phần bị bỏ, không giả vờ đã mã hoá đủ |
| Xác nhận price action D1 | Nguồn khuyên M15 xác nhận bằng H1 và D1 nhưng không cho một rule D1 duy nhất; D1 vòng này chỉ cấp ADR |
| Re-entry / đặt lại lệnh trên cùng một WAVE | Cần state machine và quy tắc nhận diện “breakout mới”; vòng này mỗi `wave_id` chỉ có một lần arm |
| Tích hợp scanner/live/paper/UI | Chỉ làm sau khi bản backtest chính qua cổng; không đưa một chiến lược chưa được kiểm chứng vào runtime |

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
| Phiên giao dịch | **24/7, không lọc phiên, cuối tuần vẫn trade** | Đây là giả thuyết thích nghi crypto, không phải hệ quả chắc chắn. Nguồn tránh phiên Á vì momentum/thanh khoản và FX đóng cuối tuần; ablation phải đo lại |
| Ngưỡng PVSRA | **Đo trước rồi quyết** | `tools/measure_pva.py` báo số, chủ project chốt |
| Neo SL | **Cấu trúc** — swing pivot | Đúng nguồn hơn `min(5 nến M15, EMA89 H1)` hiện tại |
| Trần SL | **Bội số ADR** | Xem mục 6.3 |
| Phạm vi | **B — Classic + PVSRA quan sát** | PVSRA ghi lại, không chặn lệnh |
| Phí | Có funding | Xem mục 8 |

### 4.1. Ranh giới giữa nguồn và phần cơ giới hoá

Các lựa chọn dưới đây là **quyết định thiết kế**, không phải câu chữ nguyên văn của Sonic/TAH:

| Hạng mục | Cách cơ giới hoá trong bản này | Trạng thái nguồn |
|---|---|---|
| Trend H1 | `close` đúng phía EMA89 là cổng cứng | Nguồn viết “best if”, không viết bắt buộc |
| D1 | Chỉ dùng ADR, không làm bias/gate | Nguồn khuyên dùng D1 để xác nhận M15 nhưng không cho rule máy móc duy nhất |
| Neo SL | Pivot thứ ba `HL`/`LH` của WAVE | Nguồn viết “recent large scale price swing”, không chỉ đích danh pivot thứ ba |
| “Vài pip” ngoài nến | `0.05 × ATR(14)` | Chuyển đổi đa tài sản; không có trong nguồn |
| Biên SL | `0.5 × ATR(14)` ngoài pivot | Quyết định kỹ thuật, không có trong nguồn |
| Hết hạn pending | 4 nến M15, chỉ một lần arm cho mỗi `wave_id` | Giữ parity với engine hiện tại; nguồn không nêu số nến |
| Pivot | `left=3`, `right=3` | Quyết định về nhiễu/độ trễ; không có trong nguồn |
| S&R tự động | Proxy high/low lịch sử của engine, xem 6.5 | Nguồn không cho thuật toán phát hiện level |
| RDH/RDL khi thoát | Chụp mức tại lúc fill từ dữ liệu đã đóng, không dời TP sau đó | Indicator gốc di chuyển; nguồn không quy định trader phải dời lệnh TP theo |

Vì hai rule về **S&R của WAVE** và **độ mượt/raggedness** chưa được cơ giới hoá, không được mô tả
bản này là “Sonic Classic nguyên bản đầy đủ”. Tên chính xác trong báo cáo là
**Sonic Classic crypto — deterministic subset**.

---

## 5. Kiến trúc

### 5.1. File mới

| File | Trách nhiệm | Phụ thuộc |
|---|---|---|
| `core/wave.py` | Phát hiện WAVE 3 chân bằng reducer nhân quả, đánh dấu chân sóng, cờ leg#1 cắt Dragon | `indicators` |
| `core/classic.py` | `SonicClassicConfig` + `build_classic_signals()` — ghép LONG/SHORT thành contract mà engine đọc được | `indicators`, `wave`, `mtf` |
| `tools/measure_pva.py` | Đo phân phối volume, báo % nến đạt ngưỡng | `indicators` |
| `tests/test_wave.py` | Unit test cho `wave.py` | — |
| `tests/test_classic.py` | Unit test cho `classic.py` | — |
| `tests/test_indicators.py` | Test ADR, S&R proxy và tham số PVA | — |

### 5.2. Sửa file có sẵn

- `core/indicators.py` — thêm `adr(df, period=14)`. Nhỏ và cùng họ `atr()`, không đáng tách file.
- `core/indicators.py` — mở rộng `pva_signals()` nhận `rising_mult` và `climax_mult`, với default
  `1.5/2.0` để giữ parity tuyệt đối. Hiện hàm đang hard-code hai số này; nếu không sửa chữ ký thì
  hai field config ở mục 10 là config chết.
- `core/indicators.py` — **chuyển** `find_resistance()` từ `backtest/engine.py` sang đây, kèm
  `find_support()` đối xứng cho SHORT. `backtest/engine.py` import lại từ `core.indicators`.
  Lý do: `core/classic.py` cần hàm này để tính TP, mà `core` không được phụ thuộc `backtest` —
  chiều phụ thuộc phải là `backtest → core`. Đây là refactor thuần tuý, hành vi không đổi;
  test hiện có của engine phải xanh nguyên trạng.
- `backtest/engine.py` — thêm `side` vào `Trade` và làm toàn bộ fill, SL, TP, MFE/MAE, PnL đối xứng
  LONG/SHORT. Engine hiện tại chỉ mô phỏng LONG; chỉ thêm `find_support()` là chưa đủ.
- `backtest/engine.py` — nhận `fixed_r`, `sr_level`, `rdh_rdl` của Classic mà không làm đổi hành vi
  ba mode legacy (`fixed_2r`, `sr_level`, `fib_extension`) khi chạy signal cũ. Mỗi lần chạy chỉ có
  **một** `tp_mode`; “ba mode song song” ở mục 6.5 nghĩa là ba backtest độc lập trên cùng signal set.
- `backtest/engine.py` — thêm `funding_rate_8h` và `funding_series` vào `Costs`; hạch toán funding
  bằng tiền theo từng kỳ mà vị thế thực sự đi qua, xem mục 8.
- `data/loader.py` / runner backtest — tải OHLCV **perpetual** và funding cùng venue/instrument,
  đồng thời ghi manifest bất biến của dữ liệu. Không lấy spot OHLCV rồi gắn funding perp mà không
  ghi rõ đó là proxy.

### 5.3. Không đụng

`core/pure_sonic.py`, `core/trade_setup.py`, `core/signals.py`, `core/mtf.py`, scanner, paper monitor
và UI. Các file legacy không đổi mã nguồn; baseline đối chứng được **chạy lại** trên cùng snapshot
dữ liệu/cost với Classic. Bảng T16–T20 vẫn là kết luận lịch sử của cấu hình cũ, không được dùng thay
cho lần đối chứng mới.

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
      wave_id              string — side + ba chỉ số pivot; ổn định suốt vòng đời wave
      missed_preconfirmation bool — wave đã breakout trước khi pivot 3 được biết
    """
```

**Không dùng trực tiếp output đã “clean” của `zigzag_confirmed()` trên toàn bộ DataFrame.**
Implementation hiện tại thay pivot cũ bằng một pivot cùng loại cực đoan hơn xuất hiện trong tương
lai. `confirmed_at` của từng pivot vẫn đúng, nhưng pivot cũ đã biến mất khỏi output nên kết quả trên
toàn chuỗi có thể khác kết quả chạy trên tiền tố.

`wave.py` phải lấy luồng fractal thô hoặc tự duyệt một lần theo thứ tự `confirmed_at`, rồi mới gộp
pivot cùng loại tại thời điểm pivot thay thế **được xác nhận**. Không sửa semantic legacy của
`zigzag_confirmed()` trong vòng này; test tiền tố ở 11.1 là contract bắt buộc cho `detect_waves()`.

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

Hai cơ chế chống look-ahead bắt buộc là `align_htf_to_ltf()` shift 1 nến và reducer pivot nhân quả
nói trên. Chỉ kiểm tra `confirmed_at` là **chưa đủ** nếu bước dọn pivot đã nhìn toàn chuỗi.

**Khung thời gian:** M15 vào lệnh, H1 xác nhận, D1 chỉ để tính ADR.
Nguồn ủng hộ H1 làm khung lớn — `Sneak Into Classic`: *"I do recommended H1 TF, because it shows
the exact day to day price movement picture."* Việc không dùng D1 làm bias là sai khác có chủ đích,
đã ghi ở 2 và 4.1.

---

## 6. Quy tắc tín hiệu

Mô tả dưới đây cho **LONG**. SHORT đối xứng hoàn toàn (đảo high/low, trên/dưới, dốc lên/xuống).

### 6.1. Điều kiện bối cảnh (khung H1, đã shift 1 nến)

| Cờ | Điều kiện | Nguồn |
|---|---|---|
| `f_dragon_slope` | `slope(ema_fast_close, n) > 0` | "Must be angled up" |
| `f_price_above_dragon` | `close > ema_fast_high` | "with PA above it for longs" |
| `f_trend` | `close > ema_slow` | "best if PA is above it for longs" |

Ba cờ trên đều là cổng cứng trong bản này. Riêng `f_trend` là cách cơ giới hoá chặt hơn câu
“best if” của nguồn; phải gắn nhãn là quyết định thiết kế khi báo cáo.

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

Thuật toán dùng fractal M15 với độ trễ `right`, được đưa qua reducer nhân quả ở mục 5.4:

1. Tại mỗi nến `i`, chỉ đưa vào state các pivot có `confirmed_at <= i`. Nếu hai pivot liên tiếp
   cùng loại, chỉ thay pivot cũ khi pivot mới đã được xác nhận và cực đoan hơn.
2. Lấy 3 pivot đang nhìn thấy gần nhất, yêu cầu mẫu `low → high → low`.
   Gọi là `L`, `H`, `HL`.
3. **`HL.price > L.price`** — nếu không thì không phải higher low, wave không hợp lệ.
4. **Wave phải bắt đầu dưới Dragon**: tại `L.idx`, `close < ema_fast_low` (M15).
5. **`leg1_crossed_dragon`** = tại `L.idx` giá dưới Dragon **và** tại `H.idx` giá trên Dragon
   (`close > ema_fast_high`, M15). Nguồn nói "best if" — nên đây là **cờ ghi lại**, mặc định
   *không* bắt buộc. Có config để bật thành điều kiện cứng, dùng cho ablation.
6. Chân sóng hiện tại = 3 khi nến đang xét ở hoặc sau `HL.confirmed_at`.

**Độ trễ xác nhận là có thật và phải chấp nhận.** Pivot `HL` chỉ được biết sau `right` nến.
Nến trigger vì vậy bắt buộc có index `>= HL.confirmed_at`. Nếu có bất kỳ nến nào trong khoảng
`HL.idx <= j < HL.confirmed_at` đã đóng ra ngoài Dragon theo hướng trade thì gắn
`missed_preconfirmation = True` và wave đó **không được arm**. Không được chờ một lần thoát Dragon
thứ hai rồi gọi nó là “cây đầu tiên”.
`right = 3` (thay vì 5 như code hiện tại) để giảm trễ; đây là tham số cần đo, không phải số
lấy từ nguồn.

### 6.3. Entry

**Nến trigger** = nến đầu tiên có index `i >= leg3_ready_at` tạo một lần **cross-out** khỏi Dragon
M15:

```text
LONG : close[i] > ema_fast_high[i] AND close[i-1] <= ema_fast_high[i-1]
SHORT: close[i] < ema_fast_low[i]  AND close[i-1] >= ema_fast_low[i-1]
```

Chỉ kiểm `close[i] > ema_fast_high[i]` là chưa đủ: một wave đã nằm ngoài Dragon liên tục tại lúc
pivot được xác nhận sẽ bị nhận nhầm là breakout mới, mâu thuẫn với quy tắc “cơ hội đã mất” ở 6.2.

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
hợp lý, dù nguồn không nêu con số. Cụ thể, signal ở nến `i` được fill trong các nến
`i+1 … i+pending_expiry_bars`; nó hết hạn **trước** nến kế tiếp. Mỗi `wave_id` chỉ được arm một lần.
Re-entry/re-arm cần một wave mới và nằm ngoài vòng này.

Engine giả định stop fill tại đúng `entry_trigger`; slippage đã được tính trong `Costs`. Nếu open
của nến fill gap qua trigger, vòng này vẫn fill tại trigger và phải báo đây là giới hạn của dữ liệu
OHLC, không âm thầm đổi sang một mô hình gap khác.

**Contract output tối thiểu của `build_classic_signals()`:**

| Cột | Contract |
|---|---|
| `entry_signal` | `True` duy nhất tại nến arm, không lặp trên các nến còn lại của cùng wave |
| `side` | `"LONG"` / `"SHORT"` tại signal hoặc rejected setup |
| `wave_id`, `signal_time` | định danh wave và timestamp nến trigger đã đóng |
| `entry_trigger`, `sl`, `risk` | mức lệnh và rủi ro theo công thức trong spec |
| `tp`, `tp_source` | `tp` tĩnh cho `sr_level/fixed_r`; với `rdh_rdl`, `tp` còn `NaN` lúc arm và engine chụp target vào trade tại fill |
| `rejected_reason` | chuỗi rỗng khi hợp lệ; một mã chuẩn khi setup bị loại |

Một rejected setup có `entry_signal=False` nhưng vẫn giữ `side`, `wave_id`, `risk` và
`rejected_reason` để mẫu số của `pct_rejected_*` kiểm toán được. Mẫu số là toàn bộ trigger
candidate đã qua context + WAVE, trước các cổng risk; không phải mọi nến hay mọi wave.

### 6.4. Stop loss

**Neo:** `sl_raw = HL.price` — đáy của swing gần nhất. Đây là cách bản này cơ giới hoá
*"the H/L of the recent large scale price swing"*; nguồn không nói rõ phải dùng `HL` thay vì `L`.

```
sl = sl_raw - sl_buffer_atr * ATR(entry, 14)
risk = entry_trigger - sl
```

**Cổng loại setup** — quy tắc mà code hiện tại **không có**:

```
if ADR is unavailable:                         reject("ADR_UNAVAILABLE")
if sl_max_adr is not None and risk > sl_max_adr * ADR:
                                                 reject("SL_TOO_WIDE")
if risk < sl_min_adr * ADR:                     reject("SL_TOO_TIGHT")
if risk < entry_trigger * min_risk_price_pct:   reject("SL_BELOW_ENGINE_MIN")
```

Setup bị loại **không** được nới SL để lọt. Nguồn nói rõ là bỏ lệnh.
Trước các dòng trên, level không hữu hạn hoặc `risk <= 0` bị loại với `INVALID_LEVELS`. Nếu nhiều
điều kiện cùng đúng, lấy **mã đầu tiên** theo đúng thứ tự pseudocode để báo cáo không phụ thuộc
thứ tự `if` của dev.

**Vì sao ADR chứ không phải ATR:** ADR là đại lượng bản địa của hệ thống — `Sonic_4 Access
Panel.mq4` tự tính "the daily average range" để vẽ RDH/RDL.

⚠️ **Suy luận, không phải quy tắc thành văn:** nguồn viết trần là "100–120 pip cho EUR/USD".
Thiết kế ban đầu suy ra `sl_max_adr = 1.0` từ giả định EURUSD giai đoạn 2012–2014 có ADR cùng cỡ
100–120 pip. Repo hiện **chưa lưu dataset hoặc phép tính tái lập** cho giả định lịch sử đó, nên
không được trình bày nó như một dữ kiện đã kiểm chứng. Nguồn **không** viết "SL ≤ 1 ADR";
`1.0` được giữ làm default đăng ký trước và ablation sẽ so nó với việc bỏ trần, không sweep ngưỡng.

Sàn `sl_min_adr = 0.25` đến từ Sonic M: *"I do not want you to put anything less than 50 pips.
It is almost certain that you will get washout."* 50/120 ≈ 0.4; đặt 0.25 để nới hơn một chút
vì crypto có ATR intraday khác FX. Cả hai số đều cần đo lại, không phải hằng số thiêng.

Guard sẵn có của engine thực chất là `risk < 0.1% × entry`, không phải “SL < 0.1% giá”.
Đưa nó vào signal rejection với mã riêng để không tạo signal mà engine âm thầm bỏ.

**Cách tính ADR** (theo Access Panel): trung bình `high - low` của `adr_period` ngày gần nhất
trên khung D1 UTC, **bỏ qua các nến ngày có biên độ bằng 0** (ngày thiếu dữ liệu). “14 ngày gần
nhất” nghĩa là 14 phiên có range dương gần nhất, `min_periods=14`; không lấy một cửa sổ 14 hàng rồi
chia cho số hàng còn lại sau khi bỏ zero. Sau đó shift một D1 bar trước khi align xuống M15.
Crypto không có phiên Chủ Nhật ngắn nên phần xử lý đó của bản gốc không cần.

Với SHORT, công thức đối xứng bắt buộc là:

```text
entry_trigger = trigger_bar.low - entry_buffer_atr * ATR(entry, 14)
sl            = LH.price + sl_buffer_atr * ATR(entry, 14)
risk          = sl - entry_trigger
```

### 6.5. Take profit

Ba chế độ được chạy **thành ba backtest độc lập** trên cùng signal set:

| Chế độ | Định nghĩa | Nguồn |
|---|---|---|
| `sr_level` (**primary**) | Kháng cự lịch sử gần nhất phía trên entry (LONG) / hỗ trợ gần nhất phía dưới (SHORT) | "Select a historic S&R level" |
| `rdh_rdl` (secondary) | LONG chốt tại `RDH = session_low + ADR`; SHORT chốt tại `RDL = session_high − ADR` | "restrict to only such levels within the day range (ref: RDH, RDL) for quicker in/out" |
| `fixed_r` (secondary) | LONG `entry + tp_r × risk`; SHORT `entry − tp_r × risk` | Không có trong nguồn; `tp_r` mặc định **1.0** theo số liệu JRissa cho Classic thuần |

`sr_level` dùng đúng proxy legacy đã có: nhìn tối đa `sr_lookback_bars` nến **trước signal**,
LONG chọn high nhỏ nhất `> entry × (1 + sr_min_distance_pct)`; SHORT chọn low lớn nhất
`< entry × (1 - sr_min_distance_pct)`. Đây là proxy kiểm thử được, không phải thuật toán S&R do
Sonic công bố. Không được dùng nến signal hay dữ liệu tương lai.

**RDH/RDL — định nghĩa chính xác** (User Notes của `Sonic_4 Access Panel.mq4`):

> The RDH/RWH line is the computed average range distance **above the session Low**.
> The RDL/RWL line is the computed average range distance **below the session high**.
> The lines will move as new highs/lows are achieved during the session.

Tức đây là **mức chiếu**, không phải đỉnh/đáy thật của ngày, và indicator gốc **di chuyển** khi
phiên tạo đỉnh/đáy mới. "Session" với crypto = ngày UTC. Để OHLC backtest không phải đoán thứ tự
high/low nội nến, bản này chụp RDH/RDL **một lần lúc fill**, dùng session low/high qua nến M15 đã
đóng ngay trước nến fill và ADR đã shift. TP không dời sau đó.

Khi target của `sr_level` không tồn tại, hoặc RDH/RDL nằm sai phía entry, rơi về `fixed_r` với
`tp_r = 1.0` và đánh dấu lần lượt `tp_source = "fallback_no_sr"` /
`"fallback_invalid_rdh_rdl"` để tách ra khi phân tích. Giữ `1.0R` vì đây là default đăng ký trước
gần nguồn nhất; phí được phản ánh trong expectancy sau phí, không nâng lên `1.5R` chỉ bằng trực giác.
Các source hợp lệ dùng đúng enum `"sr_level"`, `"rdh"`, `"rdl"` hoặc `"fixed_r"`.

### 6.6. Không lọc phiên

`f_session` luôn `True`. Config `session_filter: str = "none"` với lựa chọn `"sonic_ny"`
([01:00, 04:00) và [07:00, 11:00) theo `America/New_York`, T2–T6) giữ lại **chỉ để ablation**,
không dùng mặc định. Phải dùng timezone database để DST tự đổi; không hard-code UTC offset.

---

## 7. PVSRA — quan sát, không chặn lệnh

### 7.1. Công thức (default hiện tại đã đúng)

`indicators.pva_signals()` với default `lookback=10, rising_mult=1.5, climax_mult=2.0` khớp
`Sonic_2 PVA Candles.mq4`. Chỉ mở rộng chữ ký để multiplier trong config có tác dụng; output với
default phải byte-for-byte tương đương trước thay đổi. Điểm mấu chốt đã kiểm chứng: cửa sổ trung
bình là **10 nến trước, không gồm nến hiện tại** (`.shift(1)`), đúng như vòng lặp
`for(j = i+1; j <= i+10; j++)` trong mq4.

### 7.2. Script đo ngưỡng — `tools/measure_pva.py`

Chạy trên universe và khoảng thời gian thật của project. Xuất bảng:

| Cột | Ý nghĩa |
|---|---|
| `symbol`, `timeframe` | định danh |
| `pct_rising` | % nến đạt `volume >= 1.5 × avg10` |
| `pct_climax` | % nến đạt climax (một trong hai đường) |
| `pct_climax_by_volume` | % nến climax **chỉ do** volume ≥ 200% |
| `pct_climax_by_spread` | % nến climax **chỉ do** `spread × volume` đạt cực trị |
| `pct_climax_by_both` | % nến đồng thời đạt cả hai nhánh; ba nhóm nguyên nhân cộng lại bằng `pct_climax` |
| `p50/p90/p95/p99_ratio` | phân vị của `volume / avg10` |

**Tiêu chí quyết định, đặt trước khi chạy:**

- Nếu `pct_climax` nằm trong khoảng **3–12%** → giữ nguyên 150/200, không chỉnh.
- Nếu ngoài khoảng đó → báo cáo số liệu, chủ project chốt ngưỡng mới. Ngưỡng mới phải là
  **một con số cho toàn universe**, không tinh chỉnh theo từng coin.

Báo cả tỷ lệ pooled theo số nến và median/min/max theo symbol để một coin có lịch sử dài không che
phân bố chéo. Quyết định multiplier ở đây chỉ thay **annotation PVSRA**, tuyệt đối không được làm
thay entry set của lần backtest này. Nếu sau này dùng PVSRA làm gate thì đó là một giả thuyết mới,
cần dữ liệu out-of-sample mới.

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

Định nghĩa chính xác tại trigger `i`: cửa sổ là `[i-19, i]`, `range_low = min(low)`,
`range_high = max(high)`, vị trí mỗi nến dùng `typical_price = (high + low + close) / 3`.
“1/3 trên” là `typical_price >= range_low + 2/3 × (range_high-range_low)`; “1/3 dưới” là
`<= range_low + 1/3 × range`. Nếu chưa đủ 20 nến hoặc range bằng 0, ba cột `_20` là `NaN`,
không ép về 0.

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
    funding_series: Mapping[str, pd.Series] | None = None
    # mỗi Series: UTC funding timestamp -> rate của đúng instrument
```

- Lịch fallback: 00:00, 08:00, 16:00 UTC. Khi dùng `funding_series` thật, timestamp trong series
  là chuẩn vì venue/instrument có thể dùng interval khác.
- Một kỳ `t` được tính khi `entry_time < t <= exit_time`. Quy ước này không tính kỳ đúng lúc bar
  fill mở ra, nhưng tính kỳ đúng lúc bar exit mở ra — bảo thủ với độ phân giải M15.
- Dấu: LONG trả khi rate dương, nhận khi âm. SHORT ngược lại.
- Công thức tiền mặt tại mỗi kỳ:

  ```text
  funding_pnl_t = -side_sign × remaining_size_t × mark_price_t × funding_rate_t
  side_sign = +1 cho LONG, -1 cho SHORT
  ```

  `mark_price_t` dùng mark price thật nếu dataset có; nếu không, dùng close M15 cuối cùng có
  timestamp `< t` và ghi `funding_mark_source = "m15_close_proxy"`.
- Nếu `funding_series` không có symbol thì sinh lịch 8h bằng `funding_rate_8h`. Nếu có symbol nhưng
  thiếu một timestamp trong đoạn lịch sử, **không** tự trộn rate thật và default: fail validation
  cho symbol đó để lỗi dữ liệu không bị che.
- Lưu riêng `funding_pnl`, `funding_periods`, `funding_source`; chỉ sau đó cộng vào `pnl` và
  `r_multiple`. Funding credit âm/positive phải được giữ dấu, không chặn ở 0.
- Mọi index OHLCV/funding phải timezone-aware UTC; reject input naive.

⚠️ Mặc định 0.01%/8h là **kịch bản giả định**, không phải số trung tính đã được repo kiểm chứng.
Funding thật biến động mạnh, đổi dấu và có thể dùng interval khác.
Kết quả backtest dùng giá trị giả định hoặc close proxy phải được ghi nhãn rõ. **Chạy chính ưu tiên
funding thật; default chỉ là sensitivity fallback, không được trình bày như số thực tế.**

---

## 9. Giao thức kiểm chứng

**Đăng ký trước, chạy một lần, không sweep.**

Trước lần chạy tạo kết quả đầu tiên, ghi một manifest version-controlled (ví dụ
`results/classic_validation_manifest.json`) gồm:

- venue, market type (`swap/perpetual`, linear USDT), danh sách **instrument ID cố định**;
- `start_utc`, `end_utc`, timeframe, quy tắc warmup và tiêu chí thiếu dữ liệu;
- hash/size/min-max timestamp của từng file OHLCV và funding;
- commit SHA của code, toàn bộ config, cost source và random seed;
- `primary_tp_mode = "sr_level"` và đúng bốn ablation dưới đây.

Không dùng “top N tại lúc chạy” vì universe sẽ đổi. Không được chạy báo cáo chính khi manifest còn
thiếu field hoặc khi OHLCV là spot nhưng funding là perpetual.

Cổng chấp nhận edge — dùng lại tiêu chuẩn README, tính **sau mọi fee, slippage và funding**:

```
expectancy_r > 0   AND   n_trades >= 150   AND   wilson_ci_low > 0
```

`wilson_ci_low` trong repo là cận dưới Wilson 95% của **winrate trừ winrate hoà vốn plug-in**,
không phải confidence interval của mean expectancy. Giữ metric này để so được với README nhưng
phải gọi đúng tên trong báo cáo.

**Chạy chính**

| Nhánh | Mô tả |
|---|---|
| Đối chứng | `pure_sonic` hiện tại, chạy lại trên đúng manifest / chi phí |
| Bản mới — primary | `classic + sr_level`; **chỉ hàng này** được quyền qua/không qua cổng edge |
| Bản mới — secondary | `classic + rdh_rdl` và `classic + fixed_r`; mô tả sensitivity, không dùng để chọn “mode thắng” |

Nếu một secondary mode qua cổng còn primary không qua, kết luận vẫn là **primary không có bằng
chứng edge**. Không được chọn mode tốt nhất trong ba sau khi xem kết quả; làm vậy tạo ba phép thử
và vi phạm đăng ký trước.

**Ablation đã định trước** (chỉ chạy với primary `sr_level`, sau lần chính, không dùng để chọn tham
số hay tuyên bố edge cho lần chính):

1. Bắt buộc `leg1_crossed_dragon` bật/tắt
2. `sl_max_adr = 1.0` vs `None` — chỉ tắt **trần**, giữ `sl_min_adr` và engine minimum như cũ
3. `session_filter = "none"` vs `"sonic_ny"` — đo xem quy tắc phiên FX còn ý nghĩa với crypto không
4. `right = 3` vs `right = 5` cho pivot — đo chi phí của độ trễ xác nhận

**Bắt buộc báo cáo cùng kết quả**

- `pct_rejected_sl_too_wide` và `pct_rejected_sl_too_tight` — bao nhiêu setup bị cổng loại
- p10/p50/p90/p95 của `risk / ADR`, riêng cả accepted và rejected
- Phân bố `tp_source` theo từng mode, gồm từng loại fallback
- Tổng funding net, funding debit/credit, số kỳ và funding tính theo %R
- Số lệnh mở vào cuối tuần và expectancy của riêng nhóm đó

`pct_rejected_*` và phân bố `risk/ADR` đo trực tiếp cổng SL; breakdown cuối tuần đo quyết định
24/7; funding breakdown đo ảnh hưởng của chi phí perpetual. Ablation chỉ có giá trị chẩn đoán.
Nếu chúng gợi ý một default khác, thay đổi đó phải được đăng ký cho một dataset out-of-sample mới,
không chạy lại trên snapshot này.

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

    # Volatility
    atr_period: int = 14                    # engineering default
    adr_period: int = 14                    # engineering default; D1 UTC, valid days

    # Wave — engineering defaults, không từ nguồn
    pivot_left: int = 3
    pivot_right: int = 3
    require_leg1_cross: bool = False     # nguồn nói "best if", không phải bắt buộc

    # Entry — parity/engineering defaults
    entry_buffer_atr: float = 0.05       # quy đổi "vài pip"
    pending_expiry_bars: int = 4         # fill chỉ ở i+1..i+4

    # SL — suy luận, xem 6.4
    sl_buffer_atr: float = 0.5
    sl_max_adr: float | None = 1.0       # None chỉ dành cho ablation #2
    sl_min_adr: float = 0.25
    min_risk_price_pct: float = 0.001    # guard legacy của engine

    # TP
    tp_mode: str = "sr_level"            # sr_level | rdh_rdl | fixed_r
    tp_r: float = 1.0                    # chỉ dùng cho fixed_r và fallback
    sr_lookback_bars: int = 200           # default legacy find_resistance()
    sr_min_distance_pct: float = 0.005    # default legacy, không từ Sonic

    # PVSRA — quan sát
    pva_lookback: int = 10               # từ .mq4, KHÔNG đổi
    pva_rising_mult: float = 1.5         # từ .mq4, chỉ đổi sau khi đo
    pva_climax_mult: float = 2.0         # từ .mq4, chỉ đổi sau khi đo

    # Phiên
    session_filter: str = "none"         # none | sonic_ny

    # Slope — chỉ dùng dấu; lookback là engineering default
    slope_lookback: int = 5
```

**Quy ước:** tham số có ghi "từ .mq4" là hằng số của hệ thống gốc. Đổi chúng nghĩa là không còn
chạy Sonic R nữa — phải ghi rõ trong báo cáo nếu đổi.

`SonicClassicConfig.__post_init__()` phải reject enum lạ, period/buffer âm, `pivot_left/right < 1`,
`pending_expiry_bars < 1`, `sl_min_adr < 0` và `sl_max_adr <= sl_min_adr` (khi max không phải
`None`). Cửa sổ PVSRA context là hằng số 20 vì tên cột là `*_20`, không phải tham số sweep.

---

## 11. Kiểm thử

### 11.1. `tests/test_wave.py`

| Test | Khẳng định |
|---|---|
| Wave hợp lệ | Chuỗi dựng sẵn L-H-HL → `wave_valid == True`, `leg == 3` sau `HL.confirmed_at` |
| HL thấp hơn L | → `wave_valid == False` |
| Wave bắt đầu **trên** Dragon (LONG) | → `wave_valid == False` |
| `leg1_crossed_dragon` | Dựng hai chuỗi, một có cắt Dragon một không → cờ đúng cho cả hai |
| Pivot cùng loại bị thay | Pivot mới cực đoan hơn chỉ thay pivot cũ từ `confirmed_at` của chính nó, không sớm hơn |
| Breakout trước xác nhận | → `missed_preconfirmation == True`, wave không được arm |
| **Không look-ahead** | Với mọi `i`, kết quả tại `i` chỉ phụ thuộc `df[:i+1]`. Kiểm bằng cách chạy lại trên tiền tố và so khớp |
| SHORT đối xứng | Lật dấu chuỗi giá → kết quả SHORT phản chiếu LONG |

Test look-ahead là quan trọng nhất. Nó phải chạy trên chuỗi ngẫu nhiên có seed cố định, không
chỉ trên fixture dựng tay.

### 11.2. `tests/test_classic.py`

| Test | Khẳng định |
|---|---|
| Trigger đúng nến | Nến trigger là cross-out **đầu tiên** từ trong/dưới ra trên Dragon sau `leg3_ready_at` |
| Đã nằm ngoài Dragon | Close ở ngoài liên tục tại `leg3_ready_at` không được nhận nhầm là trigger |
| Không trigger trước xác nhận | Nến có index `< leg3_ready_at` không bao giờ được chọn |
| Một arm mỗi wave | Một `wave_id` chỉ có một hàng `entry_signal=True`, kể cả pending hết hạn |
| Cổng SL rộng | `risk > sl_max_adr * ADR` → `rejected_reason == "SL_TOO_WIDE"`, không sinh entry |
| Cổng SL hẹp | Tương tự với `SL_TOO_TIGHT` |
| Thiếu ADR | Chưa đủ 14 ngày hợp lệ → `ADR_UNAVAILABLE`, không sinh entry |
| Engine minimum | `risk < entry × 0.001` → `SL_BELOW_ENGINE_MIN`, không để engine bỏ âm thầm |
| SL neo đúng | `sl` nằm dưới `HL.price` đúng `sl_buffer_atr * ATR` |
| TP fallback | Không có kháng cự phía trên → `tp_source == "fallback_no_sr"`, `tp == entry + 1.0 * risk` |
| S&R không nhìn hiện tại | High/low của nến signal không được dùng làm historic S&R |
| PVSRA window | Fixture kiểm đúng typical-price thirds; thiếu 20 nến/range 0 → `NaN` |
| 24/7 | Tín hiệu vẫn sinh vào thứ Bảy và Chủ Nhật |
| SHORT đối xứng | Mọi test trên, phiên bản SHORT |

### 11.3. `tests/test_indicators.py` (bổ sung)

- `adr()` trên chuỗi biên độ đã biết → lấy đúng 14 **ngày hợp lệ** gần nhất; nến range 0 không
  làm giảm mẫu số; trước đủ warmup trả `NaN`.
- `pva_signals()` default giữ đúng output cũ; multiplier custom thay đúng nhánh volume nhưng không
  đổi công thức spread × volume.
- `find_resistance()` sau khi chuyển file giữ parity; `find_support()` phản chiếu chính xác.

### 11.4. Backtest engine

- LONG và SHORT phản chiếu nhau về fill stop, SL/TP, PnL, MFE/MAE.
- Pending ở signal `i` chỉ fill `i+1..i+4`, hết hạn trước `i+5`.
- Nến fill đồng thời chạm SL → fill rồi SL cùng nến theo giả định bi quan, cho cả hai side.
- Funding: lệnh từ `2026-07-01 01:00Z` đến `2026-07-02 02:00Z` với lịch fallback → đúng 3 kỳ.
- Boundary funding: không tính kỳ `t == entry_time`, có tính `t == exit_time`.
- Funding: LONG rate dương trả tiền; SHORT rate dương nhận tiền.
- Funding: rate âm tạo credit; missing timestamp trong real series làm validation fail.
- Regression: ba mode legacy và signal legacy cho output không đổi ngoài các cột funding mặc định 0.

### 11.5. Look-ahead toàn tuyến

Mở rộng `verify_no_lookahead()` cho H1→M15 và D1→M15 trong đường `classic`. **Phải 0 vi phạm.**
Thêm kiểm tra prefix cho toàn bộ cột signal quyết định (`entry_signal`, `side`, `entry_trigger`,
`sl`, `tp_source`, `rejected_reason`), không chỉ cho output `wave.py`.

### 11.6. Data/manifest

- Reject DatetimeIndex naive, duplicate hoặc không tăng dần.
- Reject spot/perp mismatch và instrument thiếu funding khi manifest khai `funding_source=real`.
- Chạy lại từ cùng manifest phải cho cùng hash trade log và report.

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
| 9 | `HL/LH` có thể không phải “large scale swing” mà nguồn nói | SL quá gần và tăng washout | Gắn nhãn là cơ giới hoá; báo `risk/ADR`; không đổi neo sau khi xem cùng snapshot |
| 10 | S&R proxy chỉ là high/low lịch sử, bỏ level tròn và consolidation | Primary TP không tái hiện trọn vẹn source | Gọi đúng là deterministic subset; báo fallback; level service để vòng sau |
| 11 | `zigzag_confirmed()` legacy dọn pivot trên toàn chuỗi | Có thể làm output không prefix-stable nếu tái sử dụng sai | Reducer riêng trong `wave.py`; test prefix bắt buộc |
| 12 | Chọn mode tốt nhất trong ba TP tạo multiple testing | Dễ tuyên bố edge giả | Khoá `sr_level` là primary; hai mode còn lại chỉ secondary |
| 13 | Spot OHLCV + funding perp hoặc funding khác venue | PnL/cost không thuộc cùng instrument | Manifest kiểm market type/venue/instrument và hash dữ liệu |
| 14 | Wilson edge interval không phải CI của expectancy, trade cũng không hoàn toàn độc lập | Độ chắc chắn có thể bị diễn giải quá mức | Gọi đúng metric; giữ gate để parity README, không tuyên bố rộng hơn phạm vi snapshot |
| 15 | RDH/RDL gốc di chuyển nhưng bản này chụp tại fill | Kết quả khác discretionary execution | Ghi rõ source deviation; không dời TP nội lệnh với dữ liệu OHLC |

---

## 13. Định nghĩa hoàn thành

- [ ] `core/wave.py` + test đầy đủ, gồm test không-look-ahead trên chuỗi ngẫu nhiên
- [ ] `core/classic.py` LONG và SHORT + test đầy đủ
- [ ] `indicators.adr()` + PVA multiplier + test
- [ ] `find_resistance()` / `find_support()` đã chuyển sang `core/indicators.py`, test engine cũ vẫn xanh
- [ ] `tools/measure_pva.py` chạy được, đã báo cáo số liệu, đã chốt ngưỡng
- [ ] Engine LONG/SHORT + ba mode Classic + funding, có regression cho mode legacy
- [ ] Manifest venue/instrument/time/hash/config đã commit **trước** lần chạy có kết quả
- [ ] Manifest nguồn ở `research/sources/sonic/manifest.md` có URL/ngày tải/SHA-256; artifact không còn chỉ ở scratchpad
- [ ] `verify_no_lookahead()` và prefix invariance 0 vi phạm trên toàn đường `classic`
- [ ] Backtest primary/secondary + 4 ablation đã chạy đúng một lần, kết quả và trade-log hash ghi vào README
- [ ] Kết luận edge chỉ dựa trên primary `sr_level`; không chọn mode/parameter hậu nghiệm
- [ ] `pure_sonic.py` / `trade_setup.py` **không có thay đổi nào** (kiểm bằng `git diff`)
- [ ] Scanner, paper monitor và UI **không** được nối vào Classic trong vòng này
