"""时间码工具：毫秒 <-> 00:00:00 互转。"""
from __future__ import annotations

import re


def ms_to_tc(ms: int) -> str:
    """毫秒转 00:00:00 时间码（给界面和亮点卡用）。"""
    ms = max(0, int(ms))
    total = ms // 1000
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def tc_to_ms(value: str | int | float | None) -> int:
    """把模型返回的时间（秒、毫秒或 00:00:10）统一成毫秒。"""
    if value is None:
        return 0
    if isinstance(value, (int, float)):
        # 大于 3 小时的数字更可能已经是毫秒
        if value > 3 * 3600:
            return int(value)
        return int(float(value) * 1000)
    text = str(value).strip()
    if not text:
        return 0
    if re.fullmatch(r"\d+(\.\d+)?", text):
        return tc_to_ms(float(text))
    parts = re.split(r"[:：]", text)
    try:
        parts = [float(p) for p in parts]
    except ValueError:
        return 0
    if len(parts) == 3:
        h, m, s = parts
        return int((h * 3600 + m * 60 + s) * 1000)
    if len(parts) == 2:
        m, s = parts
        return int((m * 60 + s) * 1000)
    return 0
