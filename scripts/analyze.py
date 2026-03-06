#!/usr/bin/env python3
"""
单股缠论分析命令行入口（供 Claude Skill 调用）

用法：
    python scripts/analyze.py 600519.XSHG          # 日线分析
    python scripts/analyze.py 600519.XSHG 1d       # 日线
    python scripts/analyze.py 600519.XSHG 60m      # 60分钟线

输出：Markdown 格式的分析报告（打印到 stdout）
"""
import sys
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from chanlun.data import init_rq
from chanlun.analyzer import analyze_stock, format_report


def _normalize_code(raw: str) -> str:
    """自动补全交易所后缀"""
    raw = raw.upper().strip()
    if "." in raw:
        return raw
    # 简单规则
    if raw.startswith("6"):
        return f"{raw}.XSHG"
    if raw.startswith(("0", "3")):
        return f"{raw}.XSHE"
    if raw.startswith("8") or raw.startswith("4"):
        return f"{raw}.BJSE"
    return raw


def main():
    args = sys.argv[1:]
    if not args:
        print("用法: python scripts/analyze.py <股票代码> [周期]")
        print("示例: python scripts/analyze.py 600519.XSHG 1d")
        sys.exit(1)

    code = _normalize_code(args[0])
    freq = args[1] if len(args) > 1 else "1d"

    print(f"[analyze] 初始化米筐 API...", file=sys.stderr)
    init_rq()

    print(f"[analyze] 分析 {code}（{freq}）...", file=sys.stderr)
    result = analyze_stock(code, freq=freq)
    report = format_report(result)

    # 输出到 stdout（Skill 的 !`command` 会捕获此输出）
    print(report)


if __name__ == "__main__":
    main()
