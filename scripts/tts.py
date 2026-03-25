#!/usr/bin/env python3
"""
台本のfullNarration → narration.wav
OpenAI TTS API (tts-1, voice: nova) を使用
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


def generate_tts(text, output_path, voice="nova", speed=1.5):
    """
    テキストをTTSで音声に変換
    OpenAI TTS → gTTS → サイレント音声 の順でフォールバック
    """
    print(f"   テキスト: {len(text)}文字")

    # 1. OpenAI TTS を試みる
    api_key = get_api_key()
    if api_key:
        try:
            resp = requests.post(
                "https://api.openai.com/v1/audio/speech",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "tts-1",
                    "input": text,
                    "voice": voice,
                    "speed": speed,
                    "response_format": "wav",
                },
                timeout=120,
            )
            if resp.status_code == 200:
                with open(output_path, "wb") as f:
                    f.write(resp.content)
                size_kb = len(resp.content) // 1024
                print(f"✅ OpenAI TTS 完了: {output_path} ({size_kb}KB)")
                return
            else:
                print(f"⚠️ OpenAI TTS: {resp.status_code} — gTTS にフォールバック")
        except Exception as e:
            print(f"⚠️ OpenAI TTS 失敗: {e} — gTTS にフォールバック")

    # 2. gTTS (Google Translate TTS) を試みる
    try:
        from gtts import gTTS
        import subprocess
        import tempfile
        tts = gTTS(text=text, lang="ja")
        tmp_mp3 = output_path.replace(".wav", "_tmp.mp3")
        tts.save(tmp_mp3)
        # MP3 → WAV 変換 (ffmpeg)
        result = subprocess.run(
            ["ffmpeg", "-y", "-i", tmp_mp3, "-ar", "22050", "-ac", "1", output_path],
            capture_output=True,
        )
        os.remove(tmp_mp3)
        if result.returncode == 0:
            print(f"✅ gTTS 完了: {output_path}")
            return
        else:
            print("⚠️ gTTS MP3→WAV 変換失敗 — サイレント音声を生成")
    except ImportError:
        print("⚠️ gTTS 未インストール — pip install gTTS を試みます")
        try:
            import subprocess
            subprocess.run(
                ["pip", "install", "gTTS", "-q", "--break-system-packages"],
                capture_output=True,
            )
            from gtts import gTTS
            tts = gTTS(text=text, lang="ja")
            tmp_mp3 = output_path.replace(".wav", "_tmp.mp3")
            tts.save(tmp_mp3)
            result = subprocess.run(
                ["ffmpeg", "-y", "-i", tmp_mp3, "-ar", "22050", "-ac", "1", output_path],
                capture_output=True,
            )
            os.remove(tmp_mp3)
            if result.returncode == 0:
                print(f"✅ gTTS 完了: {output_path}")
                return
        except Exception as e2:
            print(f"⚠️ gTTS 失敗: {e2}")
    except Exception as e:
        print(f"⚠️ gTTS エラー: {e}")

    # 3. macOS say コマンド（日本語Kyokoボイス）
    import subprocess
    import platform
    if platform.system() == "Darwin":
        try:
            tmp_aiff = output_path.replace(".wav", "_tmp.aiff")
            result = subprocess.run(
                ["say", "-v", "Kyoko", "-r", "180", "-o", tmp_aiff, text],
                capture_output=True, timeout=120,
            )
            if result.returncode == 0 and os.path.exists(tmp_aiff):
                conv = subprocess.run(
                    ["ffmpeg", "-y", "-i", tmp_aiff, "-ar", "22050", "-ac", "1", output_path],
                    capture_output=True,
                )
                os.remove(tmp_aiff)
                if conv.returncode == 0:
                    print(f"✅ macOS say TTS 完了: {output_path}")
                    return
        except Exception as e:
            print(f"⚠️ say コマンド失敗: {e}")

    # 4. サイレント音声を生成（文字数÷9.5文字/秒で長さ推定）
    estimated_sec = len(text) / 9.5
    print(f"⚠️ サイレント音声を生成 ({estimated_sec:.1f}秒) — 後で実音声と差し替え可")
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", f"anullsrc=r=22050:cl=mono",
         "-t", str(estimated_sec), "-q:a", "9", "-acodec", "pcm_s16le", output_path],
        capture_output=True,
    )
    if os.path.exists(output_path):
        print(f"✅ サイレント音声生成完了: {output_path}")
    else:
        print("❌ 音声生成に完全失敗しました")
        sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: tts.py <script.json or text> <output.wav> [voice] [speed]")
        sys.exit(1)

    input_path = sys.argv[1]
    output_path = sys.argv[2]
    voice = sys.argv[3] if len(sys.argv) > 3 else "nova"
    speed = float(sys.argv[4]) if len(sys.argv) > 4 else 1.5

    # JSONファイルかテキストかを判定
    if input_path.endswith(".json"):
        with open(input_path, encoding="utf-8") as f:
            script = json.load(f)
        text = script.get("fullNarration", "")
    else:
        text = input_path

    if not text:
        print("❌ ナレーションテキストが空です")
        sys.exit(1)

    generate_tts(text, output_path, voice=voice, speed=speed)
