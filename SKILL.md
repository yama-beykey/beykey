---
name: creator-video-builder
description: >
  素材（録画 + ナレーション音声）を渡すだけで、テロップ・映像切り替え・
  縦動画(1080x1920)の最終動画ファイルを書き出す。
  Remotion公式Agent Skills使用。episode.jsonで編集データを一元管理。
  creator-demo-recorderとcreator-script-writerの後に実行される。
---

# Creator Video Builder

## 前提条件

- Remotion + 公式Skills (`npx skills add remotion-dev/skills`)
- FFmpeg, Python 3, OpenAI API Key (Whisper用)
- Noto Sans JP フォント（@remotion/google-fontsで自動ロード）

## 使い方

### Naoyaがナレーションを収録した後:

```bash
bash scripts/render.sh ~/Videos/daily-shorts/YYYY-MM-DD/
```

### 処理フロー

1. **Whisper** → ナレーション文字起こし (`transcript.json`)
2. **episode.json 生成** (`metadata.json` + `transcript.json` + 素材情報を統合)
3. **素材リンク** → Remotionの `public/project/` に配置
4. **Remotionレンダリング** → 縦動画 1080x1920
5. **ナレーション音声ミックス** → `final-video.mp4`

### episode.json で微調整可能

AIが自動生成した `episode.json` を手動で編集できる:

- ショットの順番・尺を変更
- テロップのテキストを修正
- スタイル（フォントサイズ、色）を調整
- トランジションの種類を変更

編集後、再度レンダリング:

```bash
npx remotion render src/index.ts ShortVideo \
  --output ~/Videos/daily-shorts/YYYY-MM-DD/final-video.mp4 \
  --width 1080 --height 1920 --fps 30
```

## プロジェクト構造

```
creator-video-builder/
├── src/
│   ├── index.ts           # Remotionルート（Composition定義）
│   ├── ShortVideo.tsx     # メインコンポジション（縦動画 1080x1920）
│   └── CaptionOverlay.tsx # テロップコンポーネント
├── scripts/
│   ├── transcribe.py      # Whisper文字起こし
│   ├── generate-episode.py # episode.json生成
│   └── render.sh          # ワンコマンドビルド
├── public/
│   └── project/           # 素材の一時置き場（シンボリックリンク）
├── .agents/skills/
│   └── remotion-best-practices/  # Remotion公式Skills
└── SKILL.md               # このファイル
```

## 入力ファイル構造

```
~/Videos/daily-shorts/YYYY-MM-DD/
├── metadata.json          # ツール名・パターン・タグ等
├── demo-full.mp4          # 録画映像（creator-demo-recorderが生成）
├── narration.wav          # ナレーション音声（Naoyaが収録）
├── screenshots/           # スクリーンショット（任意）
│   ├── 01-top.png
│   ├── 02-features.png
│   └── 03-pricing.png
└── script.md              # 台本（creator-script-writerが生成）
```

## 出力

```
~/Videos/daily-shorts/YYYY-MM-DD/
├── （既存ファイル群）
├── transcript.json        # Whisper文字起こし
├── episode.json           # ★編集データのハブ（AI/人間どちらも編集可）
└── final-video.mp4        # 最終動画 1080x1920 縦動画
```

## metadata.json の形式

```json
{
  "toolName": "ToolName",
  "pattern": "A",
  "tag": "🎬"
}
```

## Remotionコンポジション設計

### ShortVideo.tsx の構成

- **TransitionSeries** でショット間フェードトランジション
- **VideoShot**: `<Video>` で映像クリップを `videoStartSec` から切り出し
- **KenBurnsImage**: `<Img>` + `interpolate()` でズーム＆パン
- **ColorScene**: 単色背景（CTA・問題提起に使用）
- **CaptionOverlay**: Whisperタイムスタンプに同期したテロップ

### 縦動画レイアウト

```
1080 x 1920 px (9:16)
┌─────────────────┐
│                 │
│   映像クリップ    │
│   or スクショ    │
│   (Ken Burns)   │
│                 │
│                 │
│ ┌─────────────┐ │ ← テロップ (marginBottom: 180px)
│ │  テロップ    │ │
│ └─────────────┘ │
│                 │ ← CTAボタン領域（180px確保）
└─────────────────┘
```

## Remotion公式Skillsのルール（重要）

- **CSSアニメーション禁止** → `useCurrentFrame()` + `interpolate()` を使う
- **`spring()`** でバネアニメーション
- **`Sequence`** には `premountFor={fps}` を付ける
- **`staticFile()`** でpublicフォルダのアセットを参照
- **`<Img>`, `<Video>`, `<Audio>`** はRemotionのコンポーネントを使う（HTMLタグ禁止）

## Telegram通知テンプレート

```
🎬 最終動画が完成しました!
📁 ~/Videos/daily-shorts/YYYY-MM-DD/final-video.mp4
📐 1080x1920 (縦動画)
⏱ XX秒
📝 テロップ: XX個
🎯 ショット: XX個
💡 微調整: episode.json を編集して再レンダリング可能
→ 確認して投稿してください
```
