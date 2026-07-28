# Tổng hợp toàn diện về Hệ thống giao dịch Sonic R (Sonic R System)

## TL;DR
- **Sonic R** là hệ thống giao dịch price-action do trader **sonicdeejay (Kyaw Trader / "Sonic")** khởi xướng trên ForexFactory (thread gốc "Sonic R. System" #114792; thread tiền thân "Sonic System!!" #83521 mở tháng 4/2008); cốt lõi gồm **Dragon (dải 3 đường EMA 34 áp cho High/Low/Close — chính là "Wave" của Raghee Horner được đổi tên)**, **Trend line (EMA 89 Close)** và phân tích **PVA/PVSRA (Price-Volume-S&R Analysis)** — nguồn gốc và tài liệu đầy đủ vẫn truy cập được miễn phí.
- Tài liệu và công cụ dồi dào cả tiếng Anh (thread FF, forexstrategiesresources, LiteFinance, các PDF "Secret of Sonic R", "Sonic R Manual") lẫn tiếng Việt (forexvietnam.com.vn, traderviet, marginatm, các bản dịch trên Scribd, video YouTube); bộ chỉ báo MT4/MT5 (.ex4/.mq4/.tpl) và nhiều script TradingView (Pine Script) có sẵn.
- **Cảnh báo:** kết luận phổ biến của cộng đồng là hệ thống chỉ hiệu quả trong thị trường có xu hướng (phiên Âu/Mỹ, cặp biến động mạnh như EUR/USD, GBP/USD) và "bị giết" (get murdered) trong sideways; các bản chỉ báo tải trôi nổi (.ex4 không rõ nguồn) và các EA/script "invite-only" hứa "lợi nhuận 100%/tháng" cần được xem là quảng cáo chưa kiểm chứng, tiềm ẩn rủi ro.

## Key Findings

1. **Nguồn gốc & tác giả:** Sonicdeejay (nick "Sonic", tên thường ghi là **Kyaw Trader** — xác nhận qua tiêu đề blog chính thức "Sonic R System: Sonic R. System - Kyaw Trader Sonic Deejay"; quốc tịch được ghi khác nhau là Singapore/Myanmar tùy nguồn) bắt đầu giao dịch từ 2008. Trái tim của hệ thống là **"Wave" của Raghee Horner được đổi tên thành "Dragon"** — gồm 3 đường EMA chu kỳ 34 (High, Low, Close) dựa trên dãy Fibonacci. Đồng tác giả quan trọng là **traderathome (TAH)**, người code phần lớn bộ chỉ báo và template, và duy trì thread.
2. **Ba giai đoạn phương pháp:** Classic (cốt lõi), Scout (giới thiệu 2012), PVSRA (giới thiệu 2013 — phương pháp phân tích, không phải phương pháp vào lệnh).
3. **Cấu trúc chỉ báo:** Dragon = 3 đường EMA 34 (High, Low, Close) tạo thành "đường hầm"; Trend = EMA 89 Close; nhiều biến thể thêm EMA 200 và các EMA dài (170, 510, 630) — xuất phát từ quy đổi khung thời gian trên M1 (M5-on-M1 = 34×5 = 170 EMA; M15-on-M1 = 34×3×5 = 510 EMA). PVA Candles + PVA Volumes tô màu nến/volume theo mức "rising"/"climax".
4. **Nguồn tiếng Việt phong phú** nhưng chất lượng không đồng đều — nhiều bài mang tính SEO/giới thiệu sàn.
5. **Quan điểm phản biện rõ ràng:** ngay chính tác giả thừa nhận "It is not the magic bullet, nothing is"; cộng đồng cảnh báo thua lỗ nặng trong thị trường ranging.

## Details

### 1. TÀI LIỆU GỐC VÀ NGUỒN CHÍNH THỐNG (độ tin cậy cao)

**Thread gốc ForexFactory:**
- **"Sonic R. System"** — https://www.forexfactory.com/thread/114792-sonic-r-system — thread chính, do sonicdeejay khởi xướng (profile: Commercial Member, Joined Mar 2008, ~9.229 bài). Thread cực lớn: khoảng **4.123–4.124 trang** (ước tính hơn 200.000 bài), trải dài từ ~2008 đến 2019+. Vẫn truy cập đầy đủ, đã được FF chuyển vào mục "Commercial Content" dù tác giả khẳng định phi thương mại. Post #1 chứa toàn bộ link tài liệu, manual, PDF và file tải miễn phí.
- **"Sonic System!!"** — https://www.forexfactory.com/thread/83521-sonic-system — thread tiền thân, mở **tháng 4/2008** (có các mốc "25 Apr '08", "26 Apr '08"), thời kỳ "Sonic Striker".
- Đồng tác giả **traderathome (TAH)** (Joined Mar 2008, ~22.082 bài) — người viết user notes và code chỉ báo.

**Trích Post #1 (nguyên văn):** "So, here is a simple and profitable 15M swing system inspired from Raghee's book… It is not the magic bullet. Nothing is. It is an elegantly simple and effective EMA based system. I'd like to call it the Sonic R. System." và "The Classic setup/trade is the core of the Sonic R. System. I introduced the Scout trade in 2012. The analysis we call PVSRA (for Price, Volume, S&R Analysis) came in 2013…" — ký tên "Sonicdeejay (Sonic) & Traderathome (TAH)". (Theo trang phân tích 3-candle-reversal.com: "in 2008, a young man who calls himself the Sonicdeejay turned up on trading forums to publish his Sonic R System. At the heart of his trading system was Raghee Horner's Wave which he renamed the Dragon.")

**Website & blog chính thống/cộng đồng công nhận:**
- **www.sonicrsystem.com** (website chính thức, được dẫn từ thread) — cần kiểm tra còn hoạt động.
- **Facebook group chính thức:** https://www.facebook.com/groups/sonicrsystem
- **Blog tổng hợp:** http://sonicr999.blogspot.com/2014/08/sonic-r-system.html — tổng hợp link tải template 2013/2014, khuyến nghị quản trị rủi ro (không trade phiên Á, không quá 5 lệnh/tuần, SL rộng — ví dụ tới 100 pip cho EURUSD).
- **forexstrategiesresources.com:** trang "Sonic R System (full Version)" https://www.forexstrategiesresources.com/metatrader-trading-system-ii/286-sonic-r-system-full-version/ và "Sonic R System TAH" https://www.forexstrategiesresources.com/trading-system-metatrader-4-iii/422-sonic-r-system-tah/ — có file tải template và PDF.
- **LiteFinance** (bản tiếng Anh, sàn có uy tín): https://www.litefinance.org/blog/for-beginners/trading-strategies/sonic-r-system/ — lưu ý rõ điều kiện thị trường: "The strategy works best during American and European sessions when the market is highly volatile. Recommended instruments are EUR/USD and GBP/USD… The potential profit for H4 timeframe can reach 300 pips per trade."
- **Medium:** "The Sonic R. System Basics" — https://medium.com/@bigballznzz/the-sonic-r-system-basics-57c11e8abb54

**PDF/Ebook (tiếng Anh):**
- "Sonic R." (manual gốc) — bản host trên jimcontent: https://s2e2ea4a9b3965dd1.jimcontent.com/download/version/1358943147/module/6364737080/name/Sonic%20R.pdf
- "Secret of Sonic R." — giải thích vì sao setup Classic sinh lời (dùng nến Hammer/Engulfing khung D1/H4). Bản trên Scribd: https://www.scribd.com/doc/260832961/Secret-of-Sonic-R
- "Sonic R Manual" — https://www.scribd.com/document/220403658/Sonic-R-Manual
- ⚠️ Các bản PDF trên Scribd/pdfcoffee là bản tải lại của cộng đồng, không phải trang chính thức — nội dung nhìn chung trung thực với bản gốc nhưng nên đối chiếu với Post #1 của thread.

### 2. NGUỒN TIẾNG VIỆT

**Bài viết/hướng dẫn (độ tin cậy trung bình — nhiều trang thiên về SEO/giới thiệu sàn):**
- **forexvietnam.com.vn** — bộ 2 bài dịch sát bản gốc: "Hệ thống Sonic R" https://forexvietnam.com.vn/he-thong-sonic-r-cach-su-dung-sonic-r-trong-giao-dich-forex-bid151.html và "Thiết lập cổ điển" https://forexvietnam.com.vn/thiet-lap-co-dien-cua-he-thong-sonic-r-trong-giao-dich-forex-bid152.html — đây là nguồn tiếng Việt tốt nhất, dịch trực tiếp manual.
- **marginatm.com/sonic-r** — hướng dẫn cài đặt TradingView + giải thích EMA 34/89/200, lưu ý không dùng khi sideways.
- **traderviet** (cộng đồng trader lớn nhất VN): bài tổng hợp "5 hệ thống hot nhất Forex Factory" https://traderviet.tv/t/tong-hop-5-he-thong-giao-dich-hot-nhat-tren-forex-factory.115785/ ; thread thảo luận "Chỉ báo hot!!!" https://traderviet.net/t/chi-bao-hot.56895/ (có ý kiến phản biện thẳng thắn).
- Các trang khác: forex.com.vn, goldenfund.vn (giải thích khái niệm "Value Zone": vùng tạo giữa EMA 34/89/200 — "We only look for entry when price retest this VALUE ZONE"), dautu.vdg.vn, tamnhindautu.org, topsanfx.com (kết hợp PVSRA), giavang.com, hocviendautu.edu.vn, giaodichtaichinh.com, sanuytin.com, sanforex.club.

**Ebook/tài liệu dịch tiếng Việt:**
- "Sonic R Vietsub" (PDF) — https://www.scribd.com/document/896023615/Sonic-R-Vietsub
- "Cách vào lệnh Sonic R" — https://www.scribd.com/document/739887969/Cach-vao-lệnh-Sonic-R
- "(Trading System) Hệ Thống Sonic R - Sự Đơn Giản Chính Là Sự Tinh Vi Tột Cùng" (Tầm Nhìn Đầu Tư) trên Scribd.
- Studocu có bản "Sneak into Classic" (tiếng Anh, chi tiết về Dragon/Trend/Level/Time zone/PVA): https://www.studocu.vn/vn/document/truong-dai-hoc-su-pham-ha-noi-2/ngu-am-am-vi-hoc/sneak-into-classic/72083556

**YouTube tiếng Việt:**
- "Hướng dẫn chi tiết Hệ thống Sonic R | Học Đầu Tư Forex Cùng Lucy" — https://www.youtube.com/watch?v=hwbi_-3DFys
- "Hướng Dẫn Sử Dụng Sonic R Trade thuận xu hướng, kết hợp Stoch RSI Bollinger Bands" — https://www.youtube.com/watch?v=3dH14nhVjO0

### 3. BỘ CHỈ BÁO VÀ FILE CÀI ĐẶT

**MT4/MT5 (.ex4/.mq4/.tpl):**
- Bản chính thống nhất là **"2014 Release" của TAH** (template + indicators: Filled Dragon, PVA Candles, PVA Volumes, Control Panel, FFCAL Panel, Trade Levels, TzPivots) — tải từ Post #1 thread FF và bản mirror trên forexstrategiesresources.com.
- Bộ chỉ báo VSA: "SonicR VSA (Black)" trên 4xone https://4xone.com/sonicr-vsa-black-indicator/ , mt4collection https://www.mt4collection.com/collection/sonicr-vsa-black/ , tradingfinder, forexdl.
- Mã nguồn Dragon-Trend MT4 (traderathome & qFish 2014) được lưu tại pudn.com.
- PVA cho MT5: MQL5 Code Base #22109 (Scriptor) https://www.mql5.com/en/code/22109
- **Hướng dẫn cài đặt:** copy .ex4/.mq4 vào MQL4/Indicators, .tpl vào Templates, restart MT4, load template.

**TradingView (Pine Script):**
- **"Sonic R"** — VuTienTurtleTrader — https://www.tradingview.com/script/tjpLYoFr-Sonic-R/ — mã nguồn mở; ~7.797 views, 117 boosts. Mô tả: "Indicator base on SonicR System! Enjoy!"
- **"Dragon and Trend"** — ForexPipCheats — https://www.tradingview.com/script/DWh6PLdY-Dragon-and-Trend/ — closed-source (dùng free); ~9.310 views, 252 boosts. Credit traderathome & Fish.
- **"PVA Candles and Volume"** — ForexPipCheats (& iceicebaby_) — https://www.tradingview.com/script/WfUJCZjK-PVA-Candles-and-Volume/ — closed-source (dùng free); phổ biến nhất ~28.566 views, ~1.000 boosts, 1.414 comments. Credit traderathome (TAH), qFish. Đây cũng là nguồn định nghĩa chuẩn PVSRA: **"Climax"** = nến có volume ≥ 200% trung bình 10 nến gần nhất (và tích spread×volume ≥ mức cao nhất 10 nến gần nhất); **"Volume Rising Above Average"** = volume ≥ 150% trung bình 10 nến gần nhất.
- **"SonicR PVA Volumes"** — crypteisfuture — https://www.tradingview.com/script/fFxNaJ1l-SonicR-PVA-Volumes/ — mã nguồn mở; ~5.672 views.
- **"Sonic R + EMA system by Dzung_Naga"** — https://www.tradingview.com/script/MXFwL1mz-Sonic-R-EMA-system-by-Dzung-Naga/ — mã nguồn mở; thêm EMA 200/257/458/630. Và bản "Sonic R by VuTien - edited by Dzung_Naga" https://www.tradingview.com/script/gWvEoAO5-Sonic-R-by-VuTien-edited-by-Dzung-Naga/
- **"Sonic R System Final"** — VuTienTurtleTrader — https://vn.tradingview.com/script/ckfLxZOW/ — **invite-only (trả phí)**, ~15.095 views, 555 boosts. ⚠️ Mô tả chứa quảng cáo chưa kiểm chứng "monthly profit up to 100%", "tested for 8 years", "RR 3/1".

### 4. CÔNG CỤ BỔ TRỢ THƯỜNG KẾT HỢP

- **Bộ lọc tín hiệu:** MACD, Stochastic, QQE, CCI (bản đầu dùng CCI/QQE, sau này TAH coi QQE/CCI không cần thiết), RSI.
- **Volume/VSA:** NVO, PVA/PVSRA Volumes, SonicR VSA — cốt lõi để đọc "ý đồ MM".
- **S&R & Pivot:** SonicR TzPivots, Pivot Point Zones (PPZ), whole numbers (mức 00/25/50/75), historic S&R để đặt TP.
- **Session/Time:** Time zone lines (London Open, NY Open, London Close), FFCAL Panel (lịch tin tức).
- **Nến/Price Action:** pin bar, hammer, engulfing (khung H4/D1 để xác nhận setup M15).
- **EA:** một số EA "SonicStriker_EA" và "Sonic R Final EA MT5" (bán trên eafxstore/groupbuy) — ⚠️ các số liệu "tổng lợi nhuận $472.000, drawdown 5.92%" là quảng cáo của người bán, chưa kiểm chứng độc lập.
- **Dashboard/scanner đa cặp/đa khung:** Control Panel/Chart Panel của TAH hiển thị thông tin đa khung; chưa có scanner đa cặp chính thống.

### 5. NỘI DUNG PHƯƠNG PHÁP

**Quy tắc cơ bản (Classic setup):**
- Giao dịch chính trên **M15** (đôi khi M5 đầu phiên London); dùng H4/D1 để tìm nến hỗ trợ (hammer/engulfing/pin bar).
- **WAVE:** Long = sóng L-H-HL bắt đầu dưới Dragon rồi chuyển sang HH; Short = H-L-LH bắt đầu trên Dragon rồi chuyển sang LL. Tốt nhất chân sóng #1 cắt qua Dragon.
- **Dragon (EMA 34):** phải dốc lên và giá nằm trên cho Long (ngược lại cho Short) — chọn điểm vào lệnh.
- **Trend (EMA 89):** xác nhận hướng — giá trên EMA 89 cho Long.
- **Value Zone:** vùng giữa EMA 34/89/200 khi 3 đường xếp thứ tự đúng — nhiều biến thể chỉ vào lệnh khi giá hồi (retest) về vùng này.
- **Entry:** chờ nến chân sóng #3 thoát khỏi Dragon, đặt entry vài pip ngoài (ví dụ high nến + 5 pip). Re-entry khi giá phá đỉnh/đáy gần nhất.
- **Stop Loss:** dựa vào S&R (không dựa vào cảm xúc); SL đủ rộng để giá "thở" — khuyến nghị tới 100 pip cho EURUSD, ≥80 pip cho cặp có JPY; một số dùng SMA 50/89 làm SL.
- **Take Profit:** dùng historic S&R, có thể giới hạn trong biên độ ngày (RDH/RDL) để vào/ra nhanh; RR thường 3:1.
- **Quy tắc quản trị:** chỉ trade phiên Âu/Mỹ (tránh phiên Á), đóng lệnh trước tin lớn, không quá 5 lệnh/tuần, không nhồi lệnh thua.

**Đa khung thời gian:** D1/H4 xác định bias & S&R → M15 tìm setup → (M5 tinh chỉnh entry).

**PVSRA:** dùng màu nến/volume (climax ≥200% trung bình 10 nến; rising ≥150%) để phán đoán MM là bull/bear và đang "gom hàng" hay "chạy lợi nhuận".

### Đánh giá & phản biện (quan trọng)
- Tác giả tự nhận: "It is not the magic bullet, nothing is."
- Cảnh báo kinh điển trong thread: "Looks good when the market is trending, but in a ranging market you will get murdered even if you are entering a few pips above/below the set up bar."
- LiteFinance nhấn mạnh hệ thống chỉ tối ưu trong phiên Âu/Mỹ với các cặp biến động mạnh (EUR/USD, GBP/USD, biến động 100–200 pip/ngày) — hàm ý kém hiệu quả ở điều kiện thị trường khác.
- Bản chất là hệ thống EMA + price action → **lag và thất bại trong sideways**, giống mọi hệ thống MA.
- Đường cong học tập dốc: có thành viên nói "It took 7 to 8 yrs to understand this system."
- Trên traderviet có ý kiến hoài nghi: "Mforex nó lấy ra mấy cái này lừa người thôi… trade theo mấy cái indi này có ngày xấp mặt."
- Không có bằng chứng backtest độc lập, được kiểm toán nào chứng minh lợi nhuận dài hạn; các con số lợi nhuận đều là ví dụ chọn lọc hoặc quảng cáo.

## Recommendations

1. **Bắt đầu từ nguồn gốc miễn phí:** Đọc Post #1 thread FF #114792 + "Secret of Sonic R." + manual, và bản dịch forexvietnam.com.vn. Tránh trả tiền cho khóa học/EA/script trước khi hiểu bản gốc.
2. **Cài chỉ báo an toàn:** Ưu tiên script mã nguồn mở trên TradingView (VuTienTurtleTrader, crypteisfuture, Dzung_Naga) hoặc bộ "2014 Release" của TAH tải trực tiếp từ thread FF. **Không tải file .ex4 trôi nổi** — chỉ dùng .mq4 đọc được mã hoặc nguồn uy tín; quét virus; test trên tài khoản demo/máy ảo.
3. **Backtest & demo trước:** Chạy tối thiểu 3–6 tháng demo trên M15, ghi nhật ký, đo win-rate & RR thực tế. Ngưỡng ra quyết định: nếu win-rate < 45% với RR 2:1 hoặc drawdown vượt ngưỡng chịu đựng, dừng lại và điều chỉnh.
4. **Chỉ giao dịch khi có xu hướng:** thêm bộ lọc ADX/Bollinger để tránh sideways; ưu tiên phiên Âu/Mỹ và cặp EUR/USD, GBP/USD; tránh tin lớn.
5. **Cảnh giác marketing:** với mọi tuyên bố "100%/tháng", "tested 8 years", EA "$472k profit" — coi là quảng cáo cho tới khi có sao kê được kiểm toán (Myfxbook verified).

## Caveats
- Tên thật/tổ chức của sonicdeejay không được xác minh chính thức (thường ghi Kyaw Trader; quốc tịch Singapore/Myanmar tùy nguồn).
- Ngày mở chính xác của thread #114792 không xác minh được tuyệt đối (suy luận ~2008; chỉ thread #83521 chắc chắn 4/2008).
- www.sonicrsystem.com và một số blog cũ có thể đã ngừng hoạt động — cần kiểm tra khi truy cập.
- Các link Scribd/pdfcoffee/jimcontent là bản tải lại của cộng đồng, không phải trang chính thức; một số nền tảng (Scribd) có thể yêu cầu đăng nhập/trả phí để tải.
- Số liệu views/boosts của TradingView tính đến thời điểm truy cập (7/2026) và sẽ thay đổi.
- Báo cáo này mang tính thông tin, không phải lời khuyên đầu tư; forex có rủi ro mất vốn cao.