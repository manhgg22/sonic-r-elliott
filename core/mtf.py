"""
Multi-timeframe alignment.

ĐÂY LÀ MODULE NGUY HIỂM NHẤT CỦA CẢ PROJECT.

Vấn đề: ta ra quyết định trên M15, nhưng dùng thông tin từ H1/H4/D1.
Nếu ghép sai, nến M15 lúc 10:15 sẽ "nhìn thấy" nến H1 10:00-11:00 đã đóng
-> biết trước tương lai -> backtest đẹp giả -> mất tiền thật.

Quy tắc: một nến H1 mở lúc 10:00 chỉ được dùng từ 11:00 trở đi.
Cách làm: shift(1) trên khung lớn TRƯỚC khi reindex xuống khung nhỏ.
"""

import pandas as pd


def align_htf_to_ltf(
    htf_data: pd.DataFrame,
    ltf_index: pd.DatetimeIndex,
    shift_bars: int = 1,
) -> pd.DataFrame:
    """
    Ghép dữ liệu khung lớn xuống khung nhỏ, không look-ahead.

    Args:
        htf_data:   DataFrame khung lớn (H1/H4/D1), index là thời gian MỞ nến
        ltf_index:  index của khung nhỏ cần ghép vào
        shift_bars: số nến trễ. Mặc định 1 = chỉ dùng nến đã đóng hoàn toàn.

    Returns:
        DataFrame cùng index với ltf_index.
    """
    if htf_data.empty:
        return pd.DataFrame(index=ltf_index, columns=htf_data.columns)

    # Bước 1: trễ 1 nến -> giá trị tại nến N thực chất là của nến N-1
    lagged = htf_data.shift(shift_bars)

    # Bước 2: reindex bằng forward-fill.
    # Nến M15 lúc 10:15 sẽ lấy giá trị của hàng H1 gần nhất <= 10:15,
    # mà hàng đó đã bị shift -> chứa dữ liệu nến H1 trước đó. An toàn.
    aligned = lagged.reindex(ltf_index, method="ffill")

    return aligned


def verify_no_lookahead(
    htf_raw: pd.DataFrame,
    aligned: pd.DataFrame,
    col: str = "close",
    samples: int = 200,
) -> dict:
    """
    Kiểm tra tự động: giá trị đã ghép phải đúng bằng giá trị của nến
    khung lớn liền trước nến đang chạy tại thời điểm đó.

    Trả về dict báo cáo. violations phải bằng 0.
    """
    violations = 0
    checked = 0

    step = max(1, len(aligned) // samples)
    for ts in aligned.index[::step]:
        if pd.isna(aligned.loc[ts, col]):
            continue
        current_pos = htf_raw.index.searchsorted(ts, side="right") - 1
        if current_pos < 1:
            continue
        expected_val = htf_raw.iloc[current_pos - 1][col]
        aligned_val = aligned.loc[ts, col]
        checked += 1
        if not pd.isna(expected_val) and abs(aligned_val - expected_val) >= 1e-12:
            violations += 1

    return {
        "checked": checked,
        "violations": violations,
        "clean": violations == 0,
    }


def resample_ohlcv(df: pd.DataFrame, rule: str) -> pd.DataFrame:
    """Gộp nến nhỏ thành nến lớn (dùng khi chỉ tải được 1 khung)."""
    return df.resample(rule, label="left", closed="left").agg(
        {
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last",
            "volume": "sum",
        }
    ).dropna()
