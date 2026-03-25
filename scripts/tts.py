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


def generate_tts(text, output_path, voice="nova", speed=1.1):
    """
    テキストをOpenAI TTSで音声に変換
    voice: alloy / echo / fable / onyx / nova / shimmer
    speed: 0.25〜4.0 (日本語は1.1がちょうど良い)
    """
    api_key = get_api_key()
    if not api_key:
        print("❌ OPENAI_API_KEY が見つかりません")
        sys.exit(1)

    print(f"   テキスト: {len(text)}文字")
    print(f"   声: {voice} / 速度: {speed}")

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

    if resp.status_code != 200:
        print(f"❌ TTS API error: {resp.status_code} {resp.text[:200]}")
        sys.exit(1)

    with open(output_path, "wb") as f:
        f.write(resp.content)

    size_kb = len(resp.content) // 1024
    print(f"✅ ナレーション生成完了: {output_path} ({size_kb}KB)")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: tts.py <script.json or text> <output.wav> [voice] [speed]")
        sys.exit(1)

    input_path = sys.argv[1]
    output_path = sys.argv[2]
    voice = sys.argv[3] if len(sys.argv) > 3 else "nova"
    speed = float(sys.argv[4]) if len(sys.argv) > 4 else 1.1

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
