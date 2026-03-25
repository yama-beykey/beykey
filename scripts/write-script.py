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

以下のAIツールの縦動画（60〜80秒）の台本を作成してください。

ツール名: {tool_name}
URL: {url}
サイト内容（抜粋）:
{page_text}

## 台本の構成（合計60〜80秒）
1. フック（0-5秒）: 結果・インパクトから入る。「〜で悩んでいませんか？」「〜が一瞬でできる」
2. 問題提起（5-15秒）: ターゲットの課題を具体的に
3. ツール紹介（15-30秒）: ツール名と何ができるか
4. デモ説明（30-60秒）: 実際の使い方を順番に
5. 結果・料金（60-70秒）: 料金・無料プランの有無
6. CTA（70-80秒）: フォロー・コメントを促す

## 制約
- 日本語のみ
- 1文は30文字以内（テロップに収まるよう）
- 体言止め・短文を多用
- 敬体（です・ます）
- 各パートをJSON配列で返す

## 出力形式（JSON）
{{
  "title": "動画タイトル（20文字以内）",
  "hook": "フックのセリフ",
  "parts": [
    {{"id": "hook", "startSec": 0, "endSec": 5, "text": "セリフ"}},
    {{"id": "problem", "startSec": 5, "endSec": 15, "text": "セリフ"}},
    {{"id": "intro", "startSec": 15, "endSec": 30, "text": "セリフ"}},
    {{"id": "demo", "startSec": 30, "endSec": 60, "text": "セリフ"}},
    {{"id": "result", "startSec": 60, "endSec": 70, "text": "セリフ"}},
    {{"id": "cta", "startSec": 70, "endSec": 80, "text": "セリフ"}}
  ],
  "fullNarration": "全パートを繋げた完全ナレーション文"
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
    print(f"   文字数: {char_count}文字（約{char_count // 5}秒）")

    return script


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: write-script.py <URL> <ツール名> <output.json>")
        sys.exit(1)
    write_script(sys.argv[1], sys.argv[2], sys.argv[3])
