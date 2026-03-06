#!/usr/bin/env python3
"""
每日收盘复盘脚本（自动模式）

用法：
    python scripts/daily_scan.py              # 扫描全 A 股，日线
    python scripts/daily_scan.py all 1d       # 同上
    python scripts/daily_scan.py watchlist 1d # 仅扫描 watchlist.txt 中的自选股
    python scripts/daily_scan.py all 1d --force  # 强制运行（忽略重复保护）

由 macOS launchd 在每个交易日 15:35 自动触发。
"""
import sys
import os
import datetime
import subprocess
import platform

# 确保能导入 chanlun 包
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from chanlun.data import init_rq, get_stock_universe
from chanlun.screener import load_watchlist, scan_buy_points, format_scan_report
from chanlun import config


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------

def log(msg: str, log_path: str = None):
    """打印并同时写入日志文件"""
    ts = datetime.datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    if log_path:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(line + "\n")


def is_trading_day() -> bool:
    """判断今天是否为 A 股交易日"""
    import rqdatac as rq
    today = datetime.date.today().strftime("%Y-%m-%d")
    try:
        dates = rq.get_trading_dates(start_date=today, end_date=today, market="cn")
        return len(dates) > 0
    except Exception:
        # API 异常时保守返回 True，让主流程继续
        return True


def get_remaining_flow_mb() -> float:
    """
    通过 rqsdk license info 获取剩余流量（MB）。
    解析失败时返回 -1。
    """
    try:
        result = subprocess.run(
            [sys.executable, "-m", "rqsdk", "license", "info"],
            capture_output=True, text=True, timeout=15
        )
        for line in result.stdout.splitlines():
            if "剩余流量" in line or "remaining" in line.lower():
                # 格式示例：|  流量限制: 1024.00 MB |  剩余流量: 909.41 MB |
                import re
                m = re.search(r"剩余流量[：:]\s*([\d.]+)\s*MB", line)
                if m:
                    return float(m.group(1))
    except Exception:
        pass
    return -1.0


def notify_macos(title: str, msg: str):
    """macOS 系统通知（仅 macOS 有效）"""
    if platform.system() != "Darwin":
        return
    script = f'display notification "{msg}" with title "{title}"'
    subprocess.run(["osascript", "-e", script], check=False, timeout=5)


# ---------------------------------------------------------------------------
# 主逻辑
# ---------------------------------------------------------------------------

def main():
    args = [a for a in sys.argv[1:] if a != "--force"]
    force = "--force" in sys.argv

    scope = args[0] if args else "all"
    freq  = args[1] if len(args) > 1 else "1d"

    date_str  = datetime.date.today().strftime("%Y%m%d")
    report_path = os.path.join(config.REPORTS_DIR, f"{date_str}_{scope}_{freq}.md")
    log_path    = os.path.join(config.REPORTS_DIR, "scan.log")
    os.makedirs(config.REPORTS_DIR, exist_ok=True)

    # --- 日志分隔 ---
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"\n{'='*60}\n{datetime.datetime.now()}\n{'='*60}\n")

    log(f"[daily_scan] scope={scope} freq={freq} force={force}", log_path)

    # --- 1. 初始化 API ---
    log("[daily_scan] 初始化米筐 API...", log_path)
    init_rq()

    # --- 2. 交易日检查 ---
    if not is_trading_day():
        log("[daily_scan] 今日非交易日，退出。", log_path)
        return

    # --- 3. 重复运行保护 ---
    if not force and os.path.exists(report_path):
        log(f"[daily_scan] 今日报告已存在: {report_path}，跳过（用 --force 强制重跑）", log_path)
        notify_macos("缠论复盘", f"今日报告已存在，跳过重复扫描")
        return

    # --- 4. 获取股票列表 ---
    if scope == "all":
        log("[daily_scan] 获取全 A 股列表...", log_path)
        codes = get_stock_universe()
        log(f"[daily_scan] 共 {len(codes)} 只股票，开始扫描（周期: {freq}）...", log_path)
    else:
        codes = load_watchlist()
        if not codes:
            log("[daily_scan] watchlist.txt 为空，请先填写自选股代码。", log_path)
            sys.exit(1)
        log(f"[daily_scan] 自选股 {len(codes)} 只，开始扫描（周期: {freq}）...", log_path)

    # --- 5. 扫描 ---
    results = scan_buy_points(codes, freq=freq)
    hit = len(results)
    log(f"[daily_scan] 扫描完成，命中 {hit} 只标的。", log_path)

    # --- 6. 保存报告 ---
    report = format_scan_report(results, freq)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
    log(f"[daily_scan] Markdown 报告已保存至: {report_path}", log_path)

    # --- 6b. 生成 PDF ---
    pdf_path = report_path.replace(".md", ".pdf")
    try:
        from chanlun.report_pdf import generate_pdf
        generate_pdf(results, freq, pdf_path)
        log(f"[daily_scan] PDF 报告已保存至: {pdf_path}", log_path)
    except Exception as e:
        log(f"[daily_scan] PDF 生成失败（不影响主流程）: {e}", log_path)

    # --- 7. 查询剩余流量 ---
    flow_mb = get_remaining_flow_mb()
    if flow_mb >= 0:
        flow_info = f"剩余流量 {flow_mb:.1f} MB"
        if flow_mb < 200:
            flow_info = f"⚠️ 流量告急！{flow_info}"
        log(f"[daily_scan] {flow_info}", log_path)
    else:
        flow_info = ""

    # --- 8. macOS 通知 ---
    notif_body = f"命中 {hit} 只标的"
    if flow_info:
        notif_body += f" | {flow_info}"
    notify_macos("缠论复盘完成", notif_body)

    print(report)


if __name__ == "__main__":
    main()
