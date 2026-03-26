#!/bin/bash
set -e

DIR="$1"
SKILL_DIR="$(cd "$(dirname "$0")/.." && pwd)"

if [ -z "$DIR" ]; then
  echo "Usage: ./render.sh <日付ディレクトリ>"
  echo "例: ./render.sh ~/Videos/daily-shorts/2026-03-24"
  exit 1
fi

# 絶対パスに変換
DIR="$(realpath "$DIR")"

echo "🎬 ===== 動画ビルド開始 ====="
echo "📁 $DIR"
echo ""

# --- Phase 1: 文字起こし ---
NARRATION=""
for f in narration.wav narration.mp3 voice.wav voice.mp3; do
  [ -f "$DIR/$f" ] && NARRATION="$DIR/$f" && break
done

if [ -n "$NARRATION" ]; then
  echo "📝 Phase 1: ナレーション文字起こし..."
  python3 "$SKILL_DIR/scripts/transcribe.py" "$NARRATION" "$DIR/transcript.json"
else
  echo "⚠️  ナレーション音声なし。テロップなしで進めます。"
  echo '{"subtitles":[],"durationSec":0,"fullText":""}' > "$DIR/transcript.json"
fi

# --- Phase 2: episode.json 生成 ---
echo ""
echo "📋 Phase 2: episode.json 生成..."
python3 "$SKILL_DIR/scripts/generate-episode.py" "$DIR"

# --- Phase 3: 素材をRemotionのpublicディレクトリに配置 ---
echo ""
echo "📂 Phase 3: 素材コピー..."
rm -rf "$SKILL_DIR/public/project"
mkdir -p "$SKILL_DIR/public/project"

# 動画ファイル（ハードリンクを試みて失敗したらコピー）
for f in demo-full.mp4 official-demo.mp4; do
  if [ -f "$DIR/$f" ]; then
    ln "$DIR/$f" "$SKILL_DIR/public/project/$f" 2>/dev/null \
      || cp "$DIR/$f" "$SKILL_DIR/public/project/$f"
  fi
done

# スクリーンショット
if [ -d "$DIR/screenshots" ]; then
  cp -r "$DIR/screenshots" "$SKILL_DIR/public/project/"
fi

# ナレーション
if [ -n "$NARRATION" ]; then
  NARRATION_BASENAME=$(basename "$NARRATION")
  ln "$NARRATION" "$SKILL_DIR/public/project/$NARRATION_BASENAME" 2>/dev/null \
    || cp "$NARRATION" "$SKILL_DIR/public/project/$NARRATION_BASENAME"
fi

# episode.json
cp "$DIR/episode.json" "$SKILL_DIR/public/project/"

# actions_timeline.json (あれば)
[ -f "$DIR/actions_timeline.json" ] && cp "$DIR/actions_timeline.json" "$SKILL_DIR/public/project/"

echo "  コピー完了"

# --- Phase 4: Remotionレンダリング ---
echo ""
echo "🎥 Phase 4: Remotion レンダリング..."
cd "$SKILL_DIR"

# episode.jsonからメタデータ読み取り
WIDTH=$(python3 -c "import json; print(json.load(open('$DIR/episode.json'))['meta']['width'])")
HEIGHT=$(python3 -c "import json; print(json.load(open('$DIR/episode.json'))['meta']['height'])")
FPS=$(python3 -c "import json; print(json.load(open('$DIR/episode.json'))['meta']['fps'])")
DURATION_SEC=$(python3 -c "import json; print(json.load(open('$DIR/episode.json'))['meta']['durationSec'])")
DURATION=$(python3 -c "import json; d=json.load(open('$DIR/episode.json')); print(int(d['meta']['durationSec'] * d['meta']['fps']))")

# ブラウザ実行ファイルを自動検出 (Playwright headless_shell を優先)
BROWSER_EXEC=""
for candidate in \
  "$HOME/.cache/ms-playwright/chromium_headless_shell-"*/chrome-linux/headless_shell \
  /usr/bin/google-chrome \
  /usr/bin/chromium; do
  if [ -x "$candidate" ] 2>/dev/null; then
    BROWSER_EXEC="$candidate"
    break
  fi
done
BROWSER_FLAG=""
[ -n "$BROWSER_EXEC" ] && BROWSER_FLAG="--browser-executable $BROWSER_EXEC"

# shellcheck disable=SC2086
npx remotion render src/index.tsx ShortVideo \
  $BROWSER_FLAG \
  --output "$DIR/final-video-noaudio.mp4" \
  --width "$WIDTH" \
  --height "$HEIGHT" \
  --fps "$FPS" \
  --frames "0-$((DURATION - 1))" \
  --codec h264 \
  --crf 18

# --- Phase 5: ナレーション音声ミックス ---
echo ""
echo "🔊 Phase 5: 音声ミックス..."
if [ -n "$NARRATION" ]; then
  ffmpeg -y \
    -i "$DIR/final-video-noaudio.mp4" \
    -i "$NARRATION" \
    -c:v copy \
    -c:a aac -b:a 192k \
    -map 0:v:0 -map 1:a:0 \
    -shortest \
    "$DIR/final-video.mp4" 2>/dev/null
  rm -f "$DIR/final-video-noaudio.mp4"
else
  mv "$DIR/final-video-noaudio.mp4" "$DIR/final-video.mp4"
fi

# --- 完了 ---
echo ""
echo "✅ ===== 動画ビルド完了! ====="
FILESIZE=$(ls -lh "$DIR/final-video.mp4" | awk '{print $5}')
DURATION_ACTUAL=$(ffprobe -v quiet -show_entries format=duration -of csv=p=0 "$DIR/final-video.mp4" 2>/dev/null | cut -d. -f1)
SUBTITLE_COUNT=$(python3 -c "import json; print(len(json.load(open('$DIR/episode.json'))['subtitles']))" 2>/dev/null || echo "0")
SHOT_COUNT=$(python3 -c "import json; print(len(json.load(open('$DIR/episode.json'))['shots']))" 2>/dev/null || echo "0")

echo "📁 $DIR/final-video.mp4"
echo "📐 ${WIDTH}x${HEIGHT} (縦動画)"
echo "⏱  ${DURATION_ACTUAL}秒"
echo "💾 ${FILESIZE}"
echo "📝 テロップ: ${SUBTITLE_COUNT}個"
echo "🎯 ショット: ${SHOT_COUNT}個"
echo ""
echo "💡 微調整: episode.json を編集して再レンダリング可能"
echo "   npx remotion render src/index.ts ShortVideo --output $DIR/final-video.mp4"
