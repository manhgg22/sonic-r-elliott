"""Phát hiện Sonic Classic WAVE theo pivot đã xác nhận, không look-ahead."""

from __future__ import annotations

import pandas as pd

from . import indicators as ind


WAVE_COLUMNS = [
    "wave_valid",
    "leg",
    "leg1_crossed_dragon",
    "wave_start_idx",
    "pivot_2_idx",
    "pivot_3_idx",
    "leg3_ready_at",
    "wave_id",
    "missed_preconfirmation",
]


def _is_more_extreme(new: dict, old: dict) -> bool:
    if new["kind"] == "high":
        return new["price"] > old["price"]
    return new["price"] < old["price"]


def detect_waves(
    df: pd.DataFrame,
    bands: pd.DataFrame,
    side: str,
    left: int = 3,
    right: int = 3,
) -> pd.DataFrame:
    """Trả trạng thái WAVE causal trên từng nến của khung entry.

    Pivot cùng loại được thay thế tại thời điểm pivot mới được xác nhận, thay vì
    bị sửa ngược lịch sử. Vì vậy kết quả tại nến ``i`` không phụ thuộc dữ liệu
    sau ``i``.
    """
    side = side.upper()
    if side not in {"LONG", "SHORT"}:
        raise ValueError("side phải là LONG hoặc SHORT")
    if left < 1 or right < 1:
        raise ValueError("pivot left/right phải >= 1")
    if not df.index.equals(bands.index):
        raise ValueError("df và bands phải có cùng index")

    required_df = {"high", "low", "close"}
    required_bands = {"ema_fast_high", "ema_fast_low"}
    missing_df = required_df.difference(df.columns)
    missing_bands = required_bands.difference(bands.columns)
    if missing_df:
        raise ValueError(f"WAVE thiếu cột OHLC: {sorted(missing_df)}")
    if missing_bands:
        raise ValueError(f"WAVE thiếu Dragon: {sorted(missing_bands)}")

    out = pd.DataFrame(index=df.index)
    out["wave_valid"] = False
    out["leg"] = 0
    out["leg1_crossed_dragon"] = False
    for column in WAVE_COLUMNS[3:7]:
        out[column] = pd.Series(pd.NA, index=df.index, dtype="Int64")
    out["wave_id"] = pd.Series(pd.NA, index=df.index, dtype="string")
    out["missed_preconfirmation"] = False

    raw = ind.zigzag_confirmed(df, left, right, clean=False)
    if raw.empty:
        return out

    events: dict[int, list[dict]] = {}
    for row in raw.to_dict("records"):
        events.setdefault(int(row["confirmed_at"]), []).append(row)

    visible: list[dict] = []
    wanted = ("low", "high", "low") if side == "LONG" else ("high", "low", "high")

    for i in range(len(df)):
        for pivot in events.get(i, []):
            if visible and visible[-1]["kind"] == pivot["kind"]:
                if _is_more_extreme(pivot, visible[-1]):
                    visible[-1] = pivot
            else:
                visible.append(pivot)

        if visible:
            if visible[-1]["kind"] == wanted[0]:
                out.iat[i, out.columns.get_loc("leg")] = 1
            elif len(visible) >= 2 and tuple(p["kind"] for p in visible[-2:]) == wanted[:2]:
                out.iat[i, out.columns.get_loc("leg")] = 2

        if len(visible) < 3:
            continue
        p1, p2, p3 = visible[-3:]
        if (p1["kind"], p2["kind"], p3["kind"]) != wanted:
            continue

        higher_or_lower = (
            p3["price"] > p1["price"]
            if side == "LONG"
            else p3["price"] < p1["price"]
        )
        if not higher_or_lower:
            continue

        start = int(p1["idx"])
        middle = int(p2["idx"])
        end = int(p3["idx"])
        if side == "LONG":
            starts_correct_side = (
                df["close"].iloc[start] < bands["ema_fast_low"].iloc[start]
            )
            crossed = starts_correct_side and (
                df["close"].iloc[middle] > bands["ema_fast_high"].iloc[middle]
            )
        else:
            starts_correct_side = (
                df["close"].iloc[start] > bands["ema_fast_high"].iloc[start]
            )
            crossed = starts_correct_side and (
                df["close"].iloc[middle] < bands["ema_fast_low"].iloc[middle]
            )
        if not starts_correct_side:
            continue

        out.iat[i, out.columns.get_loc("wave_valid")] = True
        out.iat[i, out.columns.get_loc("leg")] = 3
        out.iat[i, out.columns.get_loc("leg1_crossed_dragon")] = bool(crossed)
        out.iat[i, out.columns.get_loc("wave_start_idx")] = start
        out.iat[i, out.columns.get_loc("pivot_2_idx")] = middle
        out.iat[i, out.columns.get_loc("pivot_3_idx")] = end
        out.iat[i, out.columns.get_loc("leg3_ready_at")] = int(p3["confirmed_at"])
        out.iat[i, out.columns.get_loc("wave_id")] = (
            f"{side}:{start}:{middle}:{end}"
        )
        ready = int(p3["confirmed_at"])
        if side == "LONG":
            missed = (
                df["close"].iloc[end:ready]
                > bands["ema_fast_high"].iloc[end:ready]
            ).any()
        else:
            missed = (
                df["close"].iloc[end:ready]
                < bands["ema_fast_low"].iloc[end:ready]
            ).any()
        out.iat[
            i, out.columns.get_loc("missed_preconfirmation")
        ] = bool(missed)

    return out
