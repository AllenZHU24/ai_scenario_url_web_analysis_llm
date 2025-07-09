#!/usr/bin/env bash
# -------------------------------------------------------------
# 批量运行 main.py，对 inputs 目录下的所有 .txt 文件执行：
#   python main.py --input <file_path>
#
# 新增功能:
# - 如果 python 脚本执行失败，会自动重试。
# - 可配置最大重试次数和重试间隔。
# - 在多次重试失败后，会记录错误并继续处理下一个文件。
# -------------------------------------------------------------
set -euo pipefail

# --- 可配置参数 ---
MAX_RETRIES=3        # 每个文件的最大重试次数
RETRY_DELAY=5        # 每次重试前的等待时间（秒）
# --------------------

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

# 记录总体执行状态
all_successful=true

for txt in "${TXT_FILES[@]}"; do
  echo "▶️  开始处理: $txt"
  # ----------新增重启机制----------
  success=false
  # 重试循环，从第1次尝试到第 (MAX_RETRIES + 1) 次尝试
  for ((attempt=1; attempt<=MAX_RETRIES + 1; attempt++)); do
    # 直接在 if 条件中执行命令。
    # 如果命令成功（退出码为0），if 为真；如果失败（退出码非0），if 为假。
    # 这种写法可以防止 set -e 在命令失败时直接退出脚本。
    if python "$MAIN_SCRIPT" --input "$txt"; then
      echo "✅  成功完成: $txt"
      success=true
      break # 成功，跳出重试循环
    else
      # 捕获 python 脚本的退出码
      exit_code=$?
      if [[ $attempt -le MAX_RETRIES ]]; then
        echo "❗️  处理失败 (退出码: $exit_code)，将在 ${RETRY_DELAY}s 后重试... (尝试次数: $attempt/$MAX_RETRIES)" >&2
        sleep "$RETRY_DELAY"
      else
        echo "❌  处理失败: $txt" >&2
        echo "  └— 经过 $MAX_RETRIES 次重试后仍然失败 (最后一次退出码: $exit_code)。将继续处理下一个文件。" >&2
        all_successful=false
      fi
    fi
  done
  
  echo "-----------------------------"
done

echo "🎉 全部任务处理完毕。"

# 根据最终是否所有文件都成功处理来返回不同的退出信息
if $all_successful; then
  echo "所有文件均已成功处理。"
else
  echo "部分文件处理失败，请检查上面的错误日志。"
  # exit 1 # 如果希望在有任何失败时，整个脚本最终以失败状态退出，请取消此行注释
fi