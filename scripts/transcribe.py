#!/usr/bin/env python3
"""
ナレーション音声 → タイムスタンプ付きテロップJSON
OpenAI Whisper APIを使用（ローカルWhisperでも可）
"""
import json
import sys
import os


def _call_llm(prompt, temperature=0.4):
    """Claude API を優先、失敗時は OpenAI にフォールバック"""
    import requests as _requests
    try:
        import anthropic as _anthropic
        client = _anthropic.Anthropic()
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.content[0].text
    except Exception as e:
        print(f"   Claude API 失敗: {e}。OpenAI にフォールバック...")

    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        return None
    resp = _requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={"model": "gpt-4o-mini", "messages": [{"role": "user", "content": prompt}],
              "response_format": {"type": "json_object"}, "temperature": temperature},
        timeout=60,
    )
    if resp.status_code != 200:
        return None
    return resp.json()["choices"][0]["message"]["content"]


def _add_english_translations(subtitles, api_key=None):
    """Claude/GPT-4o-miniで日本語テロップを一括英訳し textEn / highlight / emoji を追加する"""
    if not subtitles:
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
        content = _call_llm(prompt, temperature=0.4)
        if not content:
            return subtitles
        import re as _re
        m = _re.search(r"```json\s*([\s\S]*?)```", content)
        if m:
            content = m.group(1)
        else:
            s = content.find("{"); e = content.rfind("}") + 1
            if s >= 0 and e > s:
                content = content[s:e]
        data = json.loads(content)
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
    import subprocess

    api_key = os.environ.get("OPENAI_API_KEY", "")

    # Whisper API 試行
    whisper_ok = False
    result = None
    if api_key:
        try:
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
                    timeout=120,
                )
            if resp.status_code == 200:
                result = resp.json()
                whisper_ok = True
            else:
                print(f"⚠️ Whisper API: {resp.status_code} — 代替タイムスタンプ推定に切り替え")
        except Exception as e:
            print(f"⚠️ Whisper 接続失敗: {e} — 代替タイムスタンプ推定に切り替え")

    # ffprobe で音声の長さを取得
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
             "-of", "csv=p=0", audio_path],
            capture_output=True, text=True,
        )
        audio_duration = float(r.stdout.strip())
    except Exception:
        audio_duration = 30.0

    words = result.get("words", []) if result else []

    # 日本語テロップ用: 句読点・文末で区切り、1行15文字以内を目安に
    subtitles = []

    if words:
        # Whisper から word タイムスタンプがある場合
        group = []
        group_start = 0
        char_count = 0
        for w in words:
            if not group:
                group_start = w["start"]
            group.append(w["word"])
            char_count += len(w["word"])
            is_punctuation = w["word"].rstrip().endswith(
                ("。", "、", "？", "！", ".", ",", "?", "!")
            )
            if char_count >= 15 or is_punctuation:
                subtitles.append({
                    "startSec": round(group_start, 2),
                    "endSec": round(w["end"], 2),
                    "text": "".join(group).strip(),
                })
                group = []
                char_count = 0
        if group:
            subtitles.append({
                "startSec": round(group_start, 2),
                "endSec": round(words[-1]["end"], 2),
                "text": "".join(group).strip(),
            })
    else:
        # タイムスタンプなし: script.json から推定タイムスタンプを生成
        script_json_path = os.path.join(os.path.dirname(audio_path), "script.json")
        full_text = ""
        if result:
            full_text = result.get("text", "")
        if not full_text and os.path.exists(script_json_path):
            with open(script_json_path, encoding="utf-8") as f:
                sc = json.load(f)
            full_text = sc.get("fullNarration", "")
            print(f"   script.json から fullNarration を使用 ({len(full_text)}文字)")

        if full_text:
            # 15文字区切りで均等にタイムスタンプを割り当て
            chars_per_sec = len(full_text) / max(audio_duration, 1)
            chunk_size = 15
            pos = 0
            while pos < len(full_text):
                chunk = full_text[pos:pos + chunk_size]
                start_sec = pos / chars_per_sec
                end_sec = (pos + len(chunk)) / chars_per_sec
                subtitles.append({
                    "startSec": round(start_sec, 2),
                    "endSec": round(end_sec, 2),
                    "text": chunk.strip(),
                })
                pos += chunk_size

    # 英訳・いらすとやキーワードを追加
    subtitles = _add_english_translations(subtitles)

    output = {
        "fullText": result.get("text", "") if result else "",
        "durationSec": result.get("duration", audio_duration) if result else audio_duration,
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
