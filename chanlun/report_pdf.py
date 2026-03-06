"""
PDF 报告生成模块
将缠论扫描结果渲染为格式化的 PDF 报告
使用 fpdf2 + macOS 内置中文字体
"""
from __future__ import annotations

import datetime
import os
from typing import List, Tuple

from fpdf import FPDF

from .analyzer import AnalysisResult

# macOS 中文字体候选（按优先级）
_CN_FONTS = [
    "/System/Library/Fonts/Hiragino Sans GB.ttc",      # 冬青黑体（简体中文）
    "/System/Library/Fonts/STHeiti Light.ttc",          # 华文黑体
    "/System/Library/Fonts/STHeiti Medium.ttc",
]

# 列宽（总 A4 可用宽度 ≈ 190mm）
_COL_WIDTHS = [28, 26, 14, 14, 22, 36, 22]   # 代码/买点/背驰/走势/收盘/中枢/位置
_COL_HEADERS = ["代码", "买点", "背驰", "走势", "收盘", "中枢区间", "价格位置"]

_BP_CN = {"1buy": "一类买点", "2buy": "二类买点", "3buy": "三类买点", "": "—"}
_SP_CN = {"1sell": "一类卖点", "2sell": "二类卖点", "3sell": "三类卖点", "": "—"}
_TREND_CN = {"up": "上涨", "down": "下跌", "sideways": "震荡", "unknown": "未知", "": "—"}
_PVZ_CN = {"above": "上方", "inside": "内部", "below": "下方", "": "—"}


def _find_font() -> str:
    for path in _CN_FONTS:
        if os.path.exists(path):
            return path
    raise FileNotFoundError(
        "未找到可用的中文字体文件，请确认 macOS 系统字体目录完整"
    )


class _ChanPDF(FPDF):
    """带页眉页脚的 PDF 基类"""

    def __init__(self, report_date: str, freq: str):
        super().__init__()
        self._report_date = report_date
        self._freq = freq

    def header(self):
        # 页眉：右对齐日期+周期
        if self.page_no() == 1:
            return
        self.set_font("cn", size=8)
        self.set_text_color(150, 150, 150)
        self.cell(0, 6, f"缠论复盘  {self._report_date}  {self._freq}", align="R")
        self.ln(4)
        self.set_text_color(0, 0, 0)

    def footer(self):
        self.set_y(-12)
        self.set_font("cn", size=8)
        self.set_text_color(150, 150, 150)
        self.cell(0, 6, f"数据来源：米筐 RQData  |  第 {self.page_no()} 页", align="C")
        self.set_text_color(0, 0, 0)


def generate_pdf(
    results: List[Tuple[str, AnalysisResult]],
    freq: str,
    pdf_path: str,
) -> None:
    """
    将筛选结果渲染为 PDF 并保存

    Parameters
    ----------
    results  : scan_buy_points() 返回的 [(code, AnalysisResult)] 列表
    freq     : 分析周期字符串（如 '1d'）
    pdf_path : 输出路径（.pdf）
    """
    today = datetime.date.today().strftime("%Y-%m-%d")
    font_path = _find_font()

    pdf = _ChanPDF(report_date=today, freq=freq)
    pdf.add_font("cn", fname=font_path, uni=True)
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    # ── 封面标题区 ──────────────────────────────────────────────
    pdf.set_font("cn", size=20)
    pdf.set_text_color(30, 30, 30)
    pdf.cell(0, 12, "缠论买点筛选报告", align="C", ln=True)

    pdf.set_font("cn", size=10)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(0, 7,
             f"日期：{today}    周期：{freq}    命中标的：{len(results)} 只",
             align="C", ln=True)
    pdf.ln(4)

    # 分隔线
    pdf.set_draw_color(200, 200, 200)
    pdf.line(pdf.get_x() + 10, pdf.get_y(),
             pdf.get_x() + pdf.epw - 10, pdf.get_y())
    pdf.ln(6)

    if not results:
        pdf.set_font("cn", size=11)
        pdf.set_text_color(0, 0, 0)
        pdf.cell(0, 10, "今日暂无符合缠论买点条件的标的。", align="C", ln=True)
        pdf.output(pdf_path)
        return

    # ── 汇总表格 ────────────────────────────────────────────────
    _draw_summary_table(pdf, results)
    pdf.ln(8)

    # ── 逐股详情 ────────────────────────────────────────────────
    pdf.set_font("cn", size=13)
    pdf.set_text_color(30, 30, 30)
    pdf.cell(0, 8, "逐股详情", ln=True)
    pdf.ln(2)

    for code, r in results:
        _draw_stock_detail(pdf, code, r)

    pdf.output(pdf_path)


