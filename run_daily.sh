#!/bin/bash
# ============================================
# 📧 一键生成日报并发送邮件
# 用法: 双击运行 或 终端输入 ./run_daily.sh
# ============================================

cd "$(dirname "$0")"

echo "🚀 启动工业 AI 日报..."
echo "⏳ 正在采集 + 分析 + 发邮件 (约 5 分钟)..."

source .venv/bin/activate
python main.py --output email --skip-dynamic --skip-llm-filter

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ 完成！邮件已发送，请查收 Gmail。"
    echo "📄 本地报告: output/digest-$(date +%Y-%m-%d).md"
else
    echo ""
    echo "❌ 运行失败，请检查日志。"
fi
