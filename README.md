# 缠中说缠 A股分析系统

基于 [czsc](https://github.com/zengbin93/czsc) 开源库和米筐（RQData）API，实现缠中说缠理论的A股技术分析。支持单股分析与全市场每日收盘自动复盘筛选。

## 功能

- **单股分析**：识别分型、笔、中枢，判断走势类型（上涨/下跌/震荡）及买卖点
- **全市场扫描**：每日收盘后自动筛选全A股（5000+）中有买点信号的标的
- **Claude Code Skill**：通过 `/chanlun-analyze 600519` 指令在 Claude 中直接分析
- **双格式报告**：同时输出 Markdown 和 PDF 报告
- **macOS 自动化**：通过 launchd 在每个交易日 15:35 自动触发复盘

## 缠论结构

```
分型（顶/底）→ 笔 → 线段 → 中枢 → 买卖点 → 背驰
```

## 快速开始

### 1. 安装依赖

```bash
pip install czsc rqdatac rqsdk fpdf2 pandas
```

### 2. 配置米筐 API

```bash
cp chanlun/config.example.py chanlun/config.py
# 编辑 config.py，填入你的 RQ_USERNAME 和 RQ_LICENSE_KEY

# 或通过 rqsdk 初始化 license
python3 -m rqsdk license -l YOUR_LICENSE_KEY
```

### 3. 分析单只股票

```bash
python3 scripts/analyze.py 600519      # 茅台（自动补全为 600519.XSHG）
python3 scripts/analyze.py 000001 60m  # 平安银行 60 分钟线
```

### 4. 全市场扫描

```bash
python3 scripts/daily_scan.py all 1d          # 扫描全A股
python3 scripts/daily_scan.py all 1d --force  # 强制重跑（忽略今日已有报告）
```

### 5. 配置 Claude Code Skill（可选）

将 `~/.claude/skills/chanlun-analyze/SKILL.md` 配置好后，在 Claude Code 中直接使用：

```
/chanlun-analyze 601666
/chanlun-analyze 000001 60m
```

## 项目结构

```
├── chanlun/
│   ├── config.example.py   # 配置模板（复制为 config.py 并填入凭证）
│   ├── data.py             # 米筐 API 封装（K线获取、股票池）
│   ├── analyzer.py         # czsc 封装，输出结构化分析结果
│   ├── screener.py         # 批量扫描，筛选买点标的
│   └── report_pdf.py       # PDF 报告生成
├── scripts/
│   ├── analyze.py          # 单股分析 CLI 入口
│   ├── daily_scan.py       # 每日复盘扫描主脚本
│   └── run_scan.sh         # macOS launchd 包装脚本
├── requirements.txt
└── watchlist.txt           # 自选股列表（每行一个代码）
```

## macOS 自动复盘

每个交易日 15:35 自动运行，报告保存至 `reports/` 目录：

```bash
# 加载 launchd 任务（首次配置）
launchctl load ~/Library/LaunchAgents/com.chanlun.dailyscan.plist

# 手动触发
launchctl kickstart -k gui/$(id -u)/com.chanlun.dailyscan
```

## 注意事项

- 需要有效的米筐（RQData）账号和 License Key
- 全市场扫描约消耗 200-400MB 流量（试用账号注意流量限制）
- 本项目仅供学习和技术研究，**不构成任何投资建议**

## 依赖

| 库 | 说明 |
|---|---|
| [czsc](https://github.com/zengbin93/czsc) | 缠中说缠开源实现 |
| rqdatac | 米筐数据 API |
| rqsdk | 米筐 SDK（License 管理） |
| fpdf2 | PDF 报告生成 |
| pandas | 数据处理 |

---

> ⚠️ 免责声明：本项目基于缠中说缠理论进行技术分析，所有分析结果仅供参考，不构成任何投资建议。股市有风险，投资需谨慎。
