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

    subtitles = transcript.get("subtitles", [])

    # 動画ファイルの尺を取得
    demo_path = os.path.join(project_dir, "demo-full.mp4")
    # screen-recording.mp4 があれば demo-full.mp4 より優先
    screen_rec_path = os.path.join(project_dir, "screen-recording.mp4")
    if os.path.exists(screen_rec_path) and not os.path.exists(demo_path):
        import shutil
        shutil.copy2(screen_rec_path, demo_path)
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
    # ナレーション後に3秒CTAを追加
    CTA_SEC = 3.0
    content_sec = total_duration      # ナレーションが流れる時間
    total_duration = content_sec + CTA_SEC

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
    # 全てのタイミングを content_sec に比例スケールする
    # テンプレート比率 (80秒ベース): hook=5s, problem=10s, intro=15s, demo=30s, result=10s
    def t(ratio):
        """0〜1の比率を content_sec の秒数に変換"""
        return round(ratio * content_sec, 2)

    shots = []

    # フック (冒頭〜6%): 最後のスクショ or デモのクライマックス
    if screenshots:
        shots.append({
            "id": "hook", "startSec": t(0.0), "endSec": t(0.0625),
            "type": "image", "src": f"screenshots/{screenshots[-1]}",
            "label": "フック — 結果を先に見せる",
        })
    elif has_demo:
        shots.append({
            "id": "hook", "startSec": t(0.0), "endSec": t(0.0625),
            "type": "video", "src": "demo-full.mp4",
            "videoStartSec": demo_duration * 0.7,
            "label": "フック — 結果を先に見せる",
        })
    else:
        shots.append({
            "id": "hook", "startSec": t(0.0), "endSec": t(0.0625),
            "type": "color", "backgroundColor": "#0f0f1a",
            "label": "フック — 結果を先に見せる",
        })

    # 問題提起 (6〜19%)
    shots.append({
        "id": "problem",
        "startSec": t(0.0625),
        "endSec": t(0.1875),
        "type": "image" if len(screenshots) >= 2 else "color",
        "src": f"screenshots/{screenshots[0]}" if len(screenshots) >= 2 else None,
        "backgroundColor": "#1a1a2e" if not (len(screenshots) >= 2) else None,
        "label": "問題提起",
    })

    # ツール紹介 (19〜38%): デモ冒頭 or スクショ
    if has_demo:
        shots.append({
            "id": "intro", "startSec": t(0.1875), "endSec": t(0.375),
            "type": "video", "src": "demo-full.mp4",
            "videoStartSec": 0, "videoEndSec": content_sec * 0.1875,
            "label": "ツール紹介 — トップページ",
        })
    elif len(screenshots) >= 1:
        shots.append({
            "id": "intro", "startSec": t(0.1875), "endSec": t(0.375),
            "type": "image", "src": f"screenshots/{screenshots[0]}",
            "label": "ツール紹介 — トップページ",
        })
    else:
        shots.append({
            "id": "intro", "startSec": t(0.1875), "endSec": t(0.375),
            "type": "color", "backgroundColor": "#1a1a2e",
            "label": "ツール紹介 — トップページ",
        })

    # デモ (38〜75%): デモ映像 or スクショをローテーション
    if has_demo:
        shots.append({
            "id": "demo", "startSec": t(0.375), "endSec": t(0.75),
            "type": "video", "src": "demo-full.mp4",
            "videoStartSec": content_sec * 0.375,
            "videoEndSec": min(demo_duration, content_sec * 0.75),
            "label": "デモ — こんな使い方ができる",
        })
    elif len(screenshots) >= 2:
        shots.append({
            "id": "demo", "startSec": t(0.375), "endSec": t(0.75),
            "type": "image", "src": f"screenshots/{screenshots[1]}",
            "label": "デモ — こんな使い方ができる",
        })
    else:
        shots.append({
            "id": "demo", "startSec": t(0.375), "endSec": t(0.75),
            "type": "color", "backgroundColor": "#1a1a2e",
            "label": "デモ — こんな使い方ができる",
        })

    # 結果 + 料金 (75〜88%): 料金ページスクショ or デモ末尾
    pricing_ss = next(
        (s for s in screenshots if "pricing" in s.lower()), None
    )
    if pricing_ss:
        shots.append({
            "id": "result", "startSec": t(0.75), "endSec": round(content_sec, 2),
            "type": "image", "src": f"screenshots/{pricing_ss}",
            "label": "結果 + 料金",
        })
    elif has_demo:
        shots.append({
            "id": "result", "startSec": t(0.75), "endSec": round(content_sec, 2),
            "type": "video", "src": "demo-full.mp4",
            "videoStartSec": max(demo_duration - 20, 0),
            "label": "結果 + 料金",
        })
    elif len(screenshots) >= 3:
        shots.append({
            "id": "result", "startSec": t(0.75), "endSec": round(content_sec, 2),
            "type": "image", "src": f"screenshots/{screenshots[2]}",
            "label": "結果 + 料金",
        })
    else:
        shots.append({
            "id": "result", "startSec": t(0.75), "endSec": round(content_sec, 2),
            "type": "color", "backgroundColor": "#1a1a2e",
            "label": "結果 + 料金",
        })

    # CTA: ナレーション終了後の固定3秒エンドカード
    shots.append({
        "id": "cta",
        "startSec": round(content_sec, 2),
        "endSec": total_duration,
        "type": "color",
        "backgroundColor": "#1a1a2e",
        "label": "CTA — フォローしてね",
    })

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
                "fontSize": 72,
                "fontWeight": "900",
                "color": "#FFFFFF",
                "backgroundColor": "transparent",
                "borderRadius": 0,
                "paddingH": 0,
                "paddingV": 0,
                "position": "bottom",
                "marginBottom": 160,  # 下帯なし、プラットフォームUI回避
                "accentColor": "#4AACFF",
            },
            "title": {
                "fontFamily": "Noto Sans JP",
                "fontSize": 56,
                "fontWeight": "900",
                "color": "#FFFFFF",
            },
            "cta": {
                "text": "B-STUDIO\nAI情報を毎日発信中\nフォローして！",
                "fontSize": 42,
            },
            "transition": {"type": "fade", "durationFrames": 8},
            # 上下固定フレーム設定
            # logoImage: "project/logo.png" のようにpublic/以下のパスを指定するとロゴ画像を表示
            # logoText: テキストロゴ（logoImageがない場合に使用）
            # topColor / bottomColor: CSSのbackground値（グラデーション可）
            "overlay": {
                "topHeight": 160,
                "bottomHeight": 0,
                "topColor": "linear-gradient(to bottom, rgba(0,0,0,0.92) 0%, rgba(0,0,0,0.82) 55%, rgba(0,0,0,0) 100%)",
                "bottomColor": "none",
                "logoText": "B-STUDIO",
                "logoFontSize": 42,
                "logoColor": "#FFFFFF",
                "logoImage": "logo.png" if os.path.exists(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "public", "logo.png")) else None,
            },
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
