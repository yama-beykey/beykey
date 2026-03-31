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

if [ -z "$OPENAI_API_KEY" ] && [ -z "$ANTHROPIC_API_KEY" ]; then
  echo "❌ API キーが設定されていません"
  echo "   export ANTHROPIC_API_KEY='sk-ant-...'  (推奨)"
  echo "   または"
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

# --- Python依存パッケージ確認 ---
python3 -c "import requests" 2>/dev/null || python3 -m pip install requests -q --break-system-packages 2>/dev/null || python3 -m pip install requests -q --user
python3 -c "import openai" 2>/dev/null || python3 -m pip install openai -q --break-system-packages 2>/dev/null || python3 -m pip install openai -q --user

# --- Phase 1: 台本生成 ---
echo "📝 Phase 1: 台本生成 (GPT-4o)..."
python3 "$SKILL_DIR/scripts/write-script.py" "$URL" "$TOOL_NAME" "$OUTPUT_DIR/script.json"

# --- Phase 2: スクリーンショット ---
echo ""
echo "📸 Phase 2: スクリーンショット撮影..."

# Playwright がなければインストール
if ! python3 -c "from playwright.sync_api import sync_playwright" 2>/dev/null; then
  echo "   Playwright インストール中..."
  python3 -m pip install playwright -q --break-system-packages 2>/dev/null || python3 -m pip install playwright -q --user
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

# --- Phase 2b: actions に沿ったブラウザ操作録画 ---
echo ""
echo "🎬 Phase 2b: ブラウザ操作録画 (Playwright + actions)..."

# script.json に actions があれば record_with_actions、なければ通常録画
if python3 -c "import json,sys; d=json.load(open('$OUTPUT_DIR/script.json')); sys.exit(0 if d.get('actions') else 1)" 2>/dev/null; then
  python3 "$SKILL_DIR/scripts/screenshot.py" "$OUTPUT_DIR/screenshots" \
    --record-actions \
    "$OUTPUT_DIR/script.json" \
    "$OUTPUT_DIR/demo-full.mp4" \
    "$OUTPUT_DIR/actions_timeline.json" \
    2>/dev/null || echo "   ⚠️  操作録画スキップ（スクリーンショットのみで続行）"
else
  # フォールバック: 通常スクロール録画
  python3 "$SKILL_DIR/scripts/screenshot.py" "$OUTPUT_DIR/screenshots" \
    --record "$OUTPUT_DIR/demo-full.mp4" \
    "$URL" \
    2>/dev/null || echo "   ⚠️  録画スキップ（スクリーンショットのみで続行）"
fi

if [ -f "$OUTPUT_DIR/demo-full.mp4" ]; then
  echo "   ✅ 録画完了"
  [ -f "$OUTPUT_DIR/actions_timeline.json" ] && echo "   📍 actionsTimeline 生成済み"
else
  echo "   ℹ️  録画なし — スクリーンショットで代替"
fi

# --- Phase 2c: AI動画クリッププロンプト生成 ---
echo ""
echo "🎬 Phase 2c: AI動画プロンプト生成..."
python3 "$SKILL_DIR/scripts/generate-clips.py" "$OUTPUT_DIR"
echo ""
echo "📋 Auto Meta 手順:"
echo "   1. $OUTPUT_DIR/ai-clips-prompts.txt を開く"
echo "   2. 🎬 AI CLIP のプロンプトを Auto Meta に貼り付けて生成"
echo "   3. 生成したクリップを $OUTPUT_DIR/ai-clips/ に保存"
echo "   (スキップして進めた場合はブラウザ録画のみで動画を生成)"
echo ""

# --- Phase 3: TTS ナレーション生成 ---
echo ""
echo "🎙 Phase 3: ナレーション生成 (OpenAI TTS / macOS say)..."
python3 "$SKILL_DIR/scripts/tts.py" \
  "$OUTPUT_DIR/script.json" \
  "$OUTPUT_DIR/narration.wav" \
  "onyx" \
  1.15

# --- Phase 4: Remotion動画生成 ---
echo ""
echo "🎥 Phase 4: 動画生成..."
bash "$SKILL_DIR/scripts/render.sh" "$OUTPUT_DIR"

echo ""
echo "🎉 ===== 全自動生成完了! ====="
echo "📁 $OUTPUT_DIR/final-video.mp4"
