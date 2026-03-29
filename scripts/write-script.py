#!/usr/bin/env python3
"""
URL + ツール名 → 縦動画台本（英語ナレーション + 日本語訳、JSON形式）
YouTube Shorts スタイル: 短いパンチラインを 8〜10 行で構成
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


def fetch_page_text(url):
    try:
        resp = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        text = resp.text[:8000]
        import re
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text[:3000]
    except Exception:
        return ""


def write_script(url, tool_name, output_path):
    page_text = fetch_page_text(url)

    prompt = f"""You are a YouTube Shorts scriptwriter specializing in AI tool introductions for Japanese creators.

Create a ~38-second script for a vertical video introducing this AI tool.

Tool: {tool_name}
URL: {url}
Page content (excerpt):
{page_text}

## SCRIPT STYLE (reference format)
Follow this exact style — short punchy lines, energetic YouTube Shorts creator tone:

Line 1 (0-4s):   Hook — lead with the result/outcome. "X just got the ability to..."
Line 2 (4-7s):   Context — what problem exists today
Line 3 (7-10s):  What makes this tool different
Line 4 (10-13s): Core capability #1 (one sentence)
Line 5 (13-18s): Core capability #2 + #3 (one sentence each)
Line 6 (18-20s): Key differentiator ("You do not need to...")
Line 7 (20-24s): How to get started (first step)
Line 8 (24-30s): Key feature or use case detail
Line 9 (30-35s): Pricing / free tier / availability
Line 10 (35-38s): Call to action ("Follow for more AI tools")

## RULES
- English narration (this will be read aloud)
- Max 15 words per line
- No filler words ("basically", "actually", "so")
- Start strong — hook must grab attention in first 4 seconds
- Use second person ("you", "your") not first person
- Each line must work as a standalone sentence

## OUTPUT FORMAT (JSON only)
{{
  "title": "video title (max 60 chars)",
  "lines": [
    {{"t": 0,  "endT": 4,  "en": "English line here", "ja": "日本語訳"}},
    {{"t": 4,  "endT": 7,  "en": "English line here", "ja": "日本語訳"}},
    {{"t": 7,  "endT": 10, "en": "English line here", "ja": "日本語訳"}},
    {{"t": 10, "endT": 13, "en": "English line here", "ja": "日本語訳"}},
    {{"t": 13, "endT": 18, "en": "English line here", "ja": "日本語訳"}},
    {{"t": 18, "endT": 20, "en": "English line here", "ja": "日本語訳"}},
    {{"t": 20, "endT": 24, "en": "English line here", "ja": "日本語訳"}},
    {{"t": 24, "endT": 30, "en": "English line here", "ja": "日本語訳"}},
    {{"t": 30, "endT": 35, "en": "English line here", "ja": "日本語訳"}},
    {{"t": 35, "endT": 38, "en": "English line here", "ja": "日本語訳"}}
  ],
  "fullNarration": "Complete English narration — all lines joined with space. Used for TTS.",
  "actions": [
    {{"t": 0,  "type": "navigate", "url": "{url}", "label": "Show homepage"}},
    {{"t": 7,  "type": "scroll",   "scrollY": 500, "label": "Scroll to features"}},
    {{"t": 13, "type": "scroll",   "scrollY": 1100, "label": "Show demo section"}},
    {{"t": 24, "type": "navigate", "url": "{url}/pricing", "label": "Pricing page"}},
    {{"t": 35, "type": "scroll",   "scrollY": 0, "label": "Back to top"}}
  ]
}}

Return JSON only."""

    import re

    def call_llm(p, temperature=0.7):
        """Claude API を優先、失敗時は OpenAI にフォールバック"""
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

        # 2. claude CLI フォールバック
        try:
            import subprocess as _sp
            result = _sp.run(
                ["claude", "--print", "--output-format", "text", p[:4000]],
                capture_output=True, text=True, timeout=120,
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
            print(f"   claude CLI 失敗: {result.stderr[:200]}。OpenAI にフォールバック...")
        except Exception as e:
            print(f"   claude CLI 失敗: {e}。OpenAI にフォールバック...")

        # 3. OpenAI フォールバック
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

    # fullNarration が空なら lines から自動生成
    if not script.get("fullNarration") and script.get("lines"):
        script["fullNarration"] = " ".join(
            line["en"] for line in script["lines"] if line.get("en")
        )

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(script, f, ensure_ascii=False, indent=2)

    lines = script.get("lines", [])
    total_sec = lines[-1]["endT"] if lines else 38
    narration = script.get("fullNarration", "")

    print(f"✅ 台本生成完了: {script.get('title', '')}")
    print(f"   ライン数: {len(lines)}行")
    print(f"   推定尺: {total_sec}秒")
    print(f"   ナレーション: {len(narration)}文字")

    return script


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: write-script.py <URL> <ツール名> <output.json>")
        sys.exit(1)
    write_script(sys.argv[1], sys.argv[2], sys.argv[3])
