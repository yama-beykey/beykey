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

    prompt = f"""You are an elite YouTube Shorts scriptwriter. Your scripts get 1M+ views.
Study this tool deeply, then write a script that makes viewers think "I NEED this right now."

Tool: {tool_name}
URL: {url}
Page content:
{page_text}

━━━ SCRIPT RULES (NON-NEGOTIABLE) ━━━

LINE 1-2 | HOOK (0-6s) — START WITH THE RESULT, NEVER THE TOOL NAME
  ✅ "I just built a full app in 30 seconds — for free."
  ✅ "This AI does something no other tool on earth can."
  ✅ "Free AI just killed a $200/month subscription."
  ❌ NEVER: "Today I want to show you..." / "Let me introduce..." / "Have you heard of..."

LINE 3-4 | PROBLEM (6-13s) — SPECIFIC PAIN POINT WITH A NUMBER
  - State a frustration the viewer has RIGHT NOW
  - Include a time/cost number: "...which normally takes 3 hours"
  - Make them nod: "Sound familiar?"

LINE 5 | TOOL REVEAL (13-18s) — DRAMATIC INTRO
  - Name the tool + one sentence on what makes it different
  - Comparison hook: "Unlike [X], this one..."

LINE 6-8 | 3 USE CASES (18-40s) — ESCALATE EXCITEMENT
  - Use Case 1: The basic one everyone needs (familiar)
  - Use Case 2: A clever trick most don't know (surprising)
  - Use Case 3: THE JAW-DROP moment — the reason people share this video
  - Be SPECIFIC: "Click here, paste this, watch it..."
  - Include exact actions, not vague descriptions

LINE 9 | RESULT + URGENCY (40-50s)
  - Concrete transformation: "3 hours → 30 seconds"
  - Price: exact free tier or "$X/month"
  - Urgency: "Just launched" / "Free while in beta" / "Limited time"

LINE 10 | CTA (50-60s)
  - "Follow for daily AI tools that actually save you time."
  - Tie back to the specific value they just saw

━━━ JAPANESE SUBTITLE RULES ━━━
  - 話し言葉（書き言葉禁止）
  - 「〜ですよね」「〜じゃないですか」で共感を作る
  - 技術用語はカタカナのまま（Whisper → Whisper）
  - 1行15文字以内
  - 直訳禁止。意味を汲んで日本語として自然に再構成

━━━ OUTPUT FORMAT (JSON ONLY) ━━━
{{
  "title": "Catchy video title (max 60 chars)",
  "lines": [
    {{"t": 0,  "endT": 4,  "en": "Hook line 1 — result first", "ja": "日本語字幕", "visualNote": "What viewer should see"}},
    {{"t": 4,  "endT": 8,  "en": "Hook line 2 — amplify", "ja": "日本語字幕", "visualNote": "What viewer should see"}},
    {{"t": 8,  "endT": 13, "en": "Problem with a number", "ja": "日本語字幕", "visualNote": "What viewer should see"}},
    {{"t": 13, "endT": 18, "en": "Secondary problem", "ja": "日本語字幕", "visualNote": "What viewer should see"}},
    {{"t": 18, "endT": 23, "en": "Tool reveal — dramatic", "ja": "日本語字幕", "visualNote": "What viewer should see"}},
    {{"t": 23, "endT": 30, "en": "Use case 1 — basic", "ja": "日本語字幕", "visualNote": "What viewer should see"}},
    {{"t": 30, "endT": 38, "en": "Use case 2 — clever trick", "ja": "日本語字幕", "visualNote": "What viewer should see"}},
    {{"t": 38, "endT": 48, "en": "Use case 3 — jaw-drop", "ja": "日本語字幕", "visualNote": "What viewer should see"}},
    {{"t": 48, "endT": 54, "en": "Result + price + urgency", "ja": "日本語字幕", "visualNote": "What viewer should see"}},
    {{"t": 54, "endT": 58, "en": "CTA tied to value", "ja": "日本語字幕", "visualNote": "What viewer should see"}}
  ],
  "fullNarration": "All 10 English lines joined. Used for TTS.",
  "actions": [
    {{"t": 0,  "type": "navigate", "url": "{url}", "label": "Homepage — show the tool"}},
    {{"t": 8,  "type": "scroll",   "scrollY": 600,  "label": "Scroll to problem/pain area"}},
    {{"t": 18, "type": "scroll",   "scrollY": 0,    "label": "Back to top for reveal"}},
    {{"t": 23, "type": "scroll",   "scrollY": 900,  "label": "Features section — use case 1"}},
    {{"t": 30, "type": "scroll",   "scrollY": 1500, "label": "Demo section — use case 2"}},
    {{"t": 38, "type": "scroll",   "scrollY": 2200, "label": "Jaw-drop feature — use case 3"}},
    {{"t": 48, "type": "navigate", "url": "{url}/pricing", "label": "Pricing page"}},
    {{"t": 54, "type": "scroll",   "scrollY": 0,    "label": "Back to top for CTA"}}
  ],
  "metadata": {{
    "hookType": "result-first | shocking-stat | impossible-claim | free-vs-paid",
    "jawDropMoment": "Line 8 description — most shareable moment",
    "targetEmotion": "amazement | FOMO | curiosity | urgency"
  }}
}}

Return JSON only. No markdown fences."""

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
