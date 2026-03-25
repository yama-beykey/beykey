#!/usr/bin/env python3
"""
metadata.json + transcript.json + script.md → episode.json
Remotionが読み込む編集データを一元生成する
"""
import json
import sys
import os
import subprocess


def get_duration(filepath):
    """ffprobeで動画/音声の尺を取得"""
    try:
        r = subprocess.run(
            [
                "ffprobe",
                "-v",
                "quiet",
                "-show_entries",
                "format=duration",
                "-of",
                "csv=p=0",
                filepath,
            ],
            capture_output=True,
            text=True,
        )
        return float(r.stdout.strip())
    except Exception:
        return 0


def generate_episode(project_dir):
    # 入力ファイル読み込み
    meta_path = os.path.join(project_dir, "metadata.json")
    transcript_path = os.path.join(project_dir, "transcript.json")

    with open(meta_path) as f:
        meta = json.load(f)

    transcript = {"subtitles": [], "durationSec": 0}
    if os.path.exists(transcript_path):
        with open(transcript_path) as f:
            transcript = json.load(f)

    # 動画ファイルの尺を取得
    demo_path = os.path.join(project_dir, "demo-full.mp4")
    demo_duration = get_duration(demo_path) if os.path.exists(demo_path) else 90

    narration_path = None
    for name in ["narration.wav", "narration.mp3", "voice.wav", "voice.mp3"]:
        p = os.path.join(project_dir, name)
        if os.path.exists(p):
            narration_path = p
            break

    narration_duration = get_duration(narration_path) if narration_path else 0

    # 全体の尺（ナレーション基準、なければデモ動画基準、最大90秒）
    total_duration = min(narration_duration or demo_duration, 90)

    # スクリーンショットを収集
    ss_dir = os.path.join(project_dir, "screenshots")
    screenshots = []
    if os.path.exists(ss_dir):
        screenshots = sorted(
            [
                f
                for f in os.listdir(ss_dir)
                if f.endswith((".png", ".jpg", ".jpeg"))
            ]
        )

    # demo-full.mp4 の存在確認
    has_demo = os.path.exists(demo_path) and demo_duration > 0

    # ショット（映像クリップ）を構成
    # 台本のパートに対応させる
    shots = []

    # フック (0:00-0:05): デモの最も印象的な部分 or 最初のスクショ
    if screenshots:
        shots.append({
            "id": "hook", "startSec": 0, "endSec": 5,
            "type": "image", "src": f"screenshots/{screenshots[-1]}",
            "label": "フック — 結果を先に見せる",
        })
    elif has_demo:
        shots.append({
            "id": "hook", "startSec": 0, "endSec": 5,
            "type": "video", "src": "demo-full.mp4",
            "videoStartSec": demo_duration * 0.7,
            "label": "フック — 結果を先に見せる",
        })
    else:
        shots.append({
            "id": "hook", "startSec": 0, "endSec": 5,
            "type": "color", "backgroundColor": "#0f0f1a",
            "label": "フック — 結果を先に見せる",
        })

    # 問題提起 (0:05-0:15): スクショ or ナレーションのみ
    shots.append(
        {
            "id": "problem",
            "startSec": 5,
            "endSec": 15,
            "type": "image" if len(screenshots) >= 2 else "color",
            "src": f"screenshots/{screenshots[0]}" if len(screenshots) >= 2 else None,
            "backgroundColor": "#1a1a2e"
            if not (len(screenshots) >= 2)
            else None,
            "label": "問題提起",
        }
    )

    # ツール紹介 (0:15-0:30): デモ冒頭 (トップページ)
    if has_demo:
        shots.append({
            "id": "intro", "startSec": 15, "endSec": 30,
            "type": "video", "src": "demo-full.mp4",
            "videoStartSec": 0, "videoEndSec": 15,
            "label": "ツール紹介 — トップページ",
        })
    else:
        shots.append({
            "id": "intro", "startSec": 15, "endSec": 30,
            "type": "color", "backgroundColor": "#1a1a2e",
            "label": "ツール紹介 — トップページ",
        })

    # デモ (0:30-1:00): デモ映像のメイン部分
    if has_demo:
        shots.append({
            "id": "demo", "startSec": 30, "endSec": 60,
            "type": "video", "src": "demo-full.mp4",
            "videoStartSec": 30, "videoEndSec": min(demo_duration, 120),
            "label": "デモ — こんな使い方ができる",
        })
    else:
        shots.append({
            "id": "demo", "startSec": 30, "endSec": 60,
            "type": "color", "backgroundColor": "#1a1a2e",
            "label": "デモ — こんな使い方ができる",
        })

    # 結果 + ハードル下げ (1:00-1:10): 料金ページスクショ
    pricing_ss = next(
        (s for s in screenshots if "pricing" in s.lower()), None
    )
    if pricing_ss:
        shots.append({
            "id": "result", "startSec": 60, "endSec": 70,
            "type": "image", "src": f"screenshots/{pricing_ss}",
            "label": "結果 + 料金",
        })
    elif has_demo:
        shots.append({
            "id": "result", "startSec": 60, "endSec": 70,
            "type": "video", "src": "demo-full.mp4",
            "videoStartSec": max(demo_duration - 20, 0),
            "label": "結果 + 料金",
        })
    else:
        shots.append({
            "id": "result", "startSec": 60, "endSec": 70,
            "type": "color", "backgroundColor": "#1a1a2e",
            "label": "結果 + 料金",
        })

    # CTA (1:10-1:20): エンドカード
    shots.append(
        {
            "id": "cta",
            "startSec": 70,
            "endSec": min(total_duration, 80),
            "type": "color",
            "backgroundColor": "#1a1a2e",
            "label": "CTA — フォローしてね",
        }
    )

    # episode.json組み立て
    episode = {
        "meta": {
            "title": meta.get("toolName", "AI Tool"),
            "pattern": meta.get("pattern", "A"),
            "tag": meta.get("tag", "🎬"),
            "date": project_dir.rstrip("/").split("/")[-1],
            "fps": 30,
            "width": 1080,
            "height": 1920,
            "durationSec": total_duration,
        },
        "files": {
            "demoVideo": "demo-full.mp4"
            if os.path.exists(demo_path)
            else None,
            "officialDemo": "official-demo.mp4"
            if os.path.exists(os.path.join(project_dir, "official-demo.mp4"))
            else None,
            "narration": os.path.basename(narration_path)
            if narration_path
            else None,
            "screenshots": [f"screenshots/{s}" for s in screenshots],
        },
        "shots": shots,
        "subtitles": transcript.get("subtitles", []),
        "style": {
            "telop": {
                "fontFamily": "Noto Sans JP",
                "fontSize": 48,
                "fontWeight": "bold",
                "color": "#FFFFFF",
                "backgroundColor": "rgba(0, 0, 0, 0.8)",
                "borderRadius": 12,
                "paddingH": 24,
                "paddingV": 14,
                "position": "bottom",
                "marginBottom": 180,
            },
            "title": {
                "fontFamily": "Noto Sans JP",
                "fontSize": 56,
                "fontWeight": "900",
                "color": "#FFFFFF",
            },
            "cta": {
                "text": "クリエイター向けAI毎日紹介中\nフォローしてね",
                "fontSize": 42,
            },
            "transition": {"type": "fade", "durationFrames": 8},
        },
    }

    output_path = os.path.join(project_dir, "episode.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(episode, f, ensure_ascii=False, indent=2)

    print("✅ episode.json 生成完了")
    print(f"   ショット: {len(shots)}個")
    print(f"   テロップ: {len(transcript.get('subtitles', []))}個")
    print(f"   尺: {total_duration:.1f}秒")
    print(
        f"   サイズ: {episode['meta']['width']}x{episode['meta']['height']} (縦動画)"
    )


if __name__ == "__main__":
    generate_episode(sys.argv[1])
