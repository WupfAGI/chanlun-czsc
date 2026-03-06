"""
czsc 封装层
对单只股票运行缠论分析，输出结构化结果和 Markdown 报告
"""
from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from typing import List, Optional

from czsc import CZSC, RawBar
from czsc.utils.sig import get_zs_seq


@dataclass
class AnalysisResult:
    """单股缠论分析结果"""
    code: str
    freq: str
    as_of: datetime.datetime

    # 笔
    bi_count: int = 0                  # 总笔数
    last_bi_direction: str = ""        # 最后一笔方向：'up' / 'down'
    last_bi_high: float = 0.0
    last_bi_low: float = 0.0

    # 中枢
    zs_count: int = 0                  # 中枢数量
    last_zs_high: float = 0.0         # 最近中枢上沿
    last_zs_low: float = 0.0          # 最近中枢下沿
    last_zs_direction: str = ""        # 中枢方向（由进入段决定）

    # 当前价格相对中枢位置
    price_vs_zs: str = ""              # 'above' / 'inside' / 'below'
    last_close: float = 0.0

    # 信号
    signals: List[str] = field(default_factory=list)   # 活跃信号列表
    buy_point: str = ""                # '1buy' / '2buy' / '3buy' / ''
    sell_point: str = ""               # '1sell' / '2sell' / '3sell' / ''
    beichi: bool = False               # 是否背驰

    # 走势类型
    trend: str = ""                    # 'up' / 'down' / 'sideways'

    error: str = ""                    # 出错信息（空表示成功）


def analyze_stock(
    code: str,
    freq: str = "1d",
    count: int = 300,
    end_date: Optional[str] = None,
) -> AnalysisResult:
    """
    对单只股票运行缠论分析

    Parameters
    ----------
    code     : 股票代码，米筐格式
    freq     : 周期
    count    : K 线数量
    end_date : 截止日期
    """
    from .data import get_klines

    result = AnalysisResult(
        code=code,
        freq=freq,
        as_of=datetime.datetime.now(),
    )

    try:
        bars: List[RawBar] = get_klines(code, freq=freq, count=count, end_date=end_date)
    except Exception as e:
        result.error = f"数据获取失败: {e}"
        return result

    if len(bars) < 50:
        result.error = f"K 线数量不足（{len(bars)} 根），无法分析"
        return result

    try:
        c = CZSC(bars)
    except Exception as e:
        result.error = f"czsc 分析失败: {e}"
        return result

    result.last_close = bars[-1].close

    # --- 笔 ---
    bis = c.bi_list
    result.bi_count = len(bis)
    if bis:
        last_bi = bis[-1]
        result.last_bi_direction = "up" if last_bi.direction.value == 1 else "down"
        result.last_bi_high = last_bi.high
        result.last_bi_low = last_bi.low

    # --- 中枢 ---
    # czsc 0.9.x 不在 CZSC 上存储中枢属性，需调用 get_zs_seq(bi_list) 计算
    zs_list = get_zs_seq(c.bi_list)
    result.zs_count = len(zs_list)
    if zs_list:
        last_zs = zs_list[-1]
        result.last_zs_high = last_zs.zg
        result.last_zs_low = last_zs.zd
        # 价格相对中枢
        p = result.last_close
        if p > result.last_zs_high:
            result.price_vs_zs = "above"
        elif p < result.last_zs_low:
            result.price_vs_zs = "below"
        else:
            result.price_vs_zs = "inside"

    # --- 走势判断（需在买卖点判断前完成） ---
    result.trend = _judge_trend(bis)

    # --- 信号 ---
    signals = _extract_signals(c)
    result.signals = signals

    # 优先用结构规则判断买卖点（基于中枢数据）
    _judge_buy_sell_points(result, bis, zs_list)

    # 若结构规则无命中，再尝试 czsc 信号字典兜底
    if not result.buy_point and not result.sell_point and not result.beichi:
        result.buy_point = _detect_buy_point(signals)
        result.sell_point = _detect_sell_point(signals)
        result.beichi = _detect_beichi(signals)

    return result


def _judge_buy_sell_points(result: AnalysisResult, bis: list, zs_list: list) -> None:
    """基于结构数据（笔+中枢）判断买卖点，直接修改 result"""
    if not bis or not zs_list:
        return

    last_zs = zs_list[-1]
    zg = last_zs.zg   # 中枢上沿
    zd = last_zs.zd   # 中枢下沿
    p = result.last_close
    trend = result.trend
    bi_dir = result.last_bi_direction   # 'up' / 'down'
    bi_high = result.last_bi_high
    bi_low = result.last_bi_low

    # ---------------------------------------------------------------
    # 三类买点：上涨走势 + 最后向下笔回调守住中枢上沿 + 当前价在中枢上方
    #   回调低点 >= ZG * 0.97（允许3%误差）且当前价 > ZG
    # ---------------------------------------------------------------
    if (trend == "up"
            and bi_dir == "down"
            and bi_low >= zg * 0.97
            and p > zg):
        result.buy_point = "3buy"
        return

    # ---------------------------------------------------------------
    # 二类买点：上涨走势 + 最后向下笔低点落在中枢区间内（ZD~ZG）
    #   当前价已回升至中枢下沿之上
    # ---------------------------------------------------------------
    if (trend == "up"
            and bi_dir == "down"
            and zd <= bi_low < zg
            and p >= zd):
        result.buy_point = "2buy"
        return

    # ---------------------------------------------------------------
    # 底背驰（一类买点前兆）：下跌走势 + 笔数足够 + 最后向下笔力度收缩
    #   最后向下笔幅度 < 前一向下笔幅度 * 0.85
    # ---------------------------------------------------------------
    if trend == "down" and bi_dir == "down" and len(bis) >= 16:
        down_bis = [b for b in bis if b.direction.value != 1]
        if len(down_bis) >= 2:
            last_range = down_bis[-1].high - down_bis[-1].low
            prev_range = down_bis[-2].high - down_bis[-2].low
            if prev_range > 0 and last_range / prev_range < 0.85:
                result.beichi = True
                result.buy_point = "1buy"
                return

    # ---------------------------------------------------------------
    # 三类卖点：下跌走势 + 最后向上笔反弹未过中枢下沿 + 当前价在中枢下方
    # ---------------------------------------------------------------
    if (trend == "down"
            and bi_dir == "up"
            and bi_high <= zd * 1.03
            and p < zd):
        result.sell_point = "3sell"


