#!/bin/bash
# 每日缠论复盘启动脚本（由 macOS launchd 调用）
# 手动测试：bash "/Users/wupfagi/Cloude Code/scripts/run_scan.sh"

export PATH="/Users/wupfagi/Library/Python/3.9/bin:/usr/local/bin:/usr/bin:/bin"

PYTHON="/usr/bin/python3"
SCRIPT="/Users/wupfagi/Cloude Code/scripts/daily_scan.py"
LOG="/Users/wupfagi/Cloude Code/reports/scan.log"

mkdir -p "/Users/wupfagi/Cloude Code/reports"

echo "" >> "$LOG"
echo "=== $(date '+%Y-%m-%d %H:%M:%S') launchd 触发 ===" >> "$LOG"

"$PYTHON" "$SCRIPT" all 1d >> "$LOG" 2>&1

echo "=== 结束 ===" >> "$LOG"
