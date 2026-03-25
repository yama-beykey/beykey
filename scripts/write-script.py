#!/usr/bin/env python3
"""
URL + ツール名 → 縦動画台本（JSON形式）
OpenAI GPT-4oで台本を自動生成する
"""
import json
import os
import sys
import requests


def get_api_key():
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
                providers = cfg.get("models", {}).get("providers", {})
                for provider in providers.values():
                    if isinstance(provider, dict) and provider.get("apiKey"):
                        return provider["apiKey"]
    return api_key


def fetch_page_text(url):
    try:
        resp = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        text = resp.text[:8000]
        # HTMLタグを簡易除去
        import re
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text[:3000]
    except Exception:
        return ""


def write_script(url, tool_name, output_path):
    api_key = get_api_key()
    if not api_key:
        print("❌ OPENAI_API_KEY が見つかりません")
        sys.exit(1)

    page_text = fetch_page_text(url)

    prompt = f"""あなたはクリエイター向けAIツール紹介のショート動画の台本ライターです。

以下のAIツールの縦動画（約38秒）の台本を作成してください。

ツール名: {tool_name}
URL: {url}
サイト内容（抜粋）:
{page_text}

## 台本の構成（ナレーション合計 約38秒 ＝ 日本語 約260〜280文字）
1. フック（0-4秒 / 約28文字）: 結果・インパクトから入る。「〜が一瞬でできる」
2. 問題提起（4-10秒 / 約42文字）: ターゲットの課題を1〜2文で具体的に
3. ツール紹介（10-20秒 / 約70文字）: ツール名と何ができるか
4. デモ説明（20-34秒 / 約98文字）: 実際の使い方を2〜3ステップで
5. 結果・料金（34-38秒 / 約28文字）: 料金・無料プランの有無を一言で

## 制約
- 日本語のみ
- 1文は25文字以内（テロップに収まるよう）
- 体言止め・短文を多用
- 敬体（です・ます）
- fullNarration の合計文字数は 260〜280文字に収める
- CTAは含めない（エンドカードで別途表示するため）

## 出力形式（JSON）
{{
  "title": "動画タイトル（20文字以内）",
  "hook": "フックのセリフ",
  "parts": [
    {{"id": "hook",    "startSec": 0,  "endSec": 4,  "text": "セリフ"}},
    {{"id": "problem", "startSec": 4,  "endSec": 10, "text": "セリフ"}},
    {{"id": "intro",   "startSec": 10, "endSec": 20, "text": "セリフ"}},
    {{"id": "demo",    "startSec": 20, "endSec": 34, "text": "セリフ"}},
    {{"id": "result",  "startSec": 34, "endSec": 38, "text": "セリフ"}}
  ],
  "fullNarration": "全パートを繋げた完全ナレーション文（260〜280文字）"
}}

JSONのみ返してください。"""

    resp = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": "gpt-4o",
            "messages": [{"role": "user", "content": prompt}],
            "response_format": {"type": "json_object"},
            "temperature": 0.7,
        },
        timeout=60,
    )

    if resp.status_code != 200:
        print(f"❌ OpenAI API error: {resp.status_code} {resp.text}")
        sys.exit(1)

    content = resp.json()["choices"][0]["message"]["content"]
    script = json.loads(content)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(script, f, ensure_ascii=False, indent=2)

    print(f"✅ 台本生成完了: {script.get('title', '')}")
    print(f"   パート: {len(script.get('parts', []))}個")
    char_count = len(script.get("fullNarration", ""))
    # 日本語TTS speed=1.1 の実測: 約7文字/秒
    estimated_sec = round(char_count / 7)
    print(f"   文字数: {char_count}文字（約{estimated_sec}秒 + CTA3秒 = 約{estimated_sec + 3}秒）")

    return script


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: write-script.py <URL> <ツール名> <output.json>")
        sys.exit(1)
    write_script(sys.argv[1], sys.argv[2], sys.argv[3])
