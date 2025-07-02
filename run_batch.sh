#!/usr/bin/env bash
# -------------------------------------------------------------
# 批量运行 main_v0_4_4.py，对 inputs 目录下的所有 .txt 文件执行：
#   python main_v0_4_4.py --input <file_path>
# -------------------------------------------------------------
set -euo pipefail

# 获取脚本所在目录，使相对路径更健壮
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

INPUT_DIR="./inputs"
MAIN_SCRIPT="./main.py"

if [[ ! -d "$INPUT_DIR" ]]; then
  echo "❌ 输入目录不存在: $INPUT_DIR" >&2
  exit 1
fi

shopt -s nullglob
TXT_FILES=("$INPUT_DIR"/*.txt)
shopt -u nullglob

if [[ ${#TXT_FILES[@]} -eq 0 ]]; then
  echo "⚠️ 未在 $INPUT_DIR 中找到任何 .txt 文件" >&2
  exit 1
fi

for txt in "${TXT_FILES[@]}"; do
  echo "▶️  开始处理: $txt"
  python "$MAIN_SCRIPT" --input "$txt"
  echo "✅  完成: $txt"
  echo "-----------------------------"
  # 如需暂停或限制速度，可在此处加 sleep
done

echo "🎉 全部任务处理完毕。" 