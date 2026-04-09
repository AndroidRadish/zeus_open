#!/usr/bin/env bash
# zeus-open init harness — 环境基础验证脚本
set -euo pipefail

ERRORS=0

# 1. 检查 Python 3
if ! command -v python3 &>/dev/null && ! command -v python &>/dev/null; then
    echo "❌ Python 3 未找到"
    ERRORS=$((ERRORS + 1))
else
    PY=$(command -v python3 || command -v python)
    echo "✅ Python 可用: $PY"
fi

# 2. 检查关键文件
for f in .zeus/main/config.json .zeus/main/task.json .zeus/scripts/zeus_runner.py; do
    if [[ ! -f "$f" ]]; then
        echo "❌ 关键文件缺失: $f"
        ERRORS=$((ERRORS + 1))
    else
        echo "✅ 文件存在: $f"
    fi
done

# 3. 检查 zeus_runner.py --status
if [[ -f ".zeus/scripts/zeus_runner.py" ]]; then
    if python .zeus/scripts/zeus_runner.py --status >/dev/null 2>&1; then
        echo "✅ zeus_runner.py --status 运行正常"
    else
        echo "❌ zeus_runner.py --status 运行失败"
        ERRORS=$((ERRORS + 1))
    fi
fi

# 4. 汇总
if [[ "$ERRORS" -eq 0 ]]; then
    echo ""
    echo "🚀 环境验证通过，可以开始工作。"
    exit 0
else
    echo ""
    echo "⚠️  环境验证失败，发现 $ERRORS 个问题，请先修复。"
    exit 1
fi
