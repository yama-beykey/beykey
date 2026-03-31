#!/bin/bash
# ============================================================
# daily.sh — B-STUDIO 毎日の動画生成 全自動ワンコマンド
#
# 使い方:
#   bash scripts/daily.sh              # トレンド調査 → 選択 → 動画生成
#   bash scripts/daily.sh --auto       # 自動で1位を選んで生成
#   bash scripts/daily.sh <URL> <名前> # URLとツール名を直接指定
#
# 例:
#   bash scripts/daily.sh
#   bash scripts/daily.sh --auto
#   bash scripts/daily.sh https://ltx.io/ltx-desktop "LTX Desktop"
# ============================================================
set -e

SKILL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
DATE=$(date +%Y-%m-%d)

echo "╔══════════════════════════════════════╗"
echo "║   B-STUDIO 動画生成パイプライン       ║"
echo "║   $(date '+%Y年%m月%d日')                    ║"
echo "╚══════════════════════════════════════╝"
echo ""

# APIキー確認
if [ -z "$OPENAI_API_KEY" ] && [ -z "$ANTHROPIC_API_KEY" ]; then
  echo "❌ APIキーが設定されていません。"
  echo ""
  echo "設定方法:"
  echo "  export ANTHROPIC_API_KEY='sk-ant-...'"
  echo "  または"
  echo "  export OPENAI_API_KEY='sk-...'"
  exit 1
fi

# Python依存パッケージ確認
echo "📦 依存パッケージ確認..."
python3 -c "import requests" 2>/dev/null || pip3 install requests -q
python3 -c "import anthropic" 2>/dev/null || pip3 install anthropic -q
echo "   ✅ 完了"
echo ""

# ── モード判定 ──
if [ -n "$1" ] && [[ "$1" != --* ]]; then
  # URLとツール名を直接指定
  URL="$1"
  TOOL_NAME="${2:-AI Tool}"
  echo "🔗 URL: $URL"
  echo "🛠  ツール: $TOOL_NAME"
  echo ""
  bash "$SKILL_DIR/scripts/create-video.sh" "$URL" "$TOOL_NAME" "$DATE"

elif [ "$1" = "--auto" ]; then
  # 自動でトレンド1位を選択
  echo "🔍 トレンド自動調査モード..."
  echo ""
  python3 "$SKILL_DIR/scripts/find-topic.py" --auto

else
  # インタラクティブ: トレンドTOP3を表示して選択
  echo "🔍 今日のトレンドを調査します..."
  echo ""
  python3 "$SKILL_DIR/scripts/find-topic.py"
fi
