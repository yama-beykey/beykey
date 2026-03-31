#!/usr/bin/env python3
"""
B-STUDIO 今日のAIツールトレンド自動調査スクリプト

複数ソースから最新AIツールを取得し、B-STUDIO視聴者向けに最適な
トピックをランキングして提案する。

使い方:
  python3 scripts/find-topic.py               # TOP3を表示して選択
  python3 scripts/find-topic.py --auto        # 1位を自動選択して create-video.sh を実行
  python3 scripts/find-topic.py --json        # JSON形式で出力

ソース:
  1. Product Hunt  — 今日のトップAIツール
  2. Hacker News   — Show HN / Launch HN の新着
  3. TechCrunch AI — 最新記事からツール名を抽出
"""
import json
import os
import sys
import re
import requests
from datetime import datetime, timezone


# ───────── ソース別取得関数 ─────────

def fetch_producthunt_today():
    """Product Hunt の今日のトップAIツールをスクレイプ"""
    tools = []
    try:
        resp = requests.get(
            "https://www.producthunt.com/topics/artificial-intelligence",
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                "Accept": "text/html",
            },
            timeout=15,
        )
        if resp.status_code != 200:
            return tools

        html = resp.text
        # OGタグとhrefからツール情報を抽出
        names = re.findall(r'"name":\s*"([^"]{5,60})"', html)
        urls = re.findall(r'href="(https://www\.producthunt\.com/posts/[^"]+)"', html)

        seen = set()
        for i, url in enumerate(urls[:20]):
            slug = url.rstrip("/").split("/")[-1]
            name = slug.replace("-", " ").title()
            if name not in seen:
                seen.add(name)
                tools.append({
                    "name": name,
                    "url": url,
                    "source": "Product Hunt",
                    "score": 10 - i,
                })
    except Exception as e:
        print(f"   ⚠️ Product Hunt 取得失敗: {e}")
    return tools[:10]


def fetch_hackernews_new():
    """HackerNews の新着から AI/ML ツールを抽出"""
    tools = []
    try:
        # Show HN と最新ストーリーを取得
        new_ids = requests.get(
            "https://hacker-news.firebaseio.com/v0/newstories.json",
            timeout=10,
        ).json()[:100]

        for story_id in new_ids[:50]:
            try:
                story = requests.get(
                    f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json",
                    timeout=5,
                ).json()
                if not story:
                    continue

                title = story.get("title", "")
                url = story.get("url", f"https://news.ycombinator.com/item?id={story_id}")

                # AI/MLツールに関連するかチェック
                ai_keywords = [
                    "AI", "LLM", "GPT", "Claude", "agent", "model",
                    "copilot", "generate", "automate", "ML", "neural",
                    "open source", "free", "tool", "app", "launch",
                ]
                title_upper = title.upper()
                if not any(kw.upper() in title_upper for kw in ai_keywords):
                    continue

                # Show HN / Launch HN を優先
                is_launch = title.startswith(("Show HN:", "Launch HN:"))
                score = story.get("score", 0)

                tools.append({
                    "name": re.sub(r"^(Show HN|Launch HN):\s*", "", title).strip(),
                    "url": url,
                    "source": "Hacker News",
                    "score": score + (50 if is_launch else 0),
                    "hn_title": title,
                })
            except Exception:
                continue

    except Exception as e:
        print(f"   ⚠️ Hacker News 取得失敗: {e}")

    return sorted(tools, key=lambda x: x["score"], reverse=True)[:10]


def fetch_techcrunch_ai():
    """TechCrunch AI セクションの最新記事からツールを抽出"""
    tools = []
    try:
        resp = requests.get(
            "https://techcrunch.com/category/artificial-intelligence/",
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=15,
        )
        if resp.status_code != 200:
            return tools

        html = resp.text
        # 記事タイトルとURLを抽出
        articles = re.findall(
            r'href="(https://techcrunch\.com/\d{4}/[^"]+?)"[^>]*>([^<]{20,120})</a>',
            html,
        )

        for url, title in articles[:20]:
            title = title.strip()
            if any(kw in title.lower() for kw in ["ai", "gpt", "llm", "model", "robot", "automation"]):
                tools.append({
                    "name": title[:60],
                    "url": url,
                    "source": "TechCrunch",
                    "score": 5,
                })

    except Exception as e:
        print(f"   ⚠️ TechCrunch 取得失敗: {e}")

    return tools[:8]


# ───────── LLMによるランキング ─────────

