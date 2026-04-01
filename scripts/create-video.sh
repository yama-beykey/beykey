#!/bin/bash
# ============================================================
# create-video.sh — URLを渡すだけで縦動画を全自動生成
#
# 使い方: bash scripts/create-video.sh <URL> <ツール名> [日付]
# 例:     bash scripts/create-video.sh https://suno.com "Suno v5.5" 2026-03-31
#
# 素材を手動で用意する場合（Playwright不要）:
#   ~/Videos/daily-shorts/YYYY-MM-DD/demo-full.mp4   → 録画を置く
#   ~/Videos/daily-shorts/YYYY-MM-DD/screenshots/    → 画像を置く
#   ※ 上記が存在すればPhase2・2bは自動スキップ
# ============================================================
set -e

URL="$1"
TOOL_NAME="$2"
DATE="${3:-$(date +%Y-%m-%d)}"
SKILL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
OUTPUT_DIR="$HOME/Videos/daily-shorts/$DATE"

if [ -z "$URL" ] || [ -z "$TOOL_NAME" ]; then
  echo "Usage: bash scripts/create-video.sh <URL> <ツール名> [日付]"
  echo "例: bash scripts/create-video.sh https://suno.com \"Suno v5.5\" 2026-03-31"
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
PREGENERATED="$SKILL_DIR/pregenerated/$DATE-script.json"
if [ -f "$OUTPUT_DIR/script.json" ]; then
  echo "⏩ Phase 1: 台本スキップ（既存の script.json を使用）"
elif [ -f "$PREGENERATED" ]; then
  echo "⏩ Phase 1: 台本スキップ（pregenerated から使用）"
  cp "$PREGENERATED" "$OUTPUT_DIR/script.json"
else
  echo "📝 Phase 1: 台本生成 (Claude / GPT-4o)..."
  python3 "$SKILL_DIR/scripts/write-script.py" "$URL" "$TOOL_NAME" "$OUTPUT_DIR/script.json"
fi

# --- Phase 2: スクリーンショット ---
# 手動で screenshots/ に画像がある場合はスキップ
echo ""
SS_MANUAL=$(find "$OUTPUT_DIR/screenshots/" -type f \( -name "*.png" -o -name "*.jpg" -o -name "*.jpeg" -o -name "*.webp" \) 2>/dev/null | wc -l | tr -d ' ')

if [ "$SS_MANUAL" -gt 0 ]; then
  echo "⏩ Phase 2: スクリーンショットスキップ（手動素材 ${SS_MANUAL}枚 を使用）"
else
  echo "📸 Phase 2: スクリーンショット自動撮影..."
  if ! python3 -c "from playwright.sync_api import sync_playwright" 2>/dev/null; then
    python3 -m pip install playwright -q --break-system-packages 2>/dev/null || python3 -m pip install playwright -q --user
  fi
  echo "   Chromium確認中..."
  python3 -m playwright install chromium 2>&1 | grep -E "(Downloading|chromium)" | head -3 || true

  PRICING_URL="${URL%/}/pricing"
  python3 "$SKILL_DIR/scripts/screenshot.py" "$OUTPUT_DIR/screenshots" \
    "$URL" "$PRICING_URL" "${URL%/}/features"

  SS_MANUAL=$(find "$OUTPUT_DIR/screenshots/" -type f \( -name "*.png" -o -name "*.jpg" -o -name "*.jpeg" -o -name "*.webp" \) 2>/dev/null | wc -l | tr -d ' ')
  echo "   ${SS_MANUAL}枚 撮影完了"
fi

# --- Phase 2b: ブラウザ操作録画 ---
# 手動で demo-full.mp4 がある場合はスキップ
echo ""
if [ -f "$OUTPUT_DIR/demo-full.mp4" ]; then
  echo "⏩ Phase 2b: 録画スキップ（手動素材 demo-full.mp4 を使用）"
  [ -f "$OUTPUT_DIR/actions_timeline.json" ] && echo "   📍 actionsTimeline あり"
