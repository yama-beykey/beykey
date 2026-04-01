#!/bin/bash
# ============================================================
# make.sh — 原稿と素材から動画を生成する
#
# 用意するもの（DIRに置く）:
#   script.json          ← 原稿（必須）
#   demo-full.mp4        ← 録画（オプション）
#   screenshots/*.png    ← 静止画（オプション）
#   ai-clips/*.mp4       ← AIクリップ（オプション）
#
# 使い方:
#   bash scripts/make.sh ~/Videos/daily-shorts/2026-03-31
# ============================================================
set -e

DIR="${1:-}"
SKILL_DIR="$(cd "$(dirname "$0")/.." && pwd)"

if [ -z "$DIR" ]; then
  echo "Usage: bash scripts/make.sh <ディレクトリ>"
  echo "例:    bash scripts/make.sh ~/Videos/daily-shorts/2026-03-31"
  exit 1
fi

DIR="$(realpath "$DIR")"

if [ ! -f "$DIR/script.json" ]; then
  echo "❌ script.json が見つかりません: $DIR/script.json"
  exit 1
fi

echo "🎬 ===== 動画生成 ====="
echo "📁 $DIR"

# metadata.json がなければ script.json のタイトルから生成
if [ ! -f "$DIR/metadata.json" ]; then
  TITLE=$(python3 -c "import json; print(json.load(open('$DIR/script.json')).get('title','Video'))" 2>/dev/null || echo "Video")
  cat > "$DIR/metadata.json" << EOF
{"toolName": "$TITLE", "pattern": "A", "tag": "🤖"}
EOF
fi

# TTS生成（narration.wav/mp3 がなければ）
NARRATION_EXISTS=false
for f in narration.wav narration.mp3 voice.wav voice.mp3; do
  [ -f "$DIR/$f" ] && NARRATION_EXISTS=true && break
done

if [ "$NARRATION_EXISTS" = false ]; then
  echo ""
  echo "🎙 ナレーション生成..."
  python3 -c "import openai" 2>/dev/null \
    || python3 -m pip install openai -q --break-system-packages 2>/dev/null \
    || python3 -m pip install openai -q --user
  python3 "$SKILL_DIR/scripts/tts.py" \
    "$DIR/script.json" \
    "$DIR/narration.wav" \
    "onyx" \
    1.15
else
  echo "⏩ ナレーションスキップ（既存ファイルを使用）"
fi

# レンダリング
echo ""
bash "$SKILL_DIR/scripts/render.sh" "$DIR"
