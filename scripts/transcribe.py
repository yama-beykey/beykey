#!/usr/bin/env python3
"""
ナレーション音声 → タイムスタンプ付きテロップJSON
OpenAI Whisper APIを使用（ローカルWhisperでも可）
"""
import json
import sys
import os


def transcribe(audio_path, output_path):
    import requests

    # OpenAI APIキー取得（環境変数 or OpenClawのconfig）
    api_key = os.environ.get("OPENAI_API_KEY", "")

    if not api_key:
        config_paths = [
            os.path.expanduser("~/.openclaw/config.json"),
            os.path.expanduser("~/.config/openclaw/config.json"),
        ]
        for cp in config_paths:
            if os.path.exists(cp):
                with open(cp) as f:
                    cfg = json.load(f)
                # OpenClawの設定構造に合わせてキーを取得
                providers = cfg.get("models", {}).get("providers", {})
                for provider in providers.values():
                    if isinstance(provider, dict) and provider.get("apiKey"):
                        api_key = provider["apiKey"]
                        break
                if api_key:
                    break

    if not api_key:
        print("❌ OPENAI_API_KEY が見つかりません")
        sys.exit(1)

    with open(audio_path, "rb") as f:
        resp = requests.post(
            "https://api.openai.com/v1/audio/transcriptions",
            headers={"Authorization": f"Bearer {api_key}"},
            files={"file": f},
            data={
                "model": "whisper-1",
                "response_format": "verbose_json",
                "timestamp_granularities[]": "word",
                "language": "ja",
            },
        )

    if resp.status_code != 200:
        print(f"❌ Whisper API error: {resp.status_code} {resp.text}")
        sys.exit(1)

    result = resp.json()
    words = result.get("words", [])

    # 日本語テロップ用: 句読点・文末で区切り、1行15文字以内を目安に
    subtitles = []
    group = []
    group_start = 0
    char_count = 0

    for w in words:
        if not group:
            group_start = w["start"]
        group.append(w["word"])
        char_count += len(w["word"])

        # 区切り条件: 15文字以上 or 句読点
        is_punctuation = w["word"].rstrip().endswith(
            ("。", "、", "？", "！", ".", ",", "?", "!")
        )
        if char_count >= 15 or is_punctuation:
            subtitles.append(
                {
                    "startSec": round(group_start, 2),
                    "endSec": round(w["end"], 2),
                    "text": "".join(group).strip(),
                }
            )
            group = []
            char_count = 0

    if group:
        subtitles.append(
            {
                "startSec": round(group_start, 2),
                "endSec": round(words[-1]["end"], 2),
                "text": "".join(group).strip(),
            }
        )

    output = {
        "fullText": result.get("text", ""),
        "durationSec": result.get("duration", 0),
        "subtitles": subtitles,
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(
        f"✅ 文字起こし完了: {len(subtitles)}テロップ, {output['durationSec']:.1f}秒"
    )


if __name__ == "__main__":
    transcribe(
        sys.argv[1],
        sys.argv[2] if len(sys.argv) > 2 else "transcript.json",
    )
