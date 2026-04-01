# B-STUDIO 動画自動生成パイプライン — 仕様書 v10

## 概要

YouTube Shorts用縦動画（1080×1920, 9:16）を全自動生成するシステム。  
URLとツール名を渡すだけで、台本→スクリーンショット→ナレーション→字幕→動画レンダリングまで自動完結する。

---

## ディレクトリ構成

```
beykey/
├── scripts/
│   ├── create-video.sh      # メインパイプライン（エントリポイント）
│   ├── render.sh            # Remotionレンダリング専用
│   ├── daily.sh             # トレンド発掘→生成の全自動ラッパー
│   ├── write-script.py      # 台本生成（LLM）
│   ├── screenshot.py        # スクリーンショット・録画（Playwright）
│   ├── tts.py               # 音声合成（TTS）
│   ├── transcribe.py        # 字幕生成（Whisper）
│   ├── generate-episode.py  # episode.json組み立て
│   ├── generate-clips.py    # AIクリッププロンプト生成
│   └── find-topic.py        # トレンドAIツール発掘
├── src/
│   ├── ShortVideo.tsx       # Remotionメインコンポジション
│   ├── CaptionOverlay.tsx   # 字幕レンダリング（英語大+日本語小）
│   ├── AutoZoom.tsx         # カメラ追従ズーム
│   └── index.ts             # Remotionエントリポイント
├── pregenerated/
│   └── YYYY-MM-DD-script.json  # 事前生成済み台本
└── public/
    └── project/             # レンダリング用素材（自動コピー）
```

---

## パイプライン全体フロー

```
[入力] URL + ツール名 + 日付
          │
          ▼
  ┌─────────────────┐
  │ create-video.sh │
  └────────┬────────┘
           │
    Phase 1: 台本生成
    ├── pregenerated/YYYY-MM-DD-script.json があればスキップ
    └── write-script.py → script.json
           │
    Phase 2: スクリーンショット
    ├── playwright install chromium（毎回バージョン確認）
    ├── screenshot.py → screenshots/*.png（3ページ分）
    └── Playwright失敗時→OG画像フォールバック（重複排除）
           │
    Phase 2b: ブラウザ録画
    ├── script.jsonのactions配列に従い操作しながら録画
    ├── demo-full.mp4 + actions_timeline.json を生成
    └── 失敗時→スクリーンショットのみで続行
           │
    Phase 2c: AIクリッププロンプト生成
    └── generate-clips.py → ai-clips-prompts.txt
           │
    Phase 3: TTS音声生成
    └── tts.py → narration.wav
           │
    Phase 4: レンダリング
    └── render.sh
           ├── transcribe.py → transcript.json
           ├── generate-episode.py → episode.json
           ├── public/project/ へ素材コピー
           ├── npx remotion render → final-video-noaudio.mp4
           └── ffmpeg → final-video.mp4（音声ミックス）

[出力] ~/Videos/daily-shorts/YYYY-MM-DD/final-video.mp4
```

---

## 主要ファイル仕様

### script.json（台本）

```json
{
  "title": "動画タイトル（最大60文字）",
  "lines": [
    {
      "t": 0,
      "endT": 4,
      "en": "English narration text",
      "ja": "日本語字幕（15文字以内）",
      "visualNote": "この行に合わせて見せるべき映像の説明"
    }
    // 10行、合計58秒程度
  ],
  "fullNarration": "全行の英語テキストを連結（TTS用）",
  "actions": [
    {"t": 0,  "type": "navigate", "url": "https://...", "label": "説明"},
    {"t": 8,  "type": "scroll",   "scrollY": 600,       "label": "説明"},
    {"t": 23, "type": "highlight","selector": ".btn",    "label": "説明"}
  ],
  "metadata": {
    "hookType": "result-first | shocking-stat | impossible-claim | free-vs-paid",
    "jawDropMoment": "最も拡散されそなシーンの説明",
    "targetEmotion": "amazement | FOMO | curiosity | urgency"
  }
}
```

**台本構成ルール（10行）:**
| 行 | 役割 | 秒数 | ルール |
|---|---|---|---|
| 1-2 | HOOK | 0-8s | 結果から始める。「今日は〜を紹介」禁止 |
| 3-4 | PROBLEM | 8-18s | 具体的な数字を入れる |
| 5 | REVEAL | 18-23s | ツール名+差別化1文 |
| 6-8 | USE CASES | 23-48s | 基本→テクニック→ジョードロップ と段階的に |
| 9 | RESULT | 48-54s | 変化+価格+緊急性 |
| 10 | CTA | 54-58s | 提供価値に紐づけたフォロー訴求 |

---

### episode.json（レンダリング設定）

