#!/usr/bin/env python3
"""
台本(script.json)の各シーンに対応するAI動画生成プロンプトを自動生成。

使い方:
  python3 scripts/generate-clips.py <日付ディレクトリ>

出力:
  <日付ディレクトリ>/ai-clips-prompts.txt   — Auto Meta / Meta AIに貼るプロンプトリスト
  <日付ディレクトリ>/ai-clips-prompts.json  — プログラムから使うJSON版
  <日付ディレクトリ>/ai-clips/              — 生成クリップのダウンロード先フォルダ
"""
import json
import sys
import os


# ショットID → AIクリップを使うかどうか（auto blend mode）
AI_SHOT_IDS = {"hook", "problem", "result", "cta"}
BROWSER_SHOT_IDS = {"intro", "demo"}


def _get_visual_context(line: dict, scene_index: int, total: int, tool_name: str) -> str:
    """visualNote があればそれを使い、なければナレーションからプロンプトを生成"""
    visual_note = line.get("visualNote", "")
    en_text = line.get("en", "")

    if visual_note:
        base = visual_note
    else:
        base = en_text

    # シーン位置による映像スタイル決定
    progress = scene_index / max(total - 1, 1)

    if scene_index == 0:
        # フック: 衝撃的・グラブ力
        style = (
            "Cinematic extreme close-up, glowing holographic interface materializing in mid-air, "
            "electric blue neon light, dark background, slow dolly in, 4K, ultra-sharp, "
            "dramatic lens flare, cyberpunk aesthetic, vertical 9:16 composition"
        )
    elif scene_index <= 2:
        # 問題提起: 混乱・overwhelm
        style = (
            "Overhead tracking shot, person overwhelmed by multiple chaotic floating screens, "
            "dim moody office lighting, slow zoom out revealing disorder, "
            "desaturated cinematic color grade, vertical 9:16"
        )
    elif progress < 0.5:
        # ツール紹介・機能説明: クリーンな未来感
        style = (
            "Sleek futuristic workspace, single glowing holographic display, "
            "warm golden hour light through floor-to-ceiling windows, "
            "smooth slow pan right, minimalist tech aesthetic, teal accent lighting, "
            "shallow depth of field, vertical 9:16"
        )
    elif progress < 0.75:
        # デモ・操作: インタラクティブ感
        style = (
            "Close-up of hands interacting with transparent holographic touchscreen, "
            "data particles flowing between fingertips, teal and purple color palette, "
            "smooth tracking shot, bokeh background, vertical 9:16"
        )
    elif scene_index == total - 1:
        # CTA: エネルギッシュ
        style = (
            "Abstract glowing particles forming a subscribe bell notification, "
            "dark background with vibrant blue and purple accents, "
            "smooth 3D camera orbit, motion graphics style, vertical 9:16"
        )
    else:
        # 結果・料金: 成功・達成感
        style = (
            "Wide cinematic shot of a futuristic cityscape at golden hour, "
            "drone shot slowly pulling upward, lens flare, epic scale, "
            "warm triumphant color grade, vertical 9:16"
        )

    return f"{style}. Context: {base}"


def generate_clip_prompts(project_dir: str):
    script_path = os.path.join(project_dir, "script.json")
    if not os.path.exists(script_path):
        print(f"❌ script.json が見つかりません: {script_path}")
        sys.exit(1)

    with open(script_path, encoding="utf-8") as f:
        script = json.load(f)

    lines = script.get("lines", [])
    tool_name = script.get("title", "AI Tool")
    total = len(lines)

    # ショットIDのマッピング（10行 → hook/problem/intro/demo/result/cta）
    def get_shot_id(index: int, total: int) -> str:
        if index == 0:
            return "hook"
        elif index <= 1:
            return "problem"
        elif index <= 3:
            return "intro"
        elif index <= 7:
            return "demo"
        elif index == total - 1:
            return "cta"
        else:
            return "result"

    prompts = []
    for i, line in enumerate(lines):
        shot_id = get_shot_id(i, total)
        use_ai = shot_id in AI_SHOT_IDS
        prompt = _get_visual_context(line, i, total, tool_name)

        prompts.append({
            "scene": i + 1,
            "shotId": shot_id,
            "useAiClip": use_ai,
            "narration_en": line.get("en", ""),
            "narration_ja": line.get("ja", ""),
            "t": line.get("t", 0),
            "endT": line.get("endT", 0),
            "video_prompt": prompt,
            "filename": f"{i+1:02d}-{shot_id}.mp4",
        })

    # Auto Meta用テキスト出力（貼り付けるだけで使える）
    prompts_txt = os.path.join(project_dir, "ai-clips-prompts.txt")
    with open(prompts_txt, "w", encoding="utf-8") as f:
        f.write(f"# {tool_name} — AI Clip Prompts\n")
        f.write("# Auto Meta に以下のプロンプトをシーンごとに貼り付けて生成してください\n")
        f.write("# AIクリップを使うシーン: hook, problem, result, cta\n")
        f.write("# ブラウザ録画を使うシーン: intro, demo\n\n")
        for p in prompts:
            marker = "🎬 AI CLIP" if p["useAiClip"] else "🌐 browser (skip)"
            f.write(f"--- Scene {p['scene']} / {p['shotId']} ({marker}) ---\n")
            f.write(f"Narration: {p['narration_en']}\n")
            if p["useAiClip"]:
                f.write(f"Prompt: {p['video_prompt']}\n")
                f.write(f"Save as: {p['filename']}\n")
            f.write("\n")

    # JSON出力
    prompts_json = os.path.join(project_dir, "ai-clips-prompts.json")
    with open(prompts_json, "w", encoding="utf-8") as f:
        json.dump(prompts, f, ensure_ascii=False, indent=2)

    # ai-clips ディレクトリ作成
    clips_dir = os.path.join(project_dir, "ai-clips")
    os.makedirs(clips_dir, exist_ok=True)

    ai_scenes = [p for p in prompts if p["useAiClip"]]
    print(f"✅ AI動画プロンプト生成完了: {total}シーン中 {len(ai_scenes)}シーンがAIクリップ対象")
    print(f"📄 {prompts_txt}")
    print(f"📁 クリップ保存先: {clips_dir}/")
    print(f"")
    print(f"👉 Auto Meta 手順:")
    print(f"   1. {prompts_txt} を開く")
    print(f"   2. 🎬 AI CLIP のプロンプトを Auto Meta に貼り付けて生成")
    print(f"   3. 生成されたファイルを {clips_dir}/ に保存")
    print(f"      ファイル名例: 01-hook.mp4, 02-problem.mp4, ...")
    print(f"   4. bash scripts/render.sh <日付ディレクトリ> を再実行")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: generate-clips.py <日付ディレクトリ>")
        sys.exit(1)
    generate_clip_prompts(sys.argv[1])
