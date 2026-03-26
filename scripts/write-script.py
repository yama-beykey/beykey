#!/usr/bin/env python3
"""
URL + ツール名 → 縦動画台本（JSON形式）
Claude claude-sonnet-4-6 または OpenAI GPT-4oで台本を自動生成する
"""
import json
import os
import sys
import requests


def get_openai_key():
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


def get_api_key():
    return get_openai_key()


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

## ブラウザ操作アクション
ナレーションの各パートに合わせて、画面で何を見せるかを actions 配列で指定してください。
アクションタイプ:
- navigate: 指定URLに移動
- scroll: ページをスクロール（scrollY はピクセル）
- highlight: 特定要素にマウスをホバー（selector は CSS セレクタ）

タイミングは parts の startSec に合わせること。
同じページを異なるスクロール位置で見せることで、ナレーションと映像を一致させてください。

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
  "fullNarration": "全5パートを繋げた完全ナレーション文。必ず280〜300文字。",
  "actions": [
    {{"t": 0,  "type": "navigate", "url": "{url}", "label": "トップページ表示"}},
    {{"t": 4,  "type": "scroll",   "scrollY": 600, "label": "問題を示す箇所を表示"}},
    {{"t": 11, "type": "navigate", "url": "{url}", "label": "機能紹介セクション", "scrollY": 0}},
    {{"t": 20, "type": "scroll",   "scrollY": 1200, "label": "デモエリア表示"}},
    {{"t": 34, "type": "navigate", "url": "{url}/pricing", "label": "料金ページ"}}
  ]
}}

JSONのみ返してください。"""

    import re

    def call_llm(p, temperature=0.7):
        """Claude API を優先、失敗時は OpenAI にフォールバック"""
        # 1. Anthropic Claude SDK を試みる（ANTHROPIC_API_KEY or 内部認証）
        try:
            import anthropic as _anthropic
            client = _anthropic.Anthropic()
            msg = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=2000,
                messages=[{"role": "user", "content": p}],
            )
            return msg.content[0].text
        except Exception as e:
            print(f"   Claude SDK 失敗: {e}。claude CLI を試みます...")

        # 2. claude CLI (Claude Code) を試みる
        try:
            import subprocess as _sp
            import tempfile as _tmp
            with _tmp.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as tf:
                tf.write(p)
                tf_path = tf.name
            result = _sp.run(
                ["claude", "--print", "--output-format", "text", p[:4000]],
                capture_output=True, text=True, timeout=120,
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
            print(f"   claude CLI 失敗: {result.stderr[:200]}。OpenAI にフォールバック...")
        except Exception as e:
            print(f"   claude CLI 失敗: {e}。OpenAI にフォールバック...")

        # OpenAI フォールバック
        oai_key = get_openai_key()
        if not oai_key:
            print("❌ API キーが見つかりません (ANTHROPIC_API_KEY / OPENAI_API_KEY)")
            sys.exit(1)
        resp = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {oai_key}", "Content-Type": "application/json"},
            json={"model": "gpt-4o", "messages": [{"role": "user", "content": p}],
                  "response_format": {"type": "json_object"}, "temperature": temperature},
            timeout=60,
        )
        if resp.status_code != 200:
            print(f"❌ OpenAI API error: {resp.status_code}")
            sys.exit(1)
        return resp.json()["choices"][0]["message"]["content"]

    def extract_json(text):
        m = re.search(r"```json\s*([\s\S]*?)```", text)
        if m:
            return m.group(1)
        s = text.find("{")
        e = text.rfind("}") + 1
        return text[s:e] if s >= 0 and e > s else text

    content = call_llm(prompt)
    if not content:
        print("❌ APIレスポンスが空です")
        sys.exit(1)

    script = json.loads(extract_json(content))

    # 文字数が短すぎる場合は一度だけ再試行
    char_count = len(script.get("fullNarration", ""))
    if char_count < 200:
        print(f"⚠️  fullNarration が{char_count}文字と短すぎます。再試行...")
        retry_content = call_llm(
            prompt + f"\n\n※前回の生成は{char_count}文字でした。必ず280文字以上300文字以下で。",
            temperature=0.8,
        )
        if retry_content:
            retry_script = json.loads(extract_json(retry_content))
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