def _extract_signals(c: CZSC) -> List[str]:
    """提取 czsc 当前活跃信号名称列表"""
    signals: List[str] = []
    # czsc 新版通过 signals 属性返回 dict
    raw = getattr(c, "signals", {})
    if isinstance(raw, dict):
        for k, v in raw.items():
            if v and v not in ("其他", "无", ""):
                signals.append(f"{k}_{v}")
    return signals


def _detect_buy_point(signals: List[str]) -> str:
    """从信号列表中识别买点类型"""
    joined = " ".join(signals)
    if "三买" in joined or "3buy" in joined.lower():
        return "3buy"
    if "二买" in joined or "2buy" in joined.lower():
        return "2buy"
    if "一买" in joined or "1buy" in joined.lower():
        return "1buy"
    return ""


def _detect_sell_point(signals: List[str]) -> str:
    """从信号列表中识别卖点类型"""
    joined = " ".join(signals)
    if "三卖" in joined or "3sell" in joined.lower():
        return "3sell"
    if "二卖" in joined or "2sell" in joined.lower():
        return "2sell"
    if "一卖" in joined or "1sell" in joined.lower():
        return "1sell"
    return ""


def _detect_beichi(signals: List[str]) -> bool:
    """判断是否存在背驰信号"""
    joined = " ".join(signals)
    return "背驰" in joined or "beichi" in joined.lower()


def _judge_trend(bis: list) -> str:
    """根据最后几笔判断趋势方向"""
    if len(bis) < 3:
        return "unknown"
    # 取最后三笔高低点
    last3 = bis[-3:]
    highs = [b.high for b in last3]
    lows = [b.low for b in last3]
    if highs[-1] > highs[0] and lows[-1] > lows[0]:
        return "up"
    if highs[-1] < highs[0] and lows[-1] < lows[0]:
        return "down"
    return "sideways"


# ---------------------------------------------------------------------------
# Markdown 报告
# ---------------------------------------------------------------------------

_TREND_CN = {"up": "上涨", "down": "下跌", "sideways": "震荡", "unknown": "未知"}
_DIR_CN = {"up": "向上笔", "down": "向下笔", "": "—"}
_PVZ_CN = {"above": "中枢上方", "inside": "中枢内部", "below": "中枢下方", "": "—"}
_BP_CN = {"1buy": "一类买点", "2buy": "二类买点", "3buy": "三类买点", "": ""}
_SP_CN = {"1sell": "一类卖点", "2sell": "二类卖点", "3sell": "三类卖点", "": ""}


def format_report(result: AnalysisResult) -> str:
    """将 AnalysisResult 格式化为 Markdown 文本，供 Claude 解读"""
    if result.error:
        return f"## {result.code} 分析失败\n\n**错误**: {result.error}\n"

    lines = [
        f"## {result.code} 缠论分析报告",
        f"**周期**: {result.freq}  |  **截止**: {result.as_of.strftime('%Y-%m-%d %H:%M')}  |  **收盘**: {result.last_close:.2f}",
        "",
        "### 走势结构",
        f"- 当前走势: **{_TREND_CN.get(result.trend, result.trend)}**",
        f"- 已识别笔数: {result.bi_count}",
        f"- 最后一笔: {_DIR_CN.get(result.last_bi_direction, result.last_bi_direction)}  "
        f"(高: {result.last_bi_high:.2f} / 低: {result.last_bi_low:.2f})",
        "",
        "### 中枢",
        f"- 已识别中枢数: {result.zs_count}",
    ]

    if result.zs_count > 0:
        lines += [
            f"- 最近中枢区间: [{result.last_zs_low:.2f}, {result.last_zs_high:.2f}]",
            f"- 当前价格位置: **{_PVZ_CN.get(result.price_vs_zs, result.price_vs_zs)}**",
        ]

    lines += ["", "### 买卖点 & 背驰"]

    if result.buy_point:
        lines.append(f"- **买点**: {_BP_CN[result.buy_point]}")
    if result.sell_point:
        lines.append(f"- **卖点**: {_SP_CN[result.sell_point]}")
    if result.beichi:
        lines.append("- **背驰**: 是")
    if not result.buy_point and not result.sell_point and not result.beichi:
        lines.append("- 暂无明确买卖点或背驰信号")

    if result.signals:
        lines += ["", "### 活跃信号（原始）"]
        for s in result.signals[:20]:   # 最多显示 20 条
            lines.append(f"- {s}")

    return "\n".join(lines) + "\n"