else
  echo "🎬 Phase 2b: ブラウザ操作録画 (Playwright)..."
  if python3 -c "import json,sys; d=json.load(open('$OUTPUT_DIR/script.json')); sys.exit(0 if d.get('actions') else 1)" 2>/dev/null; then
    python3 "$SKILL_DIR/scripts/screenshot.py" "$OUTPUT_DIR/screenshots" \
      --record-actions \
      "$OUTPUT_DIR/script.json" \
      "$OUTPUT_DIR/demo-full.mp4" \
      "$OUTPUT_DIR/actions_timeline.json" \
      || echo "   ⚠️  操作録画スキップ（スクリーンショットのみで続行）"
  else
    python3 "$SKILL_DIR/scripts/screenshot.py" "$OUTPUT_DIR/screenshots" \
      --record "$OUTPUT_DIR/demo-full.mp4" "$URL" \
      || echo "   ⚠️  録画スキップ（スクリーンショットのみで続行）"
  fi
  [ -f "$OUTPUT_DIR/demo-full.mp4" ] && echo "   ✅ 録画完了" || echo "   ℹ️  録画なし"
fi

# --- Phase 2c: AI動画クリッププロンプト生成 ---
echo ""
echo "🎬 Phase 2c: AI動画プロンプト生成..."
python3 "$SKILL_DIR/scripts/generate-clips.py" "$OUTPUT_DIR"
echo ""
echo "   💡 AIクリップを追加する場合:"
echo "      1. $OUTPUT_DIR/ai-clips-prompts.txt のプロンプトをAuto Metaで生成"
echo "      2. $OUTPUT_DIR/ai-clips/ に保存（01-hook.mp4 等）"
echo "      3. bash scripts/render.sh $OUTPUT_DIR で再レンダリング"
echo ""

# --- Phase 3: TTS ナレーション生成 ---
echo "🎙 Phase 3: ナレーション生成..."
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
echo "🎉 ===== 完了! ====="
echo "📁 $OUTPUT_DIR/final-video.mp4"


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
# pregenerated/ に今日付きの台本があればコピーして使う
PREGENERATED="$SKILL_DIR/pregenerated/$DATE-script.json"
if [ -f "$OUTPUT_DIR/script.json" ]; then
  echo "⏩ Phase 1: 台本スキップ（既存の script.json を使用）"
elif [ -f "$PREGENERATED" ]; then
  echo "⏩ Phase 1: 台本スキップ（pregenerated から使用: $PREGENERATED）"
  cp "$PREGENERATED" "$OUTPUT_DIR/script.json"
else
  echo "📝 Phase 1: 台本生成 (Claude / GPT-4o)..."
  python3 "$SKILL_DIR/scripts/write-script.py" "$URL" "$TOOL_NAME" "$OUTPUT_DIR/script.json"
fi

# --- Phase 2: スクリーンショット ---
echo ""
echo "📸 Phase 2: スクリーンショット撮影..."

# Playwright Pythonモジュールがなければインストール
if ! python3 -c "from playwright.sync_api import sync_playwright" 2>/dev/null; then
  echo "   Playwright インストール中..."
  python3 -m pip install playwright -q --break-system-packages 2>/dev/null || python3 -m pip install playwright -q --user
fi

# Chromiumを常に最新バージョンで確認・インストール（Playwright自身がバージョン管理）
# 複雑な検出ロジックは使わない — 既に正しいバージョンがあれば瞬時にスキップされる
echo "   Chromium確認中..."
python3 -m playwright install chromium 2>&1 | grep -E "(Downloading|Playwright|Browser|chromium)" | head -3 || true

# メインページと料金ページ
PRICING_URL="${URL%/}/pricing"
python3 "$SKILL_DIR/scripts/screenshot.py" "$OUTPUT_DIR/screenshots" \
  "$URL" \
  "$PRICING_URL" \
  "${URL%/}/features"

SS_COUNT=$(find "$OUTPUT_DIR/screenshots/" -type f \( -name "*.png" -o -name "*.jpg" -o -name "*.jpeg" -o -name "*.webp" \) 2>/dev/null | wc -l | tr -d ' ')
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
    || echo "   ⚠️  操作録画スキップ（スクリーンショットのみで続行）"
else
  # フォールバック: 通常スクロール録画
  python3 "$SKILL_DIR/scripts/screenshot.py" "$OUTPUT_DIR/screenshots" \
    --record "$OUTPUT_DIR/demo-full.mp4" \
    "$URL" \
    || echo "   ⚠️  録画スキップ（スクリーンショットのみで続行）"
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
