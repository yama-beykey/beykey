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

## ★最重要: 文字数ルール★
fullNarration は必ず **280文字以上300文字以下** で書いてください。
少なすぎると動画が短くなりNG。文字数が足りない場合は各パートを膨らませてください。

## 台本の構成（5パート合計 280〜300文字）
各パートの目安文字数（合計で必ず280〜300文字にすること）:

1. hook（約30文字）: 「〜が一瞬でできる！」など結果・インパクトから入る
   例: 「デザインもコーディングも、もう別々に考えなくていい時代が来ました。」
2. problem（約50文字）: ターゲットの課題を2〜3文で具体的に描写
   例: 「UIデザインからコードへの変換、毎回手動でやっていませんか？デザイナーとエンジニアの連携に時間がかかり、修正のたびにコストが膨らむ。」
3. intro（約80文字）: ツール名と何ができるか、主な機能を3〜4文で
   例: 「{tool_name}は、AIがUIデザインをリアルタイムでコードに変換するツールです。テキストで指示するだけで、Reactコンポーネントが自動生成。デザインシステムとも連携できます。」
4. demo（約110文字）: 実際の操作を3〜4ステップで丁寧に説明
   例: 「使い方はシンプル。まずプロンプトで作りたいUIを入力します。すると数秒でコードが生成され、プレビューで確認できます。気に入らない部分はチャットで修正指示を出すだけ。コードはそのままコピーして使えます。」
5. result（約30文字）: 料金・無料プランの有無・特徴を一言
   例: 「無料プランあり。有料は月額20ドルから。」

## その他の制約
- 日本語のみ
- 敬体（です・ます）
- CTAは含めない（エンドカードで別途表示するため）

## 出力形式（JSON）
{{
  "title": "動画タイトル（20文字以内）",
  "hook": "フックのセリフ",
  "parts": [
    {{"id": "hook",    "startSec": 0,  "endSec": 4,  "text": "セリフ（約30文字）"}},
    {{"id": "problem", "startSec": 4,  "endSec": 11, "text": "セリフ（約50文字）"}},
    {{"id": "intro",   "startSec": 11, "endSec": 20, "text": "セリフ（約80文字）"}},
    {{"id": "demo",    "startSec": 20, "endSec": 34, "text": "セリフ（約110文字）"}},
    {{"id": "result",  "startSec": 34, "endSec": 38, "text": "セリフ（約30文字）"}}
  ],
  "fullNarration": "全5パートを繋げた完全ナレーション文。必ず280〜300文字。"
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

    resp_json = resp.json()
    message = resp_json["choices"][0]["message"]
    content = message.get("content")

    if content is None:
        # refusal or unexpected structure — retry without json_object format
        print("⚠️  json_object形式でcontentがNull。通常モードで再試行...")
        resp2 = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "gpt-4o",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.7,
            },
            timeout=60,
        )
        if resp2.status_code != 200:
            print(f"❌ OpenAI API error (retry): {resp2.status_code} {resp2.text}")
            sys.exit(1)
        content = resp2.json()["choices"][0]["message"]["content"]

    if not content:
        print(f"❌ APIレスポンスにcontentがありません: {resp_json}")
        sys.exit(1)

    # JSON部分を抽出（```json ... ``` マークダウンに包まれる場合も対応）
    import re
    json_match = re.search(r"```json\s*([\s\S]*?)```", content)
    if json_match:
        content = json_match.group(1)
    else:
        # 最初の { から最後の } までを抽出
        start = content.find("{")
        end = content.rfind("}") + 1
        if start >= 0 and end > start:
            content = content[start:end]

    script = json.loads(content)

    # 文字数が短すぎる場合は一度だけ再試行
    char_count = len(script.get("fullNarration", ""))
    if char_count < 200:
        print(f"⚠️  fullNarration が{char_count}文字と短すぎます。再試行...")
        retry_prompt = prompt + f"\n\n※前回の生成は{char_count}文字しかありませんでした。今度は必ず280文字以上300文字以下で書いてください。"
        resp3 = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "gpt-4o",
                "messages": [{"role": "user", "content": retry_prompt}],
                "response_format": {"type": "json_object"},
                "temperature": 0.8,
            },
            timeout=60,
        )
        if resp3.status_code == 200:
            retry_content = resp3.json()["choices"][0]["message"].get("content")
            if retry_content:
                json_match2 = re.search(r"```json\s*([\s\S]*?)```", retry_content)
                if json_match2:
                    retry_content = json_match2.group(1)
                else:
                    s2 = retry_content.find("{")
                    e2 = retry_content.rfind("}") + 1
                    if s2 >= 0 and e2 > s2:
                        retry_content = retry_content[s2:e2]
                retry_script = json.loads(retry_content)
                retry_chars = len(retry_script.get("fullNarration", ""))
                if retry_chars > char_count:
                    script = retry_script
                    char_count = retry_chars
                    print(f"   再試行で{char_count}文字に改善")

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(script, f, ensure_ascii=False, indent=2)

    print(f"✅ 台本生成完了: {script.get('title', '')}")
    print(f"   パート: {len(script.get('parts', []))}個")
    # 日本語TTS speed=1.5 の実測: 約9.5文字/秒
    estimated_sec = round(char_count / 9.5)
    print(f"   文字数: {char_count}文字（約{estimated_sec}秒 + CTA3秒 = 約{estimated_sec + 3}秒）")

    return script


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: write-script.py <URL> <ツール名> <output.json>")
        sys.exit(1)
    write_script(sys.argv[1], sys.argv[2], sys.argv[3])
