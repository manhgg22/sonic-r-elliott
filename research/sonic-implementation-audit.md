# Sonic R — source audit and implementation decisions

Ngày đối chiếu: 2026-07-28.

Tài liệu đầu vào: [`research/sonic.md`](./sonic.md).

## Thứ tự tin cậy của nguồn

1. [Post #1 — Sonic R. System](https://www.forexfactory.com/thread/114792-sonic-r-system)
   của Sonicdeejay/Traderathome: nguồn chuẩn cho lịch sử, Classic, Scout, PVSRA,
   quản trị và bộ indicator 2014.
2. Các post đầu của chính Sonic trong cùng thread: nguồn chuẩn cho session,
   slope, multi-timeframe, entry-stop và S&R.
3. [Dragon and Trend](https://www.tradingview.com/script/DWh6PLdY-Dragon-and-Trend/)
   và [PVA Candles and Volume](https://www.tradingview.com/script/WfUJCZjK-PVA-Candles-and-Volume/):
   dùng để đối chiếu công thức indicator.
4. [PVA MQL5 source](https://www.mql5.com/en/code/22109) và các Pine Script
   open-source: dùng để kiểm tra cách biểu diễn, không thay thế quy tắc gốc.
5. Nguồn dịch, blog, video và bài của broker: chỉ dùng để tìm đầu mối; mọi quy
   tắc đều phải quay lại đối chiếu nhóm 1–4.

## Checklist đầy đủ và quyết định

| Hạng mục trong nghiên cứu | Quyết định | Lý do |
|---|---|---|
| Dragon EMA34 High/Close/Low | Áp dụng bắt buộc | Đây là lõi gốc; đã có trong `sonic_r_bands`. Trend chỉ đạt khi giá ra khỏi Dragon đúng hướng và toàn Dragon nằm đúng phía EMA89. |
| Trend EMA89 Close | Áp dụng bắt buộc | Nguồn Dragon/Trend xác nhận 34/89 là hai chu kỳ chuẩn. |
| EMA200 | Chỉ làm context | Không thuộc Classic nguyên bản; là biến thể Value Zone. Hiển thị `ema200_aligned` nhưng không làm mất tín hiệu Classic. |
| EMA170/510/630 | Không áp dụng | Đây là quy đổi M5/M15 lên chart M1. Project dùng dữ liệu native M15/H1 nên thêm lại sẽ trùng thông tin và tăng lag. |
| Wave L-H-HL / H-L-LH | Áp dụng bằng Dow pivots xác nhận | HH/HL và LL/LH là biểu diễn số học kiểm thử được; pivot có độ trễ xác nhận để chống look-ahead. |
| Classic setup | Chọn làm setup duy nhất để tự động hóa | Post #1 gọi Classic là core. Quy tắc rõ hơn Scout và phù hợp scanner/paper engine. |
| Scout | Không tự động hóa | Scout có thể xuất hiện trước/trong Classic và phụ thuộc PVSRA/discretion; tự động hóa dễ biến thành nhồi lệnh. |
| PVSRA | Áp dụng dưới dạng context | Post #1 và TradingView đều nói PVSRA là analysis, không phải entry method. Hệ thống chỉ phân loại volume, không suy diễn chắc chắn “MM đang gom hàng”. |
| PVA Rising | Áp dụng đúng công thức | `volume >= 150%` trung bình 10 nến trước. Dùng `shift(1)` để nến hiện tại không tự tham gia benchmark. |
| PVA Climax | Áp dụng đúng công thức | `volume >= 200%` trung bình 10 nến trước hoặc `spread × volume` đạt cực trị so với 10 nến trước. |
| M15 execution | Giữ nguyên live scanner | Đây là timeframe Classic gốc. |
| H1 confirmation | Áp dụng live | Scanner dùng H1 đã đóng, align sang M15 với shift chống look-ahead. |
| D1/H4 bias | Giữ trong research/backtest pipeline | Pipeline `Config` đã hỗ trợ D1/H4/H1. Không ép live scanner tải thêm D1/H4 cho toàn bộ perpetual universe vì làm tăng mạnh request/độ trễ; cần triển khai cache theo universe trước. |
| M5 fine-entry | Không áp dụng | Là tùy chọn đầu phiên, làm tăng nhiễu và chi phí dữ liệu; M15 pending-stop đã giải quyết phần lớn nhu cầu không đuổi giá. |
| Dragon slope | Áp dụng | Chính Sonic nêu góc 1–2h/4–5h và tránh 3h. Code dùng dấu slope chuẩn hóa thay vì “góc nhìn” phụ thuộc tỷ lệ chart. |
| Sideways filter ADX | Áp dụng | Có thể đo, ablation và backtest. Ngưỡng live mặc định 20, kết hợp separation và slope. |
| Bollinger sideways filter | Không chọn | Trùng mục tiêu đo co hẹp volatility với ATR/separation; thêm đồng thời dễ over-filter. Chỉ nên đưa vào sweep độc lập nếu dữ liệu out-of-sample chứng minh tốt hơn ADX. |
| EMA separation / ATR | Áp dụng | Đo Dragon–Trend đã tách đủ xa chưa; scale-invariant giữa BTC và altcoin. |
| Phiên Âu/Mỹ | Áp dụng | Chính Sonic nêu 01–04 và 07–11 giờ New York. Dùng `America/New_York` để tự xử lý DST và loại cuối tuần. |
| Chỉ nến đã đóng | Áp dụng bắt buộc | Chống repaint và đúng chỉ dẫn “wait till break-through candle close”. |
| Entry vài pip ngoài nến | Áp dụng bằng pending stop | Crypto không có “pip” thống nhất, nên buffer dùng 0.05 ATR. Setup được `ARMED`, chỉ `FILL` khi một trong 4 nến M15 kế tiếp vượt trigger; sau đó tự `EXPIRED` để không khớp một luận điểm đã cũ. |
| Backtest/live entry parity | Áp dụng | Nhánh Pure Sonic không còn khớp tại close của chính nến tín hiệu; backtest chờ stop trigger từ nến kế tiếp và ưu tiên SL nếu cùng nến fill có biên độ mơ hồ. |
| Không chase breakout | Áp dụng | Pending trade không được ghi OPEN tại giá close của nến signal. |
| Stop theo S&R | Áp dụng | SL lấy swing entry + biên ATR và phía ngoài Value Zone; không dùng khoảng tiền cảm tính. |
| SL 80/100 pip | Không hard-code | Con số dành cho cặp Forex, không chuyển trực tiếp sang perpetual crypto. ATR là đơn vị phù hợp đa tài sản. |
| TP historic S&R | Có trong backtest `sr_level`; live giữ fallback R/Fib | S&R tự động cần đủ pivot phía trước entry. Khi thiếu mức hợp lệ, 1.5R/3R rõ ràng và kiểm thử được an toàn hơn mục tiêu tùy tiện. |
| RDH/RDL | Chưa làm gate | Cần daily-range service và timezone thống nhất. Không giả lập bằng rolling high/low vì dễ sai ngày giao dịch. |
| RR 3:1 | Áp dụng cho TP2 fallback | Phù hợp tài liệu; TP1 1.5R để giảm rủi ro, TP2 3R, runner 20% theo Dragon H1. |
| Không quá 5 lệnh/tuần | Áp dụng guardrail | `SONIC_MAX_TRADES_PER_WEEK`, mặc định 5. |
| Risk mỗi lệnh / toàn danh mục | Áp dụng guardrail | Mặc định 0,5% mỗi lệnh và tối đa 2% risk cam kết. Dashboard lấy trực tiếp từ engine; không hard-code trên FE. |
| Không nhồi lệnh thua | Áp dụng | Mỗi symbol chỉ có một trạng thái PENDING/OPEN; Scout/add-on không được tự động mở. |
| Đóng/tránh trước tin lớn | Chưa tự động | Project chưa có economic-calendar feed đáng tin cậy và crypto có sự kiện khác Forex. Không nên tạo trạng thái “an toàn” giả. Cần tích hợp feed có timezone/impact và test riêng. |
| Whole numbers 00/25/50/75 | Chỉ context nghiên cứu | Quy mô giá crypto rất khác nhau; cần tick-size-aware level service trước khi dùng. |
| TzPivots / PPZ | Không tải indicator ngoài | Code nội bộ dùng pivot xác nhận; tránh `.ex4` đóng mã và supply-chain risk. |
| Hammer / engulfing / pin bar | Áp dụng | Entry PA hiện dùng engulfing/pin bar; BOS có trong research pipeline. |
| MACD/Stochastic | Không thêm vào live | Có ở phiên bản sớm, nhưng Post #1 hiện tại cảnh báo chart nhiều indicator tạo tín hiệu trễ. Slope/ADX đã giải quyết mục tiêu lọc hướng. |
| QQE/CCI/RSI | Không thêm | TAH về sau coi QQE/CCI không cần thiết; thêm nhiều oscillator gây trùng tín hiệu momentum. |
| NVO/VSA | Không thêm ngoài PVA | PVA đã là volume classifier chuẩn và minh bạch; không cần indicator đóng mã. |
| FFCAL/news panel | Hoãn có chủ đích | Thiếu feed lịch tin chính thức trong project; xem mục news guard. |
| Control Panel đa cặp/khung | Đã áp dụng | Scanner + dashboard realtime thực hiện vai trò này bằng code nội bộ. |
| EA/auto execution | Loại bỏ | Hệ thống chỉ paper; không có API key và không gửi lệnh thật. |
| File `.ex4` trôi nổi | Loại bỏ | Không cần binary ngoài; toàn bộ logic quan trọng là source code có test. |
| Pine open-source | Chỉ đối chiếu | Không copy code; project có implementation Python/React riêng và Pine nội bộ. |
| Script invite-only/100% tháng | Loại bỏ | Không có bằng chứng kiểm toán; trái với lời tác giả “not the magic bullet”. |
| Backtest 3–6 tháng/demo | Áp dụng theo hướng nghiêm ngặt hơn | Project có backtest, paper engine, costs, MFE/MAE, Wilson interval và regime analysis. Không tự tuyên bố edge khi mẫu chưa đủ. |
| Win rate 45% / RR 2:1 | Dùng làm cảnh báo, không tối ưu mù | Ngưỡng từ báo cáo thứ cấp. Quyết định phải dựa expectancy sau phí và confidence interval, không chỉ win rate. |
| EUR/USD, GBP/USD | Không áp dụng trực tiếp | Runtime hiện là OKX crypto perpetual. Quy tắc được chuyển sang scale-invariant ATR/ADX; không giả định hành vi Forex giống crypto. |
| Nguồn Việt/blog/video/Scribd | Đã duyệt nhưng không dùng làm chuẩn cuối | Có ích cho diễn giải, nhưng nguồn gốc/công thức được khóa theo ForexFactory và source indicator kiểm tra được. |

## Kiến trúc entry sau tối ưu

```text
Nến M15 đóng
  → Dragon/Trend đúng hướng
  → ADX + separation + slope xác nhận trending
  → đang trong phiên Âu/Mỹ
  → breakout + Dow + Value Zone + PA
  → ARMED tại high/low nến signal ± 0.05 ATR
  → một trong 4 nến M15 kế tiếp chạm trigger mới FILL, quá hạn thì EXPIRED
  → SL theo swing/S&R + ATR
  → TP1 50%, TP2 30%, runner 20% theo Dragon H1
```

PVA state, EMA200 và volume ratio được ghi cùng setup để người dùng đọc bối cảnh,
nhưng không tự biến thành lệnh.

## Những việc chỉ nên làm khi có dữ liệu bổ sung

1. News guard: cần calendar feed có impact, asset mapping và timezone.
2. RDH/RDL: cần định nghĩa ngày giao dịch thống nhất cho crypto.
3. Whole-number/PPZ: cần chuẩn hóa theo tick size và volatility từng instrument.
4. Live D1/H4: cần cache/batch fetch để không làm scanner toàn universe quá chậm.
5. Bollinger filter: chỉ thêm như một nhánh ablation, không chạy đồng thời mặc định
   với ADX/separation.

Không mục nào ở trên được coi là “đã tối ưu lợi nhuận” nếu chưa qua out-of-sample,
walk-forward và paper sample đủ lớn.
