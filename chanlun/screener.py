"""
批量筛选模块
扫描自选股或全市场，返回符合缠论买点条件的标的
"""
from __future__ import annotations

import time
from typing import List, Optional, Tuple

from .analyzer import AnalysisResult, analyze_stock
from . import config


def load_watchlist(path: Optional[str] = None) -> List[str]:
    """从 watchlist.txt 读取自选股代码列表"""
    p = path or config.WATCHLIST_PATH
    codes = []
    with open(p, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            codes.append(line)
    return codes


def scan_buy_points(
    codes: List[str],
    freq: str = "1d",
    count: int = 300,
    sleep: float = 0.2,
) -> List[Tuple[str, AnalysisResult]]:
    """
    批量扫描，筛出有买点信号的股票

    Parameters
    ----------
    codes  : 股票代码列表
    freq   : 分析周期
    count  : K 线数量
    sleep  : 每只股票间隔（秒），避免 API 限速

    Returns
    -------
    list of (code, AnalysisResult)，按买点类型排序（一买 > 二买 > 三买）
    """
    results = []
    total = len(codes)

    for i, code in enumerate(codes, 1):
        print(f"[{i}/{total}] 分析 {code}...", end="\r", flush=True)
        r = analyze_stock(code, freq=freq, count=count)
        if not r.error and (r.buy_point or r.beichi):
            results.append((code, r))
        if sleep > 0:
            time.sleep(sleep)

    print()  # 换行

    # 排序：一买 > 二买 > 三买，背驰附加
    order = {"1buy": 0, "2buy": 1, "3buy": 2, "": 3}
    results.sort(key=lambda x: order.get(x[1].buy_point, 3))
    return results


def format_scan_report(results: List[Tuple[str, AnalysisResult]], freq: str) -> str:
    """将筛选结果格式化为 Markdown 表格"""
    import datetime

    lines = [
        f"# 缠论买点筛选报告",
        f"**时间**: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}  |  **周期**: {freq}",
        f"**命中标的数**: {len(results)}",
        "",
    ]

    if not results:
        lines.append("暂无符合缠论买点条件的标的。")
        return "\n".join(lines) + "\n"

    _BP_CN = {"1buy": "一类买点", "2buy": "二类买点", "3buy": "三类买点", "": "—"}
    _TREND_CN = {"up": "上涨", "down": "下跌", "sideways": "震荡", "unknown": "?"}

    lines += [
        "| 代码 | 买点 | 背驰 | 走势 | 收盘 | 中枢区间 | 价格位置 |",
        "|------|------|------|------|------|---------|---------|",
    ]

    for code, r in results:
        zs_range = (
            f"{r.last_zs_low:.2f}-{r.last_zs_high:.2f}"
            if r.zs_count > 0
            else "—"
        )
        pvz_cn = {"above": "上方", "inside": "内部", "below": "下方", "": "—"}
        lines.append(
            f"| {code} "
            f"| {_BP_CN.get(r.buy_point, '—')} "
            f"| {'是' if r.beichi else '否'} "
            f"| {_TREND_CN.get(r.trend, '?')} "
            f"| {r.last_close:.2f} "
            f"| {zs_range} "
            f"| {pvz_cn.get(r.price_vs_zs, '—')} |"
        )

    lines += ["", "---", ""]

    # 逐只附上详情
    for code, r in results:
        from .analyzer import format_report
        lines.append(format_report(r))
        lines.append("")

    return "\n".join(lines)
