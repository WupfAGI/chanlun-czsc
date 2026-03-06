"""
配置文件模板 - 复制为 config.py 并填入你的米筐 API 凭证
cp chanlun/config.example.py chanlun/config.py
"""
import os

# 米筐 API 凭证（优先从环境变量读取，避免硬编码）
RQ_USERNAME = os.environ.get("RQ_USERNAME", "your_phone_number")
RQ_LICENSE_KEY = os.environ.get("RQ_LICENSE_KEY", "your_license_key")

# 默认分析参数
DEFAULT_FREQ = "1d"       # 默认周期：日线
DEFAULT_COUNT = 300       # 默认获取K线数量
DEFAULT_ADJUST = "pre"    # 复权方式：前复权

# 自选股列表文件路径
WATCHLIST_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "watchlist.txt")

# 报告输出目录
REPORTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "reports")

# 筛选参数
EXCLUDE_ST = True
MIN_LISTED_DAYS = 250     # 至少上市一年

# czsc 周期映射（米筐格式 -> czsc 格式）
FREQ_MAP = {
    "1d": "日线",
    "60m": "60分钟",
    "30m": "30分钟",
    "15m": "15分钟",
    "5m": "5分钟",
}
