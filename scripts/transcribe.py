#!/usr/bin/env python3
"""
ナレーション音声 → タイムスタンプ付きテロップJSON
OpenAI Whisper APIを使用（ローカルWhisperでも可）
"""
import json
import sys
import os


def _add_english_translations(subtitles, api_key):
    """GPT-4o-miniで日本語テロップを一括英訳し textEn / highlight / emoji を追加する"""
    import requests

    if not subtitles or not api_key:
        return subtitles

    texts = [s["text"] for s in subtitles]
    n = len(texts)
    prompt = (
        "以下の日本語テキストを英語に翻訳し、各テロップに強調ワードと絵文字、いらすとや検索キーワードも提案してください。\n\n"
        "ルール:\n"
        "- textEn: 自然な英語訳（短く簡潔に）\n"
        "- highlight: textEn中で強調したい重要単語を1〜2語（大文字で指定）。"
        "全テロップの30〜40%程度に入れる（毎回入れない）\n"
        "- emoji: 文脈に合う絵文字を1つ。全テロップの20〜25%程度のみに入れる"
        "（多すぎるとうるさいので厳選する）。不要な場合はnull\n"
        "- irasutoyaKeyword: いらすとやで検索するための短い日本語キーワード（名詞1〜2語）。"
        "全テロップの40〜50%程度に入れる。視覚的に表現できる具体的な名詞を選ぶ（例: パソコン、スマートフォン、アイデア、困った人、ビジネス）。不要な場合はnull\n\n"
        f"テキスト数: {n}件\n"
        f"日本語テキスト:\n{json.dumps(texts, ensure_ascii=False)}\n\n"
        "出力（JSONのみ）:\n"
        '{"items": [{"textEn": "...", "highlight": ["WORD"], "emoji": "🔥", "irasutoyaKeyword": "パソコン"}, ...]}'
    )

    try:
        resp = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "gpt-4o-mini",
                "messages": [{"role": "user", "content": prompt}],
                "response_format": {"type": "json_object"},
                "temperature": 0.4,
            },
            timeout=60,
        )
        if resp.status_code != 200:
            print(f"⚠️ 英訳APIエラー: {resp.status_code} — 日本語のみで続行")
            return subtitles

        data = json.loads(resp.json()["choices"][0]["message"]["content"])
        items = data.get("items", [])
        for i, sub in enumerate(subtitles):
            if i >= len(items):
                break
            item = items[i]
            sub["textEn"] = item.get("textEn", "")
            hl = item.get("highlight") or []
            if hl:
                sub["highlight"] = [w.upper() for w in hl]
            em = item.get("emoji")
            if em:
                sub["emoji"] = em
            kw = item.get("irasutoyaKeyword")
            if kw:
                sub["irasutoyaKeyword"] = kw
        print(f"   英訳追加: {len(items)}件")
    except Exception as e:
        print(f"⚠️ 英訳スキップ ({e})")

    return subtitles


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

    # 英訳を追加
    subtitles = _add_english_translations(subtitles, api_key)

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