def rank_with_llm(candidates: list) -> list:
    """
    Claude/GPT-4o に候補リストを渡して B-STUDIO 向けにランキングさせる。
    失敗時はスコアベースのシンプルなソートにフォールバック。
    """
    if not candidates:
        return candidates

    candidates_text = "\n".join(
        f"{i+1}. [{c['source']}] {c['name']} — {c['url']}"
        for i, c in enumerate(candidates[:20])
    )

    prompt = f"""You are a content strategist for B-STUDIO, a Japanese YouTube Shorts channel about AI tools for creators.

Today is {datetime.now(timezone.utc).strftime('%Y-%m-%d')}.

From the following trending AI tools/articles, pick the TOP 3 best for a Shorts video.

Criteria (in order of importance):
1. NEW launch or major update (not older than 2 weeks)
2. Has a demo-able product (actual website, not just research paper)
3. Relevant to creators: video, audio, writing, design, coding, automation
4. Free tier available or affordable (<$30/month)
5. Viral potential: "jaw-drop" factor, surprising capability, free vs paid

Candidates:
{candidates_text}

Return JSON only:
{{
  "top3": [
    {{
      "rank": 1,
      "name": "Tool Name",
      "url": "https://...",
      "why": "One sentence reason for Japanese creators (Japanese)",
      "hook": "Suggested hook line for the Shorts video (English)",
      "source": "Source name"
    }},
    ...
  ]
}}"""

    try:
        import anthropic as _anthropic
        client = _anthropic.Anthropic()
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}],
        )
        content = msg.content[0].text
    except Exception:
        try:
            api_key = os.environ.get("OPENAI_API_KEY", "")
            if not api_key:
                raise ValueError("no key")
            resp = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": "gpt-4o-mini",
                    "messages": [{"role": "user", "content": prompt}],
                    "response_format": {"type": "json_object"},
                },
                timeout=30,
            )
            content = resp.json()["choices"][0]["message"]["content"]
        except Exception:
            # LLMなしでスコアベースソート
            return sorted(candidates, key=lambda x: x["score"], reverse=True)[:3]

    try:
        m = re.search(r"\{[\s\S]*\}", content)
        data = json.loads(m.group(0) if m else content)
        ranked = data.get("top3", [])
        # 元の候補データとマージ
        result = []
        for r in ranked:
            match = next(
                (c for c in candidates if r["url"] in c["url"] or c["url"] in r["url"]),
                None,
            )
            entry = match.copy() if match else {}
            entry.update(r)
            result.append(entry)
        return result
    except Exception:
        return sorted(candidates, key=lambda x: x["score"], reverse=True)[:3]


# ───────── メイン ─────────

def find_topic(auto=False, output_json=False):
    print("🔍 B-STUDIO 今日のAIトレンドを調査中...")
    print("")

    all_candidates = []

    print("   📦 Product Hunt を取得中...")
    all_candidates += fetch_producthunt_today()

    print("   🔶 Hacker News を取得中...")
    all_candidates += fetch_hackernews_new()

    print("   📰 TechCrunch AI を取得中...")
    all_candidates += fetch_techcrunch_ai()

    if not all_candidates:
        print("❌ 候補が取得できませんでした。ネットワークを確認してください。")
        sys.exit(1)

    print(f"\n   🤖 LLMでランキング中 ({len(all_candidates)}件)...")
    top3 = rank_with_llm(all_candidates)

    if output_json:
        print(json.dumps(top3, ensure_ascii=False, indent=2))
        return top3

    # ──── 表示 ────
    print("")
    print("━" * 60)
    print("🏆 B-STUDIO おすすめトレンドTOP3")
    print("━" * 60)

    for i, tool in enumerate(top3):
        medal = ["🥇", "🥈", "🥉"][i]
        print(f"\n{medal} {tool.get('rank', i+1)}位: {tool.get('name', 'Unknown')}")
        print(f"   URL   : {tool.get('url', '')}")
        print(f"   ソース : {tool.get('source', '')}")
        if tool.get("why"):
            print(f"   理由   : {tool['why']}")
        if tool.get("hook"):
            print(f"   フック : \"{tool['hook']}\"")

    print("")
    print("━" * 60)

    if auto:
        # 自動で1位を選択
        chosen = top3[0]
        print(f"✅ 自動選択: {chosen['name']}")
    else:
        # インタラクティブ選択
        try:
            choice = input("どれにしますか？ (1/2/3) [1]: ").strip()
            idx = int(choice) - 1 if choice in ("1", "2", "3") else 0
            chosen = top3[idx]
        except (ValueError, IndexError, KeyboardInterrupt):
            chosen = top3[0]

    print(f"\n🎬 「{chosen['name']}」で動画を生成します")
    print(f"   URL: {chosen['url']}")

    # create-video.sh を呼び出し
    skill_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    date_str = datetime.now().strftime("%Y-%m-%d")
    tool_name = chosen.get("name", "AI Tool")[:40]
    tool_url = chosen.get("url", "")

    cmd = f'bash "{skill_dir}/scripts/create-video.sh" "{tool_url}" "{tool_name}" {date_str}'
    print(f"\n▶️  実行: {cmd}")
    print("")

    os.execv("/bin/bash", ["/bin/bash", f"{skill_dir}/scripts/create-video.sh",
                           tool_url, tool_name, date_str])


if __name__ == "__main__":
    auto_mode = "--auto" in sys.argv
    json_mode = "--json" in sys.argv
    find_topic(auto=auto_mode, output_json=json_mode)