```json
{
  "meta": {
    "title": "ツール名",
    "fps": 30,
    "width": 1080,
    "height": 1920,
    "durationSec": 38.8
  },
  "files": {
    "demoVideo": "demo-full.mp4",
    "narration": "narration.wav",
    "screenshots": ["screenshots/01-xxx.png", ...]
  },
  "shots": [
    {
      "id": "hook",
      "startSec": 0,
      "endSec": 2.4,
      "type": "image",        // "image" | "video" | "color"
      "src": "screenshots/03-xxx.png",
      "label": "フック"
    },
    {
      "id": "demo",
      "startSec": 14.5,
      "endSec": 29.1,
      "type": "video",
      "src": "demo-full.mp4",
      "videoStartSec": 14.5
    },
    {
      "id": "cta",
      "startSec": 34.2,
      "endSec": 38.8,
      "type": "color",
      "backgroundColor": "#0f0f1a"
    }
  ],
  "subtitles": [
    {
      "startSec": 0,
      "endSec": 3.8,
      "text": "日本語字幕",
      "textEn": "ENGLISH CAPTION",
      "highlight": ["KEY", "WORD"],
      "emoji": "🎬"
    }
  ],
  "actionsTimeline": [
    {"t": 0, "type": "navigate", "focusX": 540, "focusY": 960, "scale": 1.0},
    {"t": 23, "type": "scroll",  "focusX": 540, "focusY": 600, "scale": 1.2}
  ],
  "aiClips": {
    "hook": "ai-clips/01-hook.mp4",
    "problem": "ai-clips/02-problem.mp4"
  },
  "blendMode": "auto",
  "style": {
    "telop": {
      "fontFamily": "Noto Sans JP",
      "fontSize": 52,
      "fontWeight": "900",
      "color": "#FFFFFF",
      "backgroundColor": "transparent",
      "position": "bottom",
      "marginBottom": 200,
      "accentColor": "#4AACFF"
    },
    "cta": {
      "text": "B-STUDIO\nAI情報を毎日発信中\nフォローして！",
      "fontSize": 42
    },
    "transition": {"type": "fade", "durationFrames": 8},
    "overlay": {
      "topHeight": 160,
      "topColor": "linear-gradient(to bottom, rgba(0,0,0,0.92) 0%, rgba(0,0,0,0) 100%)",
      "logoText": "B-STUDIO",
      "logoFontSize": 42,
      "logoColor": "#FFFFFF",
      "logoImage": "logo.png"
    }
  }
}
```

---

### transcript.json（字幕タイムスタンプ）

```json
{
  "fullText": "All English narration text...",
  "durationSec": 38.8,
  "subtitles": [
    {
      "startSec": 0.0,
      "endSec": 3.8,
      "text": "日本語",
      "textEn": "English text",
      "highlight": ["WORD"],
      "emoji": "🔥"
    }
  ]
}
```

---

### actions_timeline.json（カメラ追従データ）

```json
[
  {"t": 0,  "type": "navigate",  "focusX": 540, "focusY": 960, "scale": 1.0},
  {"t": 8,  "type": "scroll",    "focusX": 540, "focusY": 960, "scale": 1.2},
  {"t": 23, "type": "highlight", "focusX": 320, "focusY": 450, "scale": 1.35}
]
```

---

## Remotionコンポーネント仕様

### ShortVideo.tsx

**Props（episode.jsonから読み込み）:**
- `shots`: Shot配列。type="image"→Ken Burns、type="video"→VideoShot、type="color"→ColorScene
- `subtitles`: CaptionOverlayに渡す
- `actionsTimeline`: 存在すればAutoZoomでwrapする
- `aiClips`: shot.idをキーにAI動画を自動適用（hook/problem/result/ctaが対象）
- `blendMode`: "auto"="browser-only"のいずれか

**レンダリング順序（上から）:**
1. 背景: backgroundColor="#000"
2. TransitionSeries（shots）+ フェードトランジション
3. FrameOverlay（上部グラデーション＋ロゴ）
4. CaptionOverlay（字幕）
5. Audio（narration.wav）

### ColorScene（スクリーンショットなし時のフォールバック）
- ダークグラデーション背景（青+紫のアクセント、ゆっくり移動）
- ツール名を超大文字で薄く背景表示（opacity 0.07）
- CTAショットの場合はctaTextを中央に表示

### CaptionOverlay
- 英語: 52px、UPPERCASE、アクセントカラーで強調ワードをハイライト
- 日本語: 19px（英語の36%）
- 位置: 下から200px
- フェードイン/アウト: 5フレーム
- highlight配列の単語は#4AACFFで表示

### AutoZoom
- actionsTimeline配列を受け取りフレームと録画時刻を同期
- focusX/Y/scaleをEasing.inOut(Easing.ease)で補間
- CSS transform: `translate(cx,cy) scale(s) translate(-focusX,-focusY)`
- transformOrigin: "0 0"

---

## スクリプト詳細

### write-script.py

```bash
python3 scripts/write-script.py <URL> <ツール名> <output.json>
```

**LLMフォールバック順:**
1. Claude Sonnet 4.6（Anthropic SDK）
2. claude CLI（`claude --print`）
3. GPT-4o（OpenAI API）

