#!/usr/bin/env python3
"""
ナレーション音声 → タイムスタンプ付きテロップJSON

英語ナレーション対応:
- script.json に "lines" (t / endT / en / ja) がある場合 → それをベースに字幕生成
  - 実際の音声長に合わせてタイムスタンプをスケーリング
  - Whisper が使える場合はより精密なタイムスタンプに置き換え
- "lines" がない場合（旧フォーマット）→ 従来の日本語テロップ生成
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


def _get_audio_duration(audio_path):
    import subprocess
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
             "-of", "csv=p=0", audio_path],
            capture_output=True, text=True,
        )
        return float(r.stdout.strip())
    except Exception:
        return 38.0


def _build_subtitles_from_lines(lines, actual_duration):
    """
    script.json の lines (t/endT/en/ja) から字幕を生成。
    推定合計尺 vs 実際の音声長の比でタイムスタンプをスケーリング。
    """
    if not lines:
        return []

    estimated_total = lines[-1].get("endT", 38)
    scale = actual_duration / max(estimated_total, 1)

    subtitles = []
    for line in lines:
        en = line.get("en", "")
        ja = line.get("ja", "")
        if not en and not ja:
            continue
        start = round(line.get("t", 0) * scale, 2)
        end = round(line.get("endT", line.get("t", 0) + 3) * scale, 2)

        # highlight: 大文字・強調語（AIツール名・動詞・数字）を自動抽出
        highlight = _extract_highlight_words(en)

        item = {
            "startSec": start,
            "endSec": end,
            "text": ja,
            "textEn": en,
        }
        if highlight:
            item["highlight"] = highlight
        subtitles.append(item)

    return subtitles


def _extract_highlight_words(en_text):
    """
    英語テキストから強調すべき単語を抽出する。
    - 大文字の略語 (AI, API, FREE, etc.)
    - 数字を含む語 (10x, $20, etc.)
    - 動詞・ key action words
    """
    import re
    if not en_text:
        return []

    ACTION_WORDS = {
        "AUTOMATE", "FREE", "INSTANTLY", "CONTROL", "BUILD",
        "GENERATE", "TRANSFORM", "CREATE", "UNLIMITED", "POWER",
        "CLICK", "OPEN", "FILL", "PULL", "CONNECT", "INSTALL",
        "ANYTHING", "EVERYTHING", "FULL", "REAL", "NEW", "JUST",
    }

    words = re.findall(r"[A-Za-z0-9$%+\-]+", en_text)
    highlighted = []
    for w in words:
        upper = w.upper()
        if upper in ACTION_WORDS:
            highlighted.append(upper)
        elif re.search(r"\d", w):  # 数字含む
            highlighted.append(upper)
        elif w.isupper() and len(w) >= 2:  # 大文字略語
            highlighted.append(upper)

    # 1ライン最大2語まで
    seen = []
    for w in highlighted:
        if w not in seen:
            seen.append(w)
        if len(seen) >= 2:
            break
    return seen


def _refine_with_whisper(subtitles, lines, result):
    """
    Whisper の word タイムスタンプを使って字幕の startSec / endSec を精密化する。
    lines の en テキストとの照合で各ラインの開始・終了フレームを特定。
    """
    words = result.get("words", [])
    if not words or not lines:
        return subtitles

    # words を全文として結合し、各ラインの英語テキストが何番目の単語か探す
    all_words_lower = [w["word"].strip().lower().strip(".,!?") for w in words]

    for i, line in enumerate(lines):
        en_words = [w.lower().strip(".,!?") for w in line.get("en", "").split() if w]
        if not en_words:
            continue

        # 最初の単語でスタート位置を探す
        for start_idx in range(len(all_words_lower)):
            if all_words_lower[start_idx] == en_words[0]:
                # ラインの単語列がここから始まるか確認
                end_idx = start_idx + len(en_words) - 1
                if end_idx < len(words):
                    subtitles[i]["startSec"] = round(words[start_idx]["start"], 2)
                    subtitles[i]["endSec"] = round(words[end_idx]["end"], 2)
                    break

    return subtitles


def _build_subtitles_japanese(words, full_text, audio_duration):
    """旧フォーマット（日本語台本）用: 句読点区切りで字幕生成"""
    subtitles = []

    if words:
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
    elif full_text:
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

    return subtitles


def _add_english_translations(subtitles, api_key=None):
    """旧フォーマット用: 日本語テロップを英訳して textEn / highlight / emoji を追加"""
    if not subtitles:
        return subtitles

    texts = [s["text"] for s in subtitles]
    n = len(texts)
    prompt = (
        "以下の日本語テキストを英語に翻訳し、各テロップに強調ワードと絵文字を提案してください。\n\n"
        "ルール:\n"
        "- textEn: 自然な英語訳（短く簡潔に）\n"
        "- highlight: textEn中で強調したい重要単語を1〜2語（大文字で指定）\n"
        "- emoji: 文脈に合う絵文字を1つ。全テロップの20〜25%程度のみに入れる（不要な場合はnull）\n\n"
        f"テキスト数: {n}件\n"
        f"日本語テキスト:\n{json.dumps(texts, ensure_ascii=False)}\n\n"
        "出力（JSONのみ）:\n"
        '{"items": [{"textEn": "...", "highlight": ["WORD"], "emoji": "🔥"}, ...]}'
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
        print(f"   英訳追加: {len(items)}件")
    except Exception as e:
        print(f"⚠️ 英訳スキップ ({e})")

    return subtitles


def transcribe(audio_path, output_path):
    import requests
    import subprocess

    api_key = os.environ.get("OPENAI_API_KEY", "")

    # 音声の長さを取得
    audio_duration = _get_audio_duration(audio_path)

    # script.json を確認 — 英語ライン構成かどうかチェック
    script_json_path = os.path.join(os.path.dirname(audio_path), "script.json")
    script_lines = None
    if os.path.exists(script_json_path):
        with open(script_json_path, encoding="utf-8") as f:
            sc = json.load(f)
        if sc.get("lines"):
            script_lines = sc["lines"]
            print(f"   📋 英語ライン構成を検出: {len(script_lines)}行")

    # ===== 英語ライン構成の場合 =====
    if script_lines:
        subtitles = _build_subtitles_from_lines(script_lines, audio_duration)

        # Whisper が使える場合はタイムスタンプを精密化
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
                            "language": "en",
                        },
                        timeout=120,
                    )
                if resp.status_code == 200:
                    result = resp.json()
                    subtitles = _refine_with_whisper(subtitles, script_lines, result)
                    audio_duration = result.get("duration", audio_duration)
                    print(f"   ✅ Whisper タイムスタンプ精密化完了")
                else:
                    print(f"   ℹ️  Whisper スキップ ({resp.status_code}) — スクリプトタイムスタンプを使用")
            except Exception as e:
                print(f"   ℹ️  Whisper スキップ ({e}) — スクリプトタイムスタンプを使用")

        output = {
            "fullText": " ".join(l.get("en", "") for l in script_lines),
            "durationSec": audio_duration,
            "subtitles": subtitles,
        }
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)

        print(f"✅ 字幕生成完了: {len(subtitles)}テロップ, {audio_duration:.1f}秒 (英語ライン構成)")
        return

    # ===== 旧フォーマット（日本語台本）の場合 =====
    result = None
    full_text = ""
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
                audio_duration = result.get("duration", audio_duration)
            else:
                print(f"⚠️ Whisper API: {resp.status_code}")
        except Exception as e:
            print(f"⚠️ Whisper 失敗: {e}")

    words = result.get("words", []) if result else []
    full_text = result.get("text", "") if result else ""

    if not full_text and os.path.exists(script_json_path):
        with open(script_json_path, encoding="utf-8") as f:
            sc = json.load(f)
        full_text = sc.get("fullNarration", "")

    subtitles = _build_subtitles_japanese(words, full_text, audio_duration)
    subtitles = _add_english_translations(subtitles)

    output = {
        "fullText": full_text,
        "durationSec": audio_duration,
        "subtitles": subtitles,
    }
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"✅ 文字起こし完了: {len(subtitles)}テロップ, {audio_duration:.1f}秒")


if __name__ == "__main__":
    transcribe(
        sys.argv[1],
        sys.argv[2] if len(sys.argv) > 2 else "transcript.json",
    )
