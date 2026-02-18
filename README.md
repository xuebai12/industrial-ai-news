# Industrial AI News Pipeline

抓取工业 AI 相关新闻，做相关性过滤与双视角分析（学生/技术员），并手动发送日报。

## Current Status

- 发布模式：仅手动运行（已禁用定时脚本）。
- 输出渠道：`email` / `markdown` / `notion` / `both`。
- 当 LLM 分析失败时：系统会生成可读保底摘要，不再输出 `N/A` 或 `Kein auswertbares Modell-Ergebnis verfügbar`。

## Quick Start

```bash
cd /Users/baixue/news
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
```

编辑 `.env`：

- 本地模型：`USE_LOCAL_OLLAMA=true`，并设置 `OLLAMA_MODEL`
- 或云端模型：设置 `NVIDIA_API_KEY`
- 邮件发送：`SMTP_HOST` `SMTP_PORT` `SMTP_USER` `SMTP_PASS` `EMAIL_TO`
- Notion（可选）：`NOTION_API_KEY` `NOTION_DATABASE_ID`

## Manual Run

```bash
# 邮件
./.venv/bin/python main.py --output email --output-dir output

# 邮件 + Markdown + Notion
./.venv/bin/python main.py --output both --output-dir output --log-format json

# 仅本地预览（不发邮件）
./.venv/bin/python main.py --dry-run --output email
```

## Key CLI Options

- `--skip-dynamic`: 跳过动态站点抓取（更快、更稳）
- `--skip-llm-filter`: 跳过相关性二次 LLM 校验
- `--mock`: 使用模拟分析结果，便于联调
- `--strict`: 任一关键阶段失败即返回非零退出码

## Notes

- 发送历史去重文件：`output/sent_history.json`

## Troubleshooting

1. 邮件发不出  
检查 `.env` 中 SMTP 配置和 `EMAIL_TO`。

2. 本地模型分析质量差或慢  
检查 Ollama 服务状态与 `OLLAMA_MODEL`；必要时切换到 NVIDIA 模型。

3. 文章太少  
可临时加 `--skip-llm-filter` 观察关键词过滤结果是否正常。

## Project Layout

- `/Users/baixue/news/main.py`: 主流程（抓取 -> 过滤 -> 分析 -> 交付）
- `/Users/baixue/news/src/scrapers/`: 抓取器
- `/Users/baixue/news/src/filters/`: 相关性过滤
- `/Users/baixue/news/src/analyzers/`: LLM 分析
- `/Users/baixue/news/src/delivery/`: 邮件/Notion/Markdown 交付
- `/Users/baixue/news/config.py`: 配置、关键词、画像、数据源