### screenshot.py

```bash
# スクリーンショット（OGフォールバック付き）
python3 scripts/screenshot.py <output_dir> <url1> [url2] ...

# 通常録画
python3 scripts/screenshot.py <output_dir> --record <output.mp4> <url>

# actions連動録画
python3 scripts/screenshot.py <output_dir> --record-actions <script.json> <output.mp4> <timeline.json>
```

**Playwright chromiumパス（自動検出）:**
- macOS arm64: `~/Library/Caches/ms-playwright/chromium_headless_shell-*/chrome-headless-shell-mac-arm64/chrome-headless-shell`
- macOS x64: `~/Library/Caches/ms-playwright/chromium_headless_shell-*/chrome-headless-shell-mac-x64/chrome-headless-shell`
- Linux: `~/.cache/ms-playwright/chromium_headless_shell-*/chrome-linux/headless_shell`

### tts.py

```bash
python3 scripts/tts.py <script.json> <output.wav> [voice] [speed]
# 例: python3 scripts/tts.py script.json narration.wav onyx 1.15
```

**フォールバック順:** OpenAI TTS → Google AI Studio TTS → gTTS → macOS say → 無音

### transcribe.py

```bash
python3 scripts/transcribe.py <audio.wav> [output.json]
```

**動作:**
- script.jsonのlines配列を検出→英語ライン構成で処理
- Whisperで単語レベルタイムスタンプを取得し精密化
- 連続字幕の重複を排除（前の字幕のendSec > 次のstartSecなら切り詰め）

### generate-episode.py

```bash
python3 scripts/generate-episode.py <日付ディレクトリ>
```

**ショット割り当てロジック:**
| ショット | 割合 | 素材優先順位 |
|---|---|---|
| hook | 0-6% | 最後のSS → デモ末尾 → color |
| problem | 6-19% | 1枚目SS → color |
| intro | 19-38% | デモ先頭 → 1枚目SS → color |
| demo | 38-75% | デモ中間 → 2枚目SS → color |
| result | 75-100% | pricing SS → デモ末尾 → 3枚目SS → color |

**actionsTimeline存在時:** 全ショットを単一のdemo videoショットに統合（AutoZoomが担当）

---

## 環境変数

| 変数 | 必須 | 用途 |
|---|---|---|
| `ANTHROPIC_API_KEY` | 推奨 | 台本生成・字幕翻訳 |
| `OPENAI_API_KEY` | 代替 | 台本生成・TTS・Whisper |
| `GOOGLE_AI_KEY` | オプション | Google TTS（フォールバック） |

---

## 使い方

```bash
# トレンドAIツールを自動発掘して生成
bash scripts/daily.sh

# 自動選択モード（#1を自動ピック）
bash scripts/daily.sh --auto

# URL直指定
bash scripts/create-video.sh https://suno.com "Suno v5.5" 2026-03-31

# 素材が揃っている場合のみ再レンダリング
bash scripts/render.sh ~/Videos/daily-shorts/2026-03-31
```

---

## 既知の制限と対処

| 問題 | 原因 | 対処 |
|---|---|---|
| Playwright chromiumが動かない | バイナリ未インストール | `create-video.sh`が毎回`playwright install chromium`を実行 |
| Playwright失敗時はOG画像のみ | ブラウザ録画なし | 同一URLのOG画像は重複保存しない |
| 録画に59秒かかる | 実際のブラウザ操作を録画 | 仕様（actions配列のt値＋5秒） |
| AIクリップは手動 | Auto Metaへの自動連携なし | `ai-clips-prompts.txt`のプロンプトを手動でAuto Metaに貼り付け→`ai-clips/`に保存→再レンダリング |

---

## episode.jsonを手動編集して再レンダリング

```bash
# episode.jsonを直接編集（ショット差し替え、字幕修正等）
nano ~/Videos/daily-shorts/2026-03-31/episode.json

# 再レンダリングのみ（Phase1-3をスキップ）
npx remotion render src/index.ts ShortVideo \
  --output ~/Videos/daily-shorts/2026-03-31/final-video.mp4
```

---

## AIクリップ追加フロー

1. `~/Videos/daily-shorts/YYYY-MM-DD/ai-clips-prompts.txt` を開く
2. `🎬 AI CLIP` マークのプロンプトをAuto Metaに貼り付けて動画生成
3. ダウンロードして `ai-clips/` フォルダに保存（`01-hook.mp4`, `02-problem.mp4`等）
4. `bash scripts/render.sh ~/Videos/daily-shorts/YYYY-MM-DD` で再レンダリング

---

## 依存ライブラリ

**Python:**
```
requests, playwright, openai, anthropic
```

**Node.js:**
```
remotion ^4.0.438
@remotion/transitions, @remotion/google-fonts, @remotion/cli
react ^19, typescript ^6
```

**システム:**
```
ffmpeg, ffprobe, node 18+, python3 3.9+
```
