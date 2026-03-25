#!/bin/bash
# ============================================================
# create-video.sh — URLを渡すだけで縦動画を全自動生成
# 使い方: bash scripts/create-video.sh <URL> <ツール名> [日付]
# 例: bash scripts/create-video.sh https://openclaw.ai OpenClaw 2026-03-25
# ============================================================
set -e

URL="$1"
TOOL_NAME="$2"
DATE="${3:-$(date +%Y-%m-%d)}"
SKILL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
OUTPUT_DIR="$HOME/Videos/daily-shorts/$DATE"

if [ -z "$URL" ] || [ -z "$TOOL_NAME" ]; then
  echo "Usage: bash scripts/create-video.sh <URL> <ツール名> [日付]"
  echo "例: bash scripts/create-video.sh https://openclaw.ai OpenClaw 2026-03-25"
  exit 1
fi

if [ -z "$OPENAI_API_KEY" ]; then
  echo "❌ OPENAI_API_KEY が設定されていません"
  echo "   export OPENAI_API_KEY='sk-...'"
  exit 1
fi

echo "🎬 ===== 動画全自動生成 ====="
echo "🔗 URL: $URL"
echo "🛠  ツール: $TOOL_NAME"
echo "📅 日付: $DATE"
echo "📁 出力: $OUTPUT_DIR"
echo ""

mkdir -p "$OUTPUT_DIR/screenshots"

# metadata.json
cat > "$OUTPUT_DIR/metadata.json" << EOF
{
  "toolName": "$TOOL_NAME",
  "pattern": "A",
  "tag": "🤖",
  "url": "$URL"
}
EOF

# --- Phase 1: 台本生成 ---
echo "📝 Phase 1: 台本生成 (GPT-4o)..."
python3 "$SKILL_DIR/scripts/write-script.py" "$URL" "$TOOL_NAME" "$OUTPUT_DIR/script.json"

# --- Phase 2: スクリーンショット ---
echo ""
echo "📸 Phase 2: スクリーンショット撮影..."

# Playwright がなければインストール
if ! python3 -c "from playwright.sync_api import sync_playwright" 2>/dev/null; then
  echo "   Playwright インストール中..."
  pip install playwright -q
  python3 -m playwright install chromium
fi

# メインページと料金ページ
PRICING_URL="${URL%/}/pricing"
python3 "$SKILL_DIR/scripts/screenshot.py" "$OUTPUT_DIR/screenshots" \
  "$URL" \
  "$PRICING_URL" \
  "${URL%/}/features" \
  2>/dev/null || true

SS_COUNT=$(ls "$OUTPUT_DIR/screenshots/"*.png 2>/dev/null | wc -l | tr -d ' ')
echo "   ${SS_COUNT}枚 撮影完了"

# --- Phase 3: TTS ナレーション生成 ---
echo ""
echo "🎙 Phase 3: ナレーション生成 (OpenAI TTS)..."
python3 "$SKILL_DIR/scripts/tts.py" \
  "$OUTPUT_DIR/script.json" \
  "$OUTPUT_DIR/narration.wav"

# --- Phase 4: Remotion動画生成 ---
echo ""
echo "🎥 Phase 4: 動画生成..."
bash "$SKILL_DIR/scripts/render.sh" "$OUTPUT_DIR"

echo ""
echo "🎉 ===== 全自動生成完了! ====="
echo "📁 $OUTPUT_DIR/final-video.mp4"
