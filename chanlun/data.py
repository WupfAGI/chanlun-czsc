"""
米筐 API 封装层
提供统一的数据获取接口，返回 czsc 兼容的 RawBar 列表
"""
from __future__ import annotations

import datetime
from typing import List, Optional

from czsc import RawBar, Freq

from . import config


def init_rq(username: str = "", license_key: str = "") -> None:
    """初始化米筐连接

    优先使用环境变量 RQDATAC2_CONF（rqsdk license 配置后自动生效）。
    若环境变量未设置，则使用 config.py 中的 license_key 构造 URI。
    """
    import os
    import rqdatac as rq

    # 优先走 rqsdk 配置的环境变量
    if os.environ.get("RQDATAC2_CONF") or os.environ.get("RQDATAC_CONF"):
        rq.init()
        return

    k = license_key or config.RQ_LICENSE_KEY
    if not k:
        raise ValueError(
            "请先运行: python3 -m rqsdk license -l <YOUR_LICENSE_KEY>\n"
            "或在 chanlun/config.py 中填写 RQ_LICENSE_KEY"
        )
    # 使用 URI 格式：tcp://license:<key>@host:port
    uri = f"tcp://license:{k}@rqdatad-pro.ricequant.com:16011"
    rq.init(uri=uri)


def _rq_freq_to_czsc(freq: str) -> Freq:
    """将米筐周期字符串转换为 czsc Freq 枚举"""
    mapping = {
        "1d": Freq.D,
        "60m": Freq.F60,
        "30m": Freq.F30,
        "15m": Freq.F15,
        "5m": Freq.F5,
    }
    if freq not in mapping:
        raise ValueError(f"不支持的周期 {freq!r}，可选：{list(mapping)}")
    return mapping[freq]


def get_klines(
    code: str,
    freq: str = "1d",
    count: int = 300,
    end_date: Optional[str] = None,
) -> List[RawBar]:
    """
    获取 K 线数据，返回 czsc RawBar 列表（按时间升序）

    Parameters
    ----------
    code      : 股票代码，米筐格式，如 '600519.XSHG'
    freq      : 周期，'1d' / '60m' / '30m' / '15m' / '5m'
    count     : 获取的 K 线根数
    end_date  : 结束日期，默认为今天
    """
    import rqdatac as rq
    import pandas as pd

    czsc_freq = _rq_freq_to_czsc(freq)

    end = pd.Timestamp(end_date or datetime.date.today())
    # 根据 count 和周期估算 start_date（留余量）
    if freq == "1d":
        start = end - pd.Timedelta(days=int(count * 1.5))
    elif freq in ("60m", "30m"):
        start = end - pd.Timedelta(days=int(count * 1.5 / 4))
    else:
        start = end - pd.Timedelta(days=int(count * 1.5 / 8))

    df: pd.DataFrame = rq.get_price(
        code,
        start_date=start.strftime("%Y-%m-%d"),
        end_date=end.strftime("%Y-%m-%d"),
        frequency=freq,
        fields=["open", "high", "low", "close", "volume"],
        adjust_type=config.DEFAULT_ADJUST,
    )

    # 只保留最后 count 根
    if df is not None and len(df) > count:
        df = df.iloc[-count:]

    if df is None or df.empty:
        raise ValueError(f"未获取到 {code} 的数据，请检查代码格式或 API 权限")

    # 米筐返回 MultiIndex (order_book_id, date)，提取 date 层
    if isinstance(df.index, pd.MultiIndex):
        df = df.droplevel(0)  # 去掉 order_book_id 层，只保留 date

    bars: List[RawBar] = []
    for i, (dt, row) in enumerate(df.iterrows()):
        # dt 可能是 str / date / datetime / Timestamp
        if isinstance(dt, str):
            dt = datetime.datetime.strptime(dt, "%Y-%m-%d").replace(hour=15)
        elif isinstance(dt, datetime.date) and not isinstance(dt, datetime.datetime):
            dt = datetime.datetime(dt.year, dt.month, dt.day, 15, 0, 0)
        elif hasattr(dt, 'to_pydatetime'):
            dt = dt.to_pydatetime()
            if dt.hour == 0:
                dt = dt.replace(hour=15)
        bars.append(
            RawBar(
                symbol=code,
                id=i,
                freq=czsc_freq,
                dt=dt,
                open=float(row["open"]),
                high=float(row["high"]),
                low=float(row["low"]),
                close=float(row["close"]),
                vol=float(row["volume"]),
                amount=0.0,  # rqdatac get_price 没有 amount，可后续补
            )
        )
    return bars


def get_stock_universe(date: Optional[str] = None) -> List[str]:
    """
    获取全 A 股代码列表（过滤退市股，可选过滤 ST）

    Returns
    -------
    list of str, 米筐格式股票代码，如 ['600519.XSHG', ...]
    """
    import rqdatac as rq
    import pandas as pd

    df: pd.DataFrame = rq.all_instruments(type="CS", date=date)
    df = df.set_index("order_book_id")  # 股票代码作为索引
    codes = df.index.tolist()

    if config.EXCLUDE_ST:
        # ST 股名称通常含有 'ST' 或 '*ST'
        non_st = df[~df["symbol"].str.contains(r"ST", na=False)].index.tolist()
        codes = non_st

    if config.MIN_LISTED_DAYS > 0:
        today = pd.Timestamp(date or datetime.date.today())
        min_listed = today - pd.Timedelta(days=config.MIN_LISTED_DAYS)
        df2 = df.loc[codes]
        listed = pd.to_datetime(df2["listed_date"], errors="coerce")
        codes = df2[listed <= min_listed].index.tolist()

    return codes
