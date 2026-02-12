#!/bin/bash
# ============================================
# 📧 一键生成日报并发送邮件
# 用法: 双击运行 或 终端输入 ./run_daily.sh
# ============================================
set -euo pipefail

cd "$(dirname "$0")"

echo "🚀 启动工业 AI 日报..."
echo "⏳ 正在采集 + 分析 + 发邮件 (约 5 分钟)..."

source .venv/bin/activate
today="$(date +%Y-%m-%d)"
log_file="logs/run-${today}.log"
mkdir -p logs

python main.py \
  --output email \
  --skip-dynamic \
  --skip-llm-filter \
  --output-dir output \
  --log-format json | tee "${log_file}"

echo ""
echo "✅ 完成！请检查以下产物："
echo "🧾 日志: ${log_file}"
echo "📊 运行摘要: output/run-summary-${today}.json"
echo "📄 报告(如启用 markdown): output/digest-${today}.md"
