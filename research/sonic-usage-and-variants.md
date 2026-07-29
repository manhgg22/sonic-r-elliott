# Sonic R — Cách sử dụng và các biến thể (đọc từ nguồn gốc)

Ngày đọc nguồn: 2026-07-29.
Tài liệu liên quan: [`research/sonic.md`](./sonic.md) (khảo sát nguồn), [`research/sonic-implementation-audit.md`](./sonic-implementation-audit.md) (quyết định triển khai).

## Phạm vi và phương pháp

File này được viết bằng cách **đọc trực tiếp các post gốc** trên thread ForexFactory #114792
(Post #1 và toàn bộ các post được Post #1 dẫn link), cộng với mô tả chính thức của các
indicator TradingView và hai trang mirror của forexstrategiesresources. Mọi quy tắc bên dưới
đều trích từ nguồn, không suy diễn.

**Cập nhật 2026-07-29 (lượt 2):** đã tải và đọc được **toàn bộ file đính kèm trong Post #1** —
5 PDF (188 trang, ~219.000 ký tự) và **source code `.mq4` của cả 6 indicator**. Nội dung mới nằm ở
[Phần VI](#phần-vi--tài-liệu-đính-kèm-post-1-đọc-lượt-2). Vài kết luận ở lượt đọc đầu đã được sửa;
xem [mục 0b](#0b-sửa-lại-so-với-lượt-đọc-đầu).

Những gì **không** đọc được và vì sao:

| Tài liệu | Trạng thái |
|---|---|
| "Secret of Sonic R." pdf | **Link trong Post #1 đã hỏng** — đoạn chữ "HERE" ở mục này không còn là hyperlink. Chỉ còn bản cộng đồng trên Scribd. |
| `forexvietnam.com.vn` | **Domain đã chết** — không phân giải DNS. Đây là nguồn tiếng Việt được `sonic.md` đánh giá tốt nhất; nay không còn. |
| `goldenfund.vn` | Domain nay là công ty vàng bạc đá quý, không còn nội dung Sonic R. |
| `litefinance.org`, `medium.com`, `3-candle-reversal.com` | Chặn kết nối từ môi trường này. |
| `www.sonicrsystem.com` | Không kiểm tra trong lần đọc này. |

Ảnh minh hoạ trong các PDF không trích được (chỉ có text). Với "Sneak Into Classic" và
"Exploit the market price", phần lớn lập luận nằm ở biểu đồ — text đã đủ để lấy quy tắc,
nhưng không đủ để tái tạo ví dụ.

---

## 0. Đính chính so với `research/sonic.md`

Đọc nguồn gốc làm rõ được vài điểm mà file khảo sát trước còn để ngỏ hoặc ghi lệch:

| Mục | `sonic.md` ghi | Nguồn gốc xác nhận |
|---|---|---|
| Ngày mở thread #114792 | "không xác minh được tuyệt đối (suy luận ~2008)" | **First Post: Oct 14, 2008 8:23am**, sửa lần cuối Jun 29, 2025. Đã giải quyết. |
| Số trang thread | ~4.123–4.124 trang | **4.194 trang** tại thời điểm đọc. |
| Số bài của tác giả | sonicdeejay ~9.229; TAH ~22.082 | **sonicdeejay 9.116; traderathome 23.566**. Con số này biến động, đừng dùng làm mốc. |
| Stop loss | "SL đủ rộng — khuyến nghị tới 100 pip cho EURUSD" | Ngược lại: 100–120 pip là **trần**, không phải mức khuyến nghị. Nguyên văn: *"The SL must not be more than 100-120 pips from the EP (for EUR/USD)"*. Kết hợp với Sonic M (*"I do not want you to put anything less than 50 pips"*) thì khoảng hợp lệ là **50–120 pip**. |
| Phiên giao dịch | "chỉ trade phiên Âu/Mỹ" | Hai tầng: post gốc 2008 cho **1–4 AM EST (UK) và 7–11 AM EST (US)**; nhưng bản tổng kết chính thức của TAH siết lại còn **chỉ vào lệnh trong phiên London**, đóng lệnh lúc nào cũng được. |
| "Manual gốc" | PDF trên jimcontent | Link "most recent pdf" trong Post #1 hiện trỏ tới **"Sneak Into Classic.pdf"** của Gupito1508 (2014), không phải manual 2008. |
| Bộ lọc chỉ báo | "bản đầu dùng CCI/QQE" | Bản đầu **Sonic dùng MACD + Stochastic**; CCI ±100 là của bản gốc Raghee Horner; QQE/CCI thuộc các biến thể template khác. |

## 0b. Sửa lại so với lượt đọc đầu

Sau khi đọc được các PDF đính kèm và source `.mq4`, hai kết luận ở lượt đầu phải sửa:

**1. "Classic vào lệnh theo breakout khỏi Dragon" — chưa đủ.**
PDF mà Post #1 dẫn ở mục Manual (`Sneak Into Classic.pdf`) định nghĩa Classic gọn hơn nhiều:

> "Classic can be determined by this: **Buy the first pull back from new high, sell the first
> pullback from new low**. That's the essence of Sonic R. System."

Tức Classic **là một entry theo nhịp hồi**. Mô tả của TAH ("nến đầu tiên thoát khỏi Dragon trên
chân sóng #3") và định nghĩa này không mâu thuẫn — chúng là cùng một thứ nhìn từ hai phía: chân
sóng #3 chính là lúc nhịp hồi kết thúc. Nhưng nếu chỉ đọc bản tổng kết của TAH thì rất dễ hiểu
Classic thành "momentum breakout", và đó là hiểu sai.

**2. Công thức PVA: `shift(1)` là ĐÚNG bản gốc.**
Lượt đầu tôi ghi rằng loại nến hiện tại khỏi trung bình 10 nến là "sai lệch nhẹ so với Pine
tham chiếu". Ngược lại — source `.mq4` của chính TAH tính đúng như vậy:

```mq4
for(j = i+1; j <= i+10; j++) {av = av + Volume[j];}   // 10 nến TRƯỚC, không gồm nến hiện tại
av = av / 10;
if (Volume[i] >= av * 1.5) {va = 2;}                   // Rising
```

Các bản port sang Pine Script mới là bản lệch chuẩn. Xem [mục 21](#21-thuật-toán-pva-nguyên-bản).

---

# PHẦN I — CÁCH SỬ DỤNG (quy tắc gốc)

## 1. Tuyên bố hệ thống (bản tổng kết chính thức)

Nguồn: [post #30,589 — traderathome, 12/02/2012](https://www.forexfactory.com/thread/post/5377021#post5377021)
(chính là bản được dịch ra tiếng Nga và Tây Ban Nha trong Post #1).

> "The Sonic R. System is a method of trading price movements between areas of support and
> resistance. It trades on the M15 chart. It uses a price activity WAVE at an S&R area to
> validate a trade setup, and technical indicators called the DRAGON and the TREND. The DRAGON
> is used for picking the trade entry. The TREND is used to confirm the correct trade direction.
> Historic S&R is used for picking the trade exit."

Ba vai trò tách bạch — đây là chỗ hầu hết bài viết thứ cấp làm sai:

- **S&R** → hợp lệ hoá setup (nơi được phép có setup).
- **WAVE** → xác nhận setup.
- **DRAGON** → chọn **điểm vào lệnh**. Không phải chỉ báo xu hướng.
- **TREND** → xác nhận **hướng**. Không phải chỉ báo vào lệnh.
- **S&R lịch sử** → chọn **điểm thoát**.

## 2. Định nghĩa chỉ báo

**Dragon** = 3 đường EMA chu kỳ 34, áp lần lượt cho High / Close / Low → tạo một dải ("đường hầm").
**Trend** = EMA 89 áp cho Close.

Nguồn gốc: hệ thống lấy cảm hứng từ sách Raghee Horner ("Wave" đổi tên thành "Dragon").
Bản MT4 do traderathome và qFish code; bản TradingView "Dragon and Trend" ghi rõ credit cho hai người này.

## 3. Classic setup — quy tắc đầy đủ

### 3.1. WAVE

- **Long**: `L → H → HL`, bắt đầu **dưới** Dragon, rồi chuyển sang `HH`.
- **Short**: `H → L → LH`, bắt đầu **trên** Dragon, rồi chuyển sang `LL`.
- Sóng phải thể hiện "bounce" hoặc "breakthrough" tại vùng S&R.
- **Tốt nhất khi chân sóng #1 xuyên qua Dragon.**
- TAH bổ sung ([post #44,898](https://www.forexfactory.com/thread/post/6518525#post6518525)):
  *"Smooth PA waves tend to be better than ragged ones."* Sóng có thể ở nhiều hình dạng —
  gồm cả chuỗi HH/HL rất chặt thay vì một sóng lớn trải rộng — và phân biệt sóng tốt/xấu là
  **judgement call**, không có công thức.

### 3.2. Dragon

- Long: Dragon **dốc lên**, giá **nằm trên** Dragon.
- Short: Dragon **dốc xuống**, giá **nằm dưới** Dragon.
- **Góc càng lớn càng tốt.** Sonic lượng hoá bằng mặt đồng hồ
  ([post #5](https://www.forexfactory.com/thread/post/2278415#post2278415)):
  **Long 1–2 giờ, Short 4–5 giờ, tránh 3 giờ (đi ngang)**.
- Dragon dùng để chọn EP, và **biên** (border) của Dragon là mốc.

### 3.3. Trend (EMA 89)

- Tốt nhất khi giá **trên** Trend cho Long, **dưới** Trend cho Short.
- TAH nêu thêm cách dùng thứ hai: **Dragon cắt Trend** cũng có ý nghĩa — cắt lên cho Long,
  cắt xuống cho Short — và ý nghĩa này *không giới hạn ở việc vào lệnh*, mà là **chỉ dấu về
  độ mạnh của xu hướng**.

### 3.4. Entry (EP)

Quy tắc gốc:

> "Wait for a WAVE leg #3 candle to break out of the DRAGON, and place your entry order at
> least several pips beyond it."

Diễn giải chi tiết của TAH: vào lệnh ít nhất vài pip **bên ngoài đầu mút của cây nến đầu tiên
thoát ra khỏi biên Dragon trên chân sóng thứ ba/cuối cùng**. Mục đích của khoảng đệm này là
tránh "head fakes".

Cơ chế đặt lệnh (Sonic, [post #12](https://www.forexfactory.com/thread/post/2280820#post2280820)):

> "We do not buy/sell on the break on the line immediately. **Wait till that break-thru candle
> close**, and we put buy stop/sell stop few pips above or below it."

→ Dùng **buy stop / sell stop**, không dùng lệnh thị trường. Không đuổi giá.
Sonic còn nói thích đặt giá lẻ dạng `.7` hoặc `.4`, và chấp nhận lệnh **không khớp** rồi
đặt lại ở lần breakout sau ([post #14](https://www.forexfactory.com/thread/post/2281562#post2281562)).

Điều kiện phụ: **tốt hơn nếu ngay phía ngoài entry không có vùng S&R mạnh.**

### 3.5. Re-entry

> "It is best to let PA clear the most recent high, or low, and if there is no strong S&R area
> just beyond this re-entry."

TAH mở rộng: re-entry thực chất chỉ là **giao dịch một sóng mới** sau khi setup ban đầu đã chạy.
Thường giá hồi về phía Dragon, chạm Dragon, hoặc xuyên qua Dragon rồi quay lại. Bạn có thể chọn
EP **ở bất kỳ đâu trên chân sóng thứ ba** của sóng mới:

- **Aggressive**: quanh hoặc bên trong Dragon.
- **Conservative**: chờ giá vượt qua đỉnh/đáy trước khi pullback.

### 3.6. Take Profit

> "Select a historic S&R level. Such levels can include whole/half/quarter numbers and the
> middle of consolidation areas."

Tuỳ chọn giảm phơi nhiễm: **giới hạn TP trong biên độ ngày (RDH/RDL)** để vào/ra nhanh.

Thứ tự ưu tiên của S&R theo PVSRA: **số tròn > số nửa > số 1/4 và 3/4**, sau đó mới đến các vùng
S&R hình thành từ price action quá khứ.

### 3.7. Stop Loss

Hai quy tắc, phải thoả **cả hai**:

1. SL phải **nằm ngoài đỉnh/đáy của swing giá lớn gần nhất** (ngoài High cho Short, ngoài Low cho Long).
2. SL **không được xa hơn 100–120 pip** tính từ EP (với EUR/USD).

Cộng thêm từ Sonic M: **không đặt SL dưới 50 pip** — *"It is almost certain that you will get
washout with SL even if the trade go to your direction of trade eventually."*

→ Khoảng làm việc thực tế: **50–120 pip cho EUR/USD**. Nếu quy tắc (1) đòi hỏi SL > 120 pip thì
setup đó bị loại, không phải nới SL.

### 3.8. Thời gian và cặp tiền

- **Khung chính: M15.** M5 chỉ dùng thỉnh thoảng, ngay sau khi London mở, để vào sớm hơn.
- **H4/Daily** dùng để tìm cấu hình nến hỗ trợ cho setup M15: **pin bar, hammer, engulfing**.
- **Không mở lệnh trong phiên Á.** Ưu tiên **phiên London** vì momentum tốt nhất.
  TAH nói thẳng: *"don't pick an entry to a trade outside of the LS. You can close anytime."*
- Khung giờ nguyên bản của Sonic (2008): **1–4 AM EST** (UK) và **7–11 AM EST** (US overlap).
- **Cặp ưu tiên: EUR/USD** — spread thấp nhất, biên độ rộng, và quan trọng nhất là **được giao dịch
  nhiều nhất → volume và momentum tốt nhất**.

### 3.9. Multi-timeframe

Sonic ([post #5](https://www.forexfactory.com/thread/post/2278415#post2278415)):

- Vào lệnh M5 → xác nhận bằng **M15 và H1**.
- Vào lệnh M15 → xác nhận bằng **H1 và D1**.

## 4. Scout trade

Nguồn: [post #75,110 — traderathome](https://www.forexfactory.com/thread/post/7679382#post7679382).
Sonic giới thiệu Scout từ đầu 2011 (Post #1 ghi 2012).

Có **hai loại** Scout, rủi ro rất khác nhau:

**(a) Scout trước Classic** — vào ngược xu hướng.
Bối cảnh: giá vừa chạy rất mạnh một chiều rồi kiệt, hoặc liên tục đập vào S/R, kèm volume rất cao.
Kỳ vọng: giá sẽ quay về phía Dragon, có thể xuyên qua. Loại này **không dùng Dragon để chọn EP**
vì giá có thể ở rất xa Dragon.
TAH đánh giá: **rủi ro cao nhất** — bạn vào ngược xu hướng khi chưa có momentum ngược nào đỡ lưng.
Lời khuyên nhất quán của Sonic là **chờ thêm xác nhận PA** thay vì vào nhanh.

**(b) Scout trong Classic** — nhồi thêm vào lệnh Classic đang chạy.
Thay thế hoàn toàn khái niệm "re-entry" cũ. Điểm tối ưu để thêm là **đỉnh/đáy của nhịp hồi**,
không phải chờ giá vượt đỉnh/đáy cũ.

Kết luận nguyên văn của TAH:

- Scout **trước** Classic → rủi ro cao hơn Scout **trong** Classic.
- Scout trong Classic khi lệnh đang **đỏ** (nghi bị stop hunt) → rủi ro cao, **không khuyến nghị**.
- Scout trong Classic trên các nhịp hồi khi lệnh đang **xanh** → **an toàn nhất**.

### 4.1. Quy tắc nhồi lệnh (rất quan trọng)

Nguồn: [post #68,252](https://www.forexfactory.com/thread/post/7381827#post7381827) và
[post #68,274](https://www.forexfactory.com/thread/post/7382736#post7382736).

Thông điệp của Sonic gửi toàn bộ cộng đồng:

> "Enter on M15 per the Sonic R. System. **Only add if price is moving in your favor**, and that
> is best done while the trade is 'in the green'."

TAH làm rõ thêm: câu này **không phải mệnh lệnh phải nhồi**. Nó có nghĩa: *nếu* bạn đang nghĩ đến
việc nhồi, thì đừng nhồi khi lệnh đang đỏ. TAH thừa nhận bản thân đã nhồi lệnh đỏ nhiều lần, nhưng
Sonic phản đối việc phổ biến cách đó vì trái với chủ đề "low risk" của hệ thống.

Đồng thời, PVSRA lại khuyến khích **xây lệnh bằng nhiều entry nhỏ** thay vì một entry lớn duy nhất —
vì Market Maker phản ứng với dòng lệnh và sẽ đẩy giá làm entry đơn lẻ trở nên "kém tối ưu".
Hai ý này không mâu thuẫn: **chia nhỏ được, nhưng chỉ thêm khi đang có lãi.**

## 5. PVSRA

Nguồn chính: [post #67,736 — traderathome, 22/03/2014](https://www.forexfactory.com/thread/post/7357031#post7357031).

**PVSRA là phương pháp phân tích, KHÔNG phải phương pháp vào lệnh.** Post #1 nói rõ điều này, và
mô tả chính thức của indicator TradingView cũng lặp lại: *"a form of market analysis and not a
trading method"*.

### 5.1. Mục đích

1. Xác định **Market Maker (MM) đang là bull hay bear**.
2. Xác định giá đang ở pha **"Run for Profits"** hay **"Position Building"**.

### 5.2. Ba thành phần

- **Price**: cấu hình từng nến (hammer, engulfing…), mẫu hình (H&S), và wave (HH/HL hay LH/LL).
  Ghi nhớ giá thường di chuyển theo swing liên ngày 100+, 150+, 200+, 250+ pip → vị trí hiện tại
  trong swing giúp đoán đang ở pha nào.
- **Volume**: là **số lệnh khớp trên server broker** (không lộ khối lượng tiền). Cái cần tìm là
  **mức tăng đáng kể so với volume liền trước**. **Chart M1 là tốt nhất** để phát hiện hoạt động
  giao dịch tăng cao đang xảy ra tại đỉnh hay tại đáy.
- **S&R**: ưu tiên các mốc chia tư giữa các số tròn — **số tròn > số nửa > 1/4 và 3/4** — rồi mới
  đến S&R từ price action quá khứ.

### 5.3. Tiền đề cốt lõi

> "Bull MMs prefer **buying below** key S&R and bear MMs prefer **selling above** key S&R."

→ Nhìn xem phần lớn giao dịch đang diễn ra **trên hay dưới** mốc S&R quan trọng để suy ra MM là bull hay bear.

### 5.4. Chu kỳ MM (phần quyết định của phương pháp)

1. Đầu xu hướng tăng: MM bull bắt đầu pha **"Run for Profits"**. Họ đã gom long từ cuối xu hướng
   giảm trước và trong giai đoạn đi ngang — đó là pha **"Position Building"** của họ.
2. Trong xu hướng tăng, MM bull **tiếp tục thêm long ở các nhịp hồi xuống**, đôi khi đẩy giá
   xuống dưới mốc S&R quan trọng để gom. → **Đây là cơ hội long: hồi sớm trong xu hướng tăng mới.**
3. Đến một điểm, MM chuyển từ bull "Run for Profits" sang **bear "Position Building"**. Giá vẫn
   còn tăng, nhưng MM bear đang bán ra tại đỉnh — họ vẫn đẩy giá lên để dụ phe long mua vào,
   tạo thanh khoản cho họ đóng long và mở short.
4. Cuối cùng MM bear bẻ giá xuống → bắt đầu bear "Run for Profits", và họ thêm short ở các
   nhịp hồi lên. → **Đây là cơ hội short.**

**Quy tắc rút ra: chỉ giao dịch trong pha "Run for Profits".**
Lý do: ta biết được MM là bull hay bear, nhưng **không thể biết pha Position Building kéo dài
bao lâu**. Vào lệnh theo hướng "status" của MM trong lúc họ còn đang Position Building ngược
hướng đó là cách chắc chắn nhất để bị kẹt.

Hệ quả trực tiếp: **bạn sẽ không giao dịch đỉnh/đáy.** Bạn chờ nhịp hồi sớm trong pha Run for Profits.

### 5.5. PVSRA Quick Guide

Nguồn: [post #68,619](https://www.forexfactory.com/thread/post/7396684#post7396684).

1. Tìm setup **Classic long** nếu MM là **bull** và PA đang **bullish**.
2. Tìm setup **Classic short** nếu MM là **bear** và PA đang **bearish**.

TAH cảnh báo dứt khoát về một hiểu sai phổ biến:

> "It is **not** alright to trade counter trend just because the MMs are. If the MMs are bulls,
> but pushing the price lower, it is not alright to add long."

Đây là điểm sửa lại "luật cũ" mà theo TAH đã gây drawdown nặng cho nhiều người.

### 5.6. Quy tắc tô màu PVA (công thức chính xác)

Từ mô tả indicator TradingView "PVA Candles and Volume" (credit traderathome, qFish):

| Điều kiện | Định nghĩa | Màu nến tăng | Màu nến giảm |
|---|---|---|---|
| **Climax** | `volume ≥ 200%` trung bình 10 nến **HOẶC** `spread × volume ≥` giá trị lớn nhất của tích đó trong 10 nến | Green | Red |
| **Rising above average** | `volume ≥ 150%` trung bình 10 nến | Blue | Blue-violet |
| **Bình thường** | còn lại | Silver / xám nhạt | Xám đậm |

Lưu ý cài đặt: phải set độ trong suốt thân + viền nến của chart chính về 100% và chỉnh màu râu nến
tương ứng, nếu không indicator sẽ bị nến gốc che.

## 6. Trade Execution

Nguồn: [post #78,059 — traderathome](https://www.forexfactory.com/thread/post/7945770#post7945770),
dựa trên đóng góp của Gupito1508.

> "Every trade, regardless of preceding analysis and point of entry, **must be considered a losing
> trade**. And with this mindset, we must have a plan for 'why' and 'when' we will exit."

- **Why** vào lệnh: vì price action đã tạo ra setup Classic, **đúng thời điểm phiên**.
- **When** vào lệnh: **ngay lập tức**. Setup đã có thì không có lý do chần chừ.
- Kích thước lệnh và vốn phải đủ để chịu được các "tai nạn" xảy ra với một lệnh vốn dĩ hợp lệ.
- Khi thị trường chứng minh lệnh sai → **thoát ngay**, không giữ lâu.

## 7. Quản trị vốn — Sonic M

Nguồn: [post #44,583 — sonicdeejay](https://www.forexfactory.com/thread/post/6488843#post6488843),
kèm file `Sonic M.xlsx`.

Máy tính lot size, 6 bước: vốn → % rủi ro (ví dụ 5%) → số tiền tối đa được mất mỗi lệnh →
SL tính bằng pip (**không dưới 50**) → giá trị $/pip → lot tối đa.

Điểm cốt lõi Sonic nhấn mạnh là **hiệu ứng cộng dồn**: lot tự tăng khi tài khoản lớn lên và
tự giảm khi tài khoản co lại — *"reducing the risk while you are trading poorly"*.

> Lưu ý: mức 5% trong ví dụ của Sonic là **minh hoạ cách dùng file**, không phải khuyến nghị
> rủi ro. 5%/lệnh là rất cao theo chuẩn quản trị rủi ro hiện đại.

## 8. Bộ chỉ báo chính thức (2014 Release)

Nguồn: [post #67,352 — traderathome](https://www.forexfactory.com/thread/post/7343308#post7343308).
Yêu cầu MT4 **Build 600+**. Phải nạp lên chart **theo đúng thứ tự số** để hiển thị đẹp.

| # | Indicator | Chức năng |
|---|---|---|
| 1 | `Sonic_1 Solid Dragon` | Vẽ Dragon; có tuỳ chọn hiện luôn đường Trend |
| 2 | `Sonic_2 PVA Candles` | Nến tô màu theo PVA |
| 3 | `Sonic_3 Trade Levels` | Thay thế đường trade level mặc định của MT4: EP, EP trung bình, TP, SL, kèm nhãn P/L |
| 4 | `Sonic_4 Access Panel` | (trước gọi Control Panel) đồng hồ, bid line, levels, pivots, RDH/RDL, separator ngày, mốc mở/đóng các phiên. **Có thủ tục setup bắt buộc — phải đọc User Notes** |
| 5 | `Sonic_5 FFCAL Panel` | Liệt kê tối đa 4 sự kiện tin sắp tới có thể gây biến động |
| 6 | `Sonic_6 PVA Volumes` | Volume tô màu theo PVA, ở sub-window đầu tiên |

**Cách đọc tài liệu indicator**: TAH viết "User Notes" ngay đầu source code của từng indicator,
và coi đó là manual chính thức. Mở MetaEditor từ MT4 → Navigator → Indicators → double-click.

Cài đặt: giải nén ra 2 thư mục (chart đen / chart trắng) → `.ex4/.mq4` vào `MQL4/Indicators`,
`.tpl` vào `Templates` → restart MT4.

---

# PHẦN II — CÁC BIẾN THỂ

Sonic R tồn tại ít nhất **6 biến thể** khác nhau đáng kể. Nhầm lẫn giữa chúng là nguyên nhân chính
khiến các bài viết thứ cấp mâu thuẫn nhau.

## Biến thể 1 — Bản gốc 2008 ("Sonic Striker" era)

Đây là bản Sonic post trong những ngày đầu, **có bộ lọc chỉ báo**, thứ mà bản Classic sau này bỏ đi.

- Khung: M5/M15 scalp.
- Vào lệnh: chờ nến vượt đường trắng (biên Dragon) **đóng nến**, đặt buy/sell stop vài pip ngoài.
- **Bộ lọc: MACD dốc theo hướng lệnh + Stochastic chỉ theo hướng lệnh.**
  Sonic trả lời rõ là **không quan tâm Stoch ở mức nào**, chỉ cần hướng: *"Stoch up is all I want."*
- Bản gốc của Raghee Horner (theo thành viên emacro) dùng **CCI vượt ±100** làm xác nhận.

## Biến thể 2 — "Full Version" trên forexstrategiesresources

Bản template lưu hành rộng, **khác đáng kể so với Classic** — nếu bạn tải template này về mà đọc
manual Classic thì sẽ thấy không khớp.

- Chỉ báo: **Stealth LCD V10, QQE MTF, CCI(63), EMA 34 H/C/L, SMA 50**.
- Buy khi: LCD xanh + QQE trên 50 + CCI trên 0 (an toàn hơn: trên +75) + giá trên SMA 50 +
  giá trên đường trắng trên và đường dốc lên → vào 5–7 pip trên nến trước, sau khi nến đóng.
- Sell: điều kiện đối xứng (LCD vàng, QQE dưới 50, CCI dưới 0 / dưới −75).
- **SL dùng SMA 50**: thoát khi giá đóng cửa ở phía ngược lại của SMA 50.
- Không định nghĩa TP.
- Cặp: EURUSD, GBPUSD, USDCAD, EURJPY, GBPJPY. Phiên: 1–4 AM EST và 7–11 AM EST.

**Điểm khác biệt lớn nhất so với Classic: không có EMA 89, thay bằng SMA 50 làm cả trend filter lẫn exit.**

## Biến thể 3 — "Sonic R System TAH"

Bản mang tên TAH trên forexstrategiesresources, nằm giữa bản gốc và Classic.

- Chỉ báo: Tunnel Dragon (EMA 34 ×3), **EMA 89**, SHI_Channel_MTF, QQE hoặc CCI (bắt phân kỳ),
  SonicR VSA Histogram.
- **Ba kịch bản vị trí của EMA 89 so với Dragon** — đây là phần không có trong bản Classic:
  1. EMA 89 **trên** Dragon → giao dịch cú cắt biên trên.
  2. EMA 89 **dưới** Dragon → giao dịch cú cắt biên dưới.
  3. EMA 89 **nằm trong** Dragon → giao dịch cú breakout khỏi vùng giữa.
- Entry long mô tả cụ thể: *"Wait for current candle high cross 89EMA and make sure the previous
  candle high is lower than Tunnel Dragon 34 EMA high. Wait for the current candle to close.
  Now mark that candle high + 5 pips as your long entry."*
- **SL theo fractal**: đặt ngoài fractal gần nhất — fractal đó phải cao hơn 2 fractal bên trái
  (cho short) hoặc thấp hơn 2 fractal bên trái (cho long). Trần: 100–120 pip.
- TP phân biệt theo bối cảnh: lệnh **ngược** khung lớn → thoát tại biên channel;
  lệnh **thuận** khung lớn → nhắm S&R lịch sử, số tròn/nửa/1-4, hoặc giữa vùng consolidation.
- Multi-TF: so sánh hướng H4 / H1 / M15 (hoặc D1).

## Biến thể 4 — Classic + PVSRA (bản chính thống 2012–2014)

Chính là toàn bộ Phần I ở trên. Đặc trưng: **bỏ hết bộ lọc oscillator**.
TAH về sau coi QQE/CCI là không cần thiết; vai trò xác nhận chuyển sang **volume (PVSRA)** và
**cấu hình nến H4/D1**.

Đây là bản mà Post #1 gọi là core và là bản duy nhất có tài liệu đầy đủ.

## Biến thể 5 — "Sonic R.evolution" (hanz1881, 2017)

Thread riêng: [#703694](https://www.forexfactory.com/thread/703694-sonic-revolution).
Đây là bản **đơn giản hoá mạnh**, gần như là một hệ thống khác dùng chung ý tưởng dải MA.

- Chỉ báo: **SMMA 20** áp cho Close / High / Low (không phải EMA 34), + "Icitan Signal" (`.ex4` đóng mã) + Volume.
- **Khung: H4** (không phải M15).
- Buy: giá trên SMA 20 High + mũi tên Icitan hướng lên. Sell: đối xứng.
- Exit: swing high/low gần nhất, **hoặc** mũi tên ngược xuất hiện, **hoặc** nến đảo chiều.

⚠️ Phụ thuộc vào một file `.ex4` đóng mã do cá nhân phát hành — không kiểm chứng được logic.
Slogan "BUY SELL OR PASS IN 5 SECONDS" mâu thuẫn trực tiếp với tinh thần discretionary của bản gốc.

## Biến thể 6 — Các bản TradingView

| Script | EMA sử dụng | Ghi chú |
|---|---|---|
| **Dragon and Trend** (ForexPipCheats) | 34 (H/C/L) + 89 | Bản trung thành nhất với gốc. Credit traderathome & Fish. Closed-source nhưng free. |
| **PVA Candles and Volume** (ForexPipCheats) | — | Nguồn định nghĩa PVSRA chuẩn (mục 5.6). |
| **Sonic R** (VuTienTurtleTrader) | 34 + 89 (+200) | Mã nguồn mở. |
| **Sonic R + EMA system** (Dzung_Naga) | 34 (H/L/C) + 89 + **144, 200, 257, 458, 630** | Mã nguồn mở. Bốn EMA dài đóng vai trò **S&R động**. Khung khuyến nghị **D1 hoặc H4** (không phải M15). Tín hiệu: **Dragon cắt EMA 89** — đây là biến thể *cơ giới hoá* điều mà TAH chỉ coi là "chỉ dấu độ mạnh xu hướng". |
| **Sonic R System Final** (VuTienTurtleTrader) | — | **Invite-only, trả phí.** Mô tả quảng cáo "monthly profit up to 100%" — không có sao kê kiểm toán. Không dùng. |

### Về EMA 200 và "Value Zone"

**EMA 200 không thuộc Classic nguyên bản.** Không post gốc nào trong Post #1 nhắc tới nó.
Khái niệm "Value Zone" (vùng giữa EMA 34 / 89 / 200, chỉ vào lệnh khi giá retest về vùng này)
là **sáng tạo của cộng đồng Việt Nam**, phổ biến qua các trang như goldenfund.vn và marginatm.

Nó không sai về mặt logic — nhưng cần biết rằng nó **thay đổi bản chất entry**: Classic vào theo
**breakout khỏi Dragon** (momentum), còn Value Zone vào theo **retest về Dragon** (pullback).
Hai cách này cho tín hiệu ở hai thời điểm khác nhau của cùng một sóng.

### Về EMA 170 / 510 / 630

Đây là **quy đổi khung thời gian trên chart M1**, không phải EMA mới:
`M5-on-M1 = 34 × 5 = 170`; `M15-on-M1 = 34 × 3 × 5 = 510`.
Nếu bạn đã dùng dữ liệu native M15/H1 thì thêm các EMA này là **trùng thông tin**.

## Bảng đối chiếu nhanh

| | Gốc 2008 | Full Version | TAH | **Classic+PVSRA** | R.evolution | Dzung_Naga |
|---|---|---|---|---|---|---|
| Khung | M5/M15 | M5/M15 | M15 | **M15** | H4 | D1/H4 |
| Dải chính | EMA34 H/C/L | EMA34 H/C/L | EMA34 H/C/L | **EMA34 H/C/L** | SMMA20 H/C/L | EMA34 H/L/C |
| Trend line | — | SMA 50 | EMA 89 | **EMA 89** | — | EMA 89 |
| Bộ lọc | MACD + Stoch | LCD/QQE/CCI | QQE/CCI + VSA | **PVSRA volume** | Icitan `.ex4` | — |
| Trigger | Breakout Dragon | Hợp lưu chỉ báo | Cắt EMA89 | **Nến chân sóng #3 thoát Dragon** | Giá vs SMA20 | Dragon × EMA89 |
| SL | S&R | SMA 50 | Fractal, ≤120p | **Swing ngoài, 50–120p** | — | — |
| TP | Phá mẫu hình | — | S&R / channel | **S&R lịch sử** | Swing gần nhất | — |
| Tài liệu | Rải rác | Trang mirror | Trang mirror | **Đầy đủ** | 1 post | Mô tả script |

---

# PHẦN III — CHECKLIST THỰC THI (bản Classic)

Trước khi vào lệnh, xác nhận theo thứ tự:

1. **Phiên** — đang trong phiên London (hoặc 1–4 / 7–11 AM EST). Nếu không → bỏ qua.
2. **Tin** — kiểm tra FFCAL Panel, không có sự kiện lớn sắp tới.
3. **Bias khung lớn** — H4/D1 có nến hỗ trợ (pin bar / hammer / engulfing)? Hướng H1 và D1 có
   thuận không?
4. **S&R** — giá đang ở một vùng S&R có ý nghĩa (số tròn > nửa > 1/4)?
5. **PVSRA** — MM là bull hay bear? Đang ở pha Run for Profits hay Position Building?
   **Chỉ vào lệnh trong pha Run for Profits, cùng hướng với status của MM.**
6. **Trend** — giá ở đúng phía EMA 89?
7. **Dragon** — góc đủ dốc (1–2h cho long, 4–5h cho short)? Tránh 3h.
8. **Wave** — đã có L-H-HL (long) / H-L-LH (short)? Chân #1 có xuyên Dragon không?
9. **Nến trigger** — nến của chân sóng #3 đã **thoát khỏi biên Dragon và ĐÃ ĐÓNG** chưa?
10. **EP** — đặt **buy stop / sell stop** vài pip ngoài đầu mút nến đó. Phía ngoài có S&R mạnh không?
11. **SL** — ngoài swing lớn gần nhất **và** trong khoảng 50–120 pip. Nếu không thoả cả hai → **bỏ setup**.
12. **TP** — chọn mức S&R lịch sử cụ thể (cân nhắc giới hạn trong RDH/RDL).
13. **Size** — tính qua Sonic M từ khoảng cách SL.

Sau khi vào lệnh:

- Chỉ nhồi thêm khi lệnh **đang xanh** và giá đang chạy thuận.
- **Không** nhồi khi lệnh đang đỏ.
- Khi setup không còn hợp lệ → thoát, không chờ SL.

---

# PHẦN IV — MÂU THUẪN VÀ ĐIỂM CẦN LƯU Ý

1. **"Phiên London" vs "1–4 và 7–11 AM EST"** — hai mốc này không trùng nhau hoàn toàn.
   Bản 2008 rộng hơn (gồm cả overlap US), bản tổng kết của TAH siết còn London. Nguồn không
   giải thích lý do siết lại.

2. **Sóng "đẹp" là judgement call.** TAH nói thẳng rằng có những setup hợp lệ *không* trông giống
   sóng lý tưởng, và rằng nhiều EP được post lên thread **không đúng quy tắc EP cơ bản** (quá gần
   Dragon, thậm chí sai phía Dragon) — nhưng điều đó *"does not imply the basics have changed"*.
   → Hệ thống có **một lõi cơ giới hoá được** và **một lớp discretion không cơ giới hoá được**.
   Bất kỳ nỗ lực tự động hoá nào cũng chỉ nắm được lớp thứ nhất.

3. **Nhồi lệnh: hai thông điệp gần đối nghịch.** PVSRA khuyến khích chia nhỏ entry để chống MM;
   Sonic cấm nhồi khi đỏ. TAH thừa nhận bản thân làm khác lời khuyên chính thức.
   → Quy tắc an toàn: chia nhỏ **chỉ trong vùng xanh**.

4. **Không có backtest độc lập.** Toàn bộ bằng chứng trong thread là **ảnh chụp các lệnh đã chọn lọc**.
   Không có sao kê kiểm toán nào cho hệ thống này. Chính Sonic viết: *"It is not the magic bullet.
   Nothing is."* và *"There is no 'mechanical' system or indicator that can really predict where
   the price will go with 60~100% accuracy."*

5. **Phản biện xuất hiện ngay ở post #4** (Yaad, cùng ngày mở thread):
   *"Looks good when the market is trending, but in a ranging market you will get murdered even if
   you are entering a few pips above/below the set up bar."*
   Sonic **đồng ý hoàn toàn** và đưa 4 biện pháp: khung giờ, góc Dragon, multi-TF, không đuổi giá.
   → Bốn biện pháp đó chính là bộ lọc sideways của hệ thống. Bỏ chúng đi thì phản biện của Yaad đúng.

6. **Volume trong forex là volume tick của broker**, không phải volume thật của thị trường.
   PVSRA xây trên đại lượng này. Khi chuyển sang thị trường có volume thật (crypto perpetual,
   chứng khoán), ý nghĩa của các ngưỡng 150%/200% **không tự động tương đương** và cần đo lại.

7. **Cảnh giác `.ex4` đóng mã.** Cả "Icitan Signal" lẫn nhiều bản "Sonic R" trôi nổi đều là `.ex4`.
   Bộ chính thống duy nhất là file đính kèm trong Post #1.

---

# PHẦN V — NGUỒN GỐC (link trực tiếp)

## Post nền tảng

| Nội dung | Link |
|---|---|
| **Post #1** (mục lục toàn hệ thống) | https://www.forexfactory.com/thread/114792-sonic-r-system |
| Bản tổng kết hệ thống (EN) | https://www.forexfactory.com/thread/post/5377021#post5377021 |
| "The Sonic R. System Basics" (bản sau, chi tiết hơn) | https://www.forexfactory.com/thread/post/6518525#post6518525 |
| 4 biện pháp chống whipsaw (Sonic, 2008) | https://www.forexfactory.com/thread/post/2278415#post2278415 |
| Khung giờ + cơ chế buy/sell stop (Sonic, 2008) | https://www.forexfactory.com/thread/post/2280820#post2280820 |
| Ví dụ giao dịch có chú thích (GBP/USD) | https://www.forexfactory.com/thread/post/2281562#post2281562 |
| **Scout trade** (định nghĩa đầy đủ) | https://www.forexfactory.com/thread/post/7679382#post7679382 |
| **PVSRA** (bài giảng gốc của TAH) | https://www.forexfactory.com/thread/post/7357031#post7357031 |
| PVSRA Quick Guide + cảnh báo counter-trend | https://www.forexfactory.com/thread/post/7396684#post7396684 |
| Quy tắc nhồi lệnh ("only add in the green") | https://www.forexfactory.com/thread/post/7381827#post7381827 |
| Làm rõ quy tắc nhồi lệnh | https://www.forexfactory.com/thread/post/7382736#post7382736 |
| **Trade Execution** | https://www.forexfactory.com/thread/post/7945770#post7945770 |
| **Sonic M** (quản trị vốn) | https://www.forexfactory.com/thread/post/6488843#post6488843 |
| **2014 Release** — mô tả 6 indicator | https://www.forexfactory.com/thread/post/7343308#post7343308 |
| Quick Start Guide cho indicator | https://www.forexfactory.com/thread/post/7355377#post7355377 |
| Bản tóm tắt tiếng Nga | https://www.forexfactory.com/thread/post/5557152#post5557152 |
| Bản tóm tắt tiếng Tây Ban Nha | https://www.forexfactory.com/thread/post/5559065#post5559065 |

## File tải trực tiếp

| File | Link |
|---|---|
| **TAH 03-17-2014 Revised.zip** (bộ indicator + template chính thống) | https://www.forexfactory.com/attachment/file/1572569?d=1418607844 |
| `5steps.pdf` (đọc trước tiên, theo lời Sonic) | https://www.forexfactory.com/attachment/file/1383779?d=1394520328 |
| `Sneak Into classic.pdf` (Gupito1508 — hướng dẫn từng bước vào Classic) | https://www.forexfactory.com/attachment/file/1445705?d=1402491913 |
| `PVSRA.pdf` (jackywang5 — 130+ trang, tổng hợp toàn bộ post PVSRA) | https://www.forexfactory.com/attachment/file/1205207?d=1370192837 |
| `Introduction_to_PVSRA.pdf` (Tymedu — 12 trang nhập môn) | https://www.forexfactory.com/attachment/file/1205218?d=1370196413 |
| `Exploit the market price by Volume reading.pdf` (Gupito1508) | https://www.forexfactory.com/attachment/file/1433883?d=1400996668 |
| `Indicator-QSG-for-Lazy-Sonicers_2014.pdf` | https://www.forexfactory.com/attachment/file/1390785?d=1395390287 |
| `Sonic M.xlsx` (lot size calculator) | https://www.forexfactory.com/attachment/file/1146074?d=1362406978 |

**Thứ tự đọc đề xuất:** `5steps.pdf` → Post #1 → bản tổng kết (5377021) → Basics (6518525) →
`Sneak Into classic.pdf` → `Introduction_to_PVSRA.pdf` → post PVSRA gốc (7357031) → `PVSRA.pdf` →
Scout (7679382) → Trade Execution (7945770).

## Nguồn ngoài thread

| Nội dung | Link |
|---|---|
| Thread "Sonic R.evolution" (biến thể hanz1881) | https://www.forexfactory.com/thread/703694-sonic-revolution |
| Sonic R System (Full Version) — biến thể LCD/QQE/CCI | https://www.forexstrategiesresources.com/metatrader-trading-system-ii/286-sonic-r-system-full-version/ |
| Sonic R System TAH — biến thể SHI channel / fractal SL | https://www.forexstrategiesresources.com/trading-system-metatrader-4-iii/422-sonic-r-system-tah/ |
| Dragon and Trend (TradingView) | https://www.tradingview.com/script/DWh6PLdY-Dragon-and-Trend/ |
| PVA Candles and Volume (TradingView) — định nghĩa PVSRA chuẩn | https://www.tradingview.com/script/WfUJCZjK-PVA-Candles-and-Volume/ |
| Sonic R + EMA system by Dzung_Naga (TradingView) | https://www.tradingview.com/script/MXFwL1mz-Sonic-R-EMA-system-by-Dzung-Naga/ |

---

# PHẦN VI — TÀI LIỆU ĐÍNH KÈM POST #1 (đọc lượt 2)

Tải qua session browser (FF chặn tải trực tiếp, trả 403). Tổng: 5 PDF + 6 file `.mq4`.

| File | Trang | Tác giả | Vai trò |
|---|---|---|---|
| `5steps.pdf` | 5 | — | Sonic bảo đọc **trước tiên**, trước mọi thứ khác |
| `Sneak Into classic.pdf` | 9 | Gupito1508 | Định nghĩa Classic + quy trình vào lệnh |
| `Exploit the market price by Volume reading.pdf` | 12 | Gupito1508 | Vì sao volume phản ánh ý đồ MM; quy trình 5 bước |
| `Introduction_to_PVSRA.pdf` | 12 | Tymedu | Nhập môn PVSRA, các "hint" nhận diện MM |
| `PVSRA.pdf` | 130 | jackywang5 | Tuyển tập post PVSRA + ví dụ thực chiến |
| `TAH 03-17-2014 Revised.zip` | — | traderathome, qFish | **Source code 6 indicator** — TAH gọi User Notes trong code là manual chính thức |

## 20. Định nghĩa Classic (từ `Sneak Into Classic.pdf`)

**Bản chất:** *"Buy the first pull back from new high, sell the first pullback from new low."*

**Quy trình 5 chương:**

1. **Xác định điều kiện thị trường trên khung lớn.** Gupito khuyến nghị **H1** — *"because it shows
   the exact day to day price movement picture"*. Ba trạng thái: Trending / Reversal / (ranging).
   Với Reversal, bằng chứng cuối cùng phải là **"resetting wave"**: đảo từ tăng sang giảm thì
   **Lower High phải xuất hiện trên khung lớn**; đảo từ giảm sang tăng thì **Higher Low phải xuất hiện**.
2. **Chuyển xuống M15**, tìm Classic setup.
3. **Đặt pending order tại đường Level** (00/25/50/75), không vào bằng lệnh thị trường.
   Ví dụ nguyên văn: giá ask 171.38, muốn Long → đặt **buy limit** 171.28 (= level 171.25 + 3 pip spread).
4. **Fold / Hold / Add** — xem mục 23.
5. Không dùng thêm indicator nào ngoài bộ Sonic.

⚠️ **Đây là một khác biệt thật với bản tổng kết của TAH.** TAH mô tả **buy stop** đặt *ngoài* nến
đã đóng (đuổi theo xác nhận). Gupito dùng **buy limit** đặt *tại* mức Level (đón giá). Hai cơ chế
lệnh ngược nhau. Cả hai đều nằm trong tài liệu Post #1 dẫn.

**Bộ công cụ tối thiểu** (chương 3): Dragon + Trend, Level (00/25/50/75), Time zone (LO/NY/LC),
PVA Candle + PVA Volume, FFCAL. Và: *"you don't need indicator except Sonic."*
Bản rút gọn cho điện thoại: 3 EMA 34 (High/Low/Close) + EMA 89 (Close) + Volume.

## 21. Thuật toán PVA nguyên bản

Từ `Sonic_2 PVA Candles.mq4` và `Sonic_6 PVA Volumes.mq4` (© 2014 traderathome & qFish).
Ghi công: định nghĩa "climax" mượn từ `BetterVolume_v1.4`.

```mq4
// Rising
for(j = i+1; j <= i+10; j++) {av = av + Volume[j];}      // 10 nến TRƯỚC nến hiện tại
av = av / 10;
if (Volume[i] >= av * 1.5) {va = 2;}

// Climax
Range  = High[i] - Low[i];
Value2 = Volume[i] * Range;
for(n = i+1; n <= i+10; n++) {
   tempv2 = Volume[n] * (High[n] - Low[n]);
   if (tempv2 >= HiValue2) {HiValue2 = tempv2;}          // max của 10 nến TRƯỚC
}
if ((Value2 >= HiValue2) || (Volume[i] >= av * 2)) {va = 1;}   // climax đè lên rising
```

Bốn điểm cần chú ý khi tái hiện:

- Cửa sổ trung bình là **10 nến trước, không gồm nến hiện tại** (`i+1 … i+10`).
- Mốc so sánh `spread × volume` cũng là **max của 10 nến trước**, dùng `>=`.
- **Climax ghi đè Rising** (nhánh `va=1` được gán sau và loại trừ).
- Bull/bear phân theo `close` vs `open`; trường hợp `close == open` được xử lý riêng.

Định nghĩa volume, từ `Exploit the market price`: **"VOLUME IS THE COUNT OF TICK"** — mỗi lần giá
thay đổi thì đếm +1. *"If in a minute, there are 459 price changes, then the volume will show 459."*
→ Ngưỡng 150%/200% được hiệu chỉnh cho **đếm tick**, không phải cho khối lượng giao dịch thật.

## 22. Quy trình PVSRA 5 bước (từ `Exploit the market price`)

1. **Xác định ý đồ MM.** Giá xuống + đỏ/tím lặp lại → MM đang Long. Giá lên + xanh lá/xanh dương
   lặp lại → MM đang Short. Xét trên **H1 → H4 → D1**. *"How if there are no clue at all? STAY AWAY."*
2. **Lọc màn hình**: nếu MM long thì tạm bỏ qua xanh; nếu MM short thì tạm bỏ qua đỏ/tím.
3. **Tìm bằng chứng suy yếu**: MM long → đỏ/tím bắt đầu giảm dần. MM short → xanh bắt đầu giảm dần.
4. **Xuống M15**, tìm Classic setup, thực thi.
5. **Biết trước điểm thoát** cho cả lệnh xanh lẫn lệnh đỏ (xem mục 23).

**Ba "hint" nhận diện MM** (từ `Introduction_to_PVSRA`):

- **Volume tăng ở đỉnh hay ở đáy?** Lặp lại ở đỉnh → MM là bear. Lặp lại ở đáy → MM là bull.
- **Volume tăng trên hay dưới mốc S&R?** Tăng ngay dưới mốc → MM là bull. Tăng ngay trên → MM là bear.
- **Off-hours drift.** Giá trôi xuống sau khi London đóng **không phải** dấu hiệu bán tháo — đó là
  MM tạo giá tốt để đóng short/mở long. *"A lower drifting price is confirmation the MMs are bulls."*

## 23. Thoát lệnh và "Fold / Hold / Add"

**Thoát theo volume khung lớn** (H1/H4/D1) — đây là quy tắc exit chính, không phải TP cố định:

| Trạng thái | Tín hiệu thoát |
|---|---|
| Long đang lãi | xanh lá/xanh dương bắt đầu **giảm** trên khung lớn |
| Long đang lỗ | đỏ/tím bắt đầu **tăng** trên khung lớn |
| Short đang lãi | đỏ/tím bắt đầu **giảm** |
| Short đang lỗ | xanh bắt đầu **tăng** |

Ai không đủ kiên nhẫn thì dùng **RDH/RDL** làm mục tiêu cho lệnh đang lãi.

**Mẹo giữ khách quan:** tắt indicator Trade Levels và tắt đường trade level của MT4, rồi nhìn
lại chart như thể chưa có lệnh nào. *"PA and PVSRA never lie to us; the only one that deceives
us is our analysis."*

**Fold / Hold / Add** (chương 6 `Sneak Into Classic`):

- Lệnh Classic vào đúng vẫn có thể **tạm đỏ** — đừng hoảng.
- Nhìn chart tìm bằng chứng: MM thật sự đi ngược ta → **fold**. MM chỉ rung cây → cân nhắc **add**,
  nhưng chỉ khi mức Level đó **chưa có lệnh nào**.
- Nhồi vô nghĩa: 171.25 / 171.35 / 171.33 / 171.40 / 171.38 (dồn cục một chỗ).
  Nhồi hợp lý: long 171.25, giá bị dập về 170.90 → long thêm tại 171.00.
- **Định lượng: mỗi 100 pip chỉ có 4 cơ hội vào lệnh.**
- **Drawdown quá 150 pip = dấu hiệu sớm rằng bạn đã vào quá sớm.**

## 24. ⚠️ Mâu thuẫn lớn: có SL hay không?

Đây là mâu thuẫn nghiêm trọng nhất trong toàn bộ corpus, và nó nằm giữa hai tài liệu **cùng được
Post #1 dẫn**:

| Nguồn | Quy tắc |
|---|---|
| Bản tổng kết TAH 2012 (post 5377021) | SL bắt buộc: ngoài swing lớn gần nhất, **trần 100–120 pip** |
| Sonic M (post 6488843) | SL **không dưới 50 pip** |
| `Introduction_to_PVSRA.pdf` tr.11 | **"This system do not use an initial SL"** — thay bằng chia lot ÷10 và xây lệnh nhiều lần |

`PVSRA.pdf` cho thấy cộng đồng thực tế chạy **ba style song song**, mỗi style một hồ sơ rủi ro riêng
(nguyên văn của JRissa):

| Style | SL | Rủi ro | TP | RR |
|---|---|---|---|---|
| Classic Sonic R | swing high/low gần nhất | 50–100 pip | 50–100 pip | **~1:1** |
| Classic + PVSRA (early entry) | swing gần nhất | 20–50 pip | 80–150 pip | **~30/70** |
| Position building "MM way" | **không có SL ban đầu** | không định nghĩa được | — | — |

→ **"RR 3:1" không phải quy tắc của hệ thống.** Classic thuần chạy quanh **1:1**. Con số ~3:1 chỉ
xuất hiện ở style "Classic + PVSRA early entry", và đạt được bằng cách **thu hẹp rủi ro** (20–50 pip)
chứ không phải bằng cách kéo dài TP.

TAH tự cảnh báo về style thứ ba: *"I do not yet recommend anyone trade like this… you better demo
it… It is better to blow one or more demo accounts until you truly understand."*

## 25. RDH / RDL — định nghĩa chính xác

Từ User Notes của `Sonic_4 Access Panel.mq4`:

> * The RDH/RWH line is the computed **average range distance above the session Low**.
> * The RDL/RWL line is the computed **average range distance below the session high**.
> * The lines will move as new highs/lows are achieved during the session.

→ RDH/RDL **không phải** đỉnh/đáy của ngày. Chúng là **mức chiếu**: lấy biên độ trung bình ngày (ADR)
cộng lên từ đáy phiên, và trừ xuống từ đỉnh phiên. Chúng **di chuyển** khi phiên tạo đỉnh/đáy mới.
Cách tính ADR ngày cố ý **bỏ qua các phiên Chủ Nhật ngắn** của một số broker để không kéo trung bình
xuống; ADR tuần thì dùng công thức ATR chuẩn.

Ai muốn giới hạn phơi nhiễm với biến động thì bám RDH/RDL thay vì S&R xa.

## 26. Các dịch vụ khác của Access Panel

- **Level lines**: chia khoảng giữa hai số tròn thành **bốn phần** (00/25/50/75) — đúng thứ tự ưu tiên
  S&R mà PVSRA nêu.
- **Pivots**: Daily hoặc Fibonacci, kèm mid-pivot.
- **vLines**: Asian Open, **London Open, New York Open, London Close** (+ tuỳ chọn Frankfurt, Sydney).
  Code tự xử lý DST riêng cho từng thành phố, không hard-code offset.
- Average Range H/L cho cả ngày và tuần; Day Separators.

## 27. Trôi dạt của nguồn thứ cấp (đo được)

`marginatm.com/sonic-r` — một trong những nguồn tiếng Việt phổ biến nhất — cho thấy mức trôi dạt:

| Nội dung marginatm | Đối chiếu nguồn gốc |
|---|---|
| "EMA 34, 89, 200, **610**" | Gốc chỉ có 34 và 89. 200/610 là bổ sung của cộng đồng. |
| "dựa trên lý thuyết **Elliott Wave** — mỗi sóng lớn gồm 34 sóng chính và 89 sóng hồi" | **Sai.** Post #1 ghi rõ nguồn cảm hứng là **sách của Raghee Horner**; 34/89 là số Fibonacci. Không post gốc nào nhắc Elliott. |
| "chỉ báo do một trader **Singapore** phát hiện" | Quốc tịch không được xác minh; các nguồn ghi khác nhau Singapore/Myanmar. |

→ Khi gặp mâu thuẫn, luôn quay về Post #1 và các file đính kèm của nó.

---

*Báo cáo mang tính thông tin và tổng hợp tài liệu, không phải lời khuyên đầu tư.*