def _draw_summary_table(pdf: _ChanPDF, results: List[Tuple[str, AnalysisResult]]):
    """绘制汇总表格"""
    ROW_H = 7

    # 表头背景
    pdf.set_fill_color(45, 85, 140)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("cn", size=9)
    for i, (header, w) in enumerate(zip(_COL_HEADERS, _COL_WIDTHS)):
        pdf.cell(w, ROW_H, header, border=0, align="C", fill=True)
    pdf.ln()

    # 数据行（交替底色）
    pdf.set_text_color(30, 30, 30)
    pdf.set_font("cn", size=8)
    for idx, (code, r) in enumerate(results):
        fill = idx % 2 == 0
        pdf.set_fill_color(245, 248, 255) if fill else pdf.set_fill_color(255, 255, 255)

        zs_range = (
            f"{r.last_zs_low:.2f}-{r.last_zs_high:.2f}"
            if r.zs_count > 0 else "—"
        )

        row = [
            code.replace(".XSHG", "").replace(".XSHE", ""),
            _BP_CN.get(r.buy_point, "—"),
            "是" if r.beichi else "否",
            _TREND_CN.get(r.trend, "—"),
            f"{r.last_close:.2f}",
            zs_range,
            _PVZ_CN.get(r.price_vs_zs, "—"),
        ]
        for cell, w in zip(row, _COL_WIDTHS):
            pdf.cell(w, ROW_H, cell, border=0, align="C", fill=True)
        pdf.ln()

    # 底部边框线
    pdf.set_draw_color(180, 180, 180)
    pdf.line(pdf.get_x(), pdf.get_y(), pdf.get_x() + sum(_COL_WIDTHS), pdf.get_y())


def _draw_stock_detail(pdf: _ChanPDF, code: str, r: AnalysisResult):
    """绘制单只股票的详情小节"""
    # 检查剩余空间，不够则换页
    if pdf.get_y() > 240:
        pdf.add_page()

    # 小节标题
    bp_label = _BP_CN.get(r.buy_point, "")
    title = f"▌ {code}   {bp_label}{'  |  底背驰' if r.beichi else ''}"
    pdf.set_font("cn", size=11)
    pdf.set_text_color(45, 85, 140)
    pdf.cell(0, 8, title, ln=True)

    # 详情内容
    pdf.set_font("cn", size=9)
    pdf.set_text_color(60, 60, 60)

    lines = []
    lines.append(f"走势：{_TREND_CN.get(r.trend, '—')}  |  已识别笔数：{r.bi_count}  |  "
                 f"最后一笔：{'向上' if r.last_bi_direction=='up' else '向下'}"
                 f"（高 {r.last_bi_high:.2f} / 低 {r.last_bi_low:.2f}）")

    if r.zs_count > 0:
        lines.append(f"中枢：共 {r.zs_count} 个  |  "
                     f"最近中枢 [{r.last_zs_low:.2f}, {r.last_zs_high:.2f}]  |  "
                     f"当前价 {_PVZ_CN.get(r.price_vs_zs, '—')} 中枢")

    if r.buy_point:
        lines.append(f"买点类型：{_BP_CN[r.buy_point]}")
    if r.sell_point:
        lines.append(f"卖点类型：{_SP_CN[r.sell_point]}")
    if r.beichi:
        lines.append("背驰：是")

    if r.signals:
        lines.append(f"活跃信号：{' / '.join(r.signals[:6])}")

    for line in lines:
        pdf.cell(0, 6, line, ln=True)

    # 分隔
    pdf.set_draw_color(220, 220, 220)
    pdf.line(pdf.get_x() + 5, pdf.get_y() + 2,
             pdf.get_x() + pdf.epw - 5, pdf.get_y() + 2)
    pdf.ln(5)
