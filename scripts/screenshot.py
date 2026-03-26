#!/usr/bin/env python3
"""
URLリスト → スクリーンショット + ブラウザ録画 (1080x1920 縦動画用)
Playwright を使用

使い方:
  スクリーンショット: screenshot.py <output_dir> <url1> [url2] ...
  録画:             screenshot.py <output_dir> --record <output.mp4> <url>
"""
import sys
import os
import asyncio
import glob as _glob


def _get_launch_kwargs():
    """Playwright 起動オプション（headless_shell 自動検出）"""
    _exec = None
    for _cand in _glob.glob(os.path.expanduser(
        "~/.cache/ms-playwright/chromium_headless_shell-*/chrome-linux/headless_shell"
    )):
        _exec = _cand
        break
    # macOS: Playwright インストール済み Chromium を自動検出
    if not _exec:
        for _cand in _glob.glob(os.path.expanduser(
            "~/Library/Caches/ms-playwright/chromium-*/chrome-mac/Chromium.app/Contents/MacOS/Chromium"
        )):
            _exec = _cand
            break

    kwargs = {"headless": True}
    if _exec:
        kwargs["executable_path"] = _exec
    kwargs["args"] = [
        "--no-sandbox",
        "--disable-dev-shm-usage",
        "--disable-extensions",
        "--disable-remote-fonts",
        "--font-render-hinting=none",
    ]
    return kwargs


async def take_screenshots(urls, output_dir, width=1080, height=1920):
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        print("❌ Playwright がインストールされていません: pip install playwright && playwright install chromium")
        sys.exit(1)

    os.makedirs(output_dir, exist_ok=True)
    saved = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(**_get_launch_kwargs())
        context = await browser.new_context(
            viewport={"width": width, "height": height},
            device_scale_factor=1,
        )
        page = await context.new_page()

        async def _block_heavy(route):
            if route.request.resource_type in ("font", "media"):
                await route.abort()
            else:
                await route.continue_()
        await page.route("**/*", _block_heavy)

        for i, url in enumerate(urls):
            domain = url.split("//")[-1].split("/")[0].replace(".", "-")
            slug = url.rstrip("/").split("/")[-1][:24] if url.rstrip("/").split("/")[-1] else ""
            filename = f"{i+1:02d}-{domain}"
            if slug:
                filename += f"-{slug}"
            filename = filename[:50] + ".png"
            output_path = os.path.join(output_dir, filename)

            try:
                print(f"   📸 {url}")
                try:
                    await page.goto(url, wait_until="domcontentloaded", timeout=25000)
                except Exception:
                    pass
                await asyncio.sleep(2)
                await page.screenshot(path=output_path, full_page=False, timeout=15000)
                saved.append(output_path)
                print(f"   ✅ 保存: {filename}")
            except Exception as e:
                print(f"   ⚠️  スキップ ({url}): {e}")

        await context.close()
        await browser.close()

    return saved


async def record_browser(url, output_path, width=1080, height=1920, duration_sec=12):
    """
    Playwrightでサイトをスクロール録画 → MP4保存
    言葉と合った映像のみ使用するため、指定URLのみを録画する
    """
    import tempfile
    import subprocess

    try:
        from playwright.async_api import async_playwright
    except ImportError:
        print("❌ Playwright がインストールされていません")
        return False

    tmp_dir = tempfile.mkdtemp()
    print(f"   🎬 録画開始: {url}")

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(**_get_launch_kwargs())
            context = await browser.new_context(
                viewport={"width": width, "height": height},
                device_scale_factor=1,
                record_video_dir=tmp_dir,
                record_video_size={"width": width, "height": height},
            )
            page = await context.new_page()

            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=25000)
            except Exception:
                pass

            # ページロード待機
            await asyncio.sleep(3)

            # スムーズスクロールでサイトを見せる
            scroll_steps = int(duration_sec * 1.5)
            for i in range(scroll_steps):
                scroll_y = int((i / scroll_steps) * 3000)
                await page.evaluate(f"window.scrollTo({{top: {scroll_y}, behavior: 'smooth'}})")
                await asyncio.sleep(0.4)

            # 最後に少し待機
            await asyncio.sleep(2)

            video_path = await page.video.path()
            await context.close()
            await browser.close()

            # WebM → MP4 変換
            result = subprocess.run(
                [
                    "ffmpeg", "-y",
                    "-i", video_path,
                    "-c:v", "libx264",
                    "-crf", "23",
                    "-preset", "fast",
                    "-pix_fmt", "yuv420p",
                    output_path,
                ],
                capture_output=True,
            )
            if result.returncode == 0 and os.path.exists(output_path):
                size_mb = os.path.getsize(output_path) / 1024 / 1024
                print(f"   ✅ 録画完了: {output_path} ({size_mb:.1f}MB)")
                return True
            else:
                print(f"   ⚠️  MP4変換失敗: {result.stderr.decode()[:200]}")
                return False

    except Exception as e:
        print(f"   ⚠️  録画失敗: {e}")
        return False


def main():
    if len(sys.argv) < 3:
        print("Usage:")
        print("  screenshot.py <output_dir> <url1> [url2] ...")
        print("  screenshot.py <output_dir> --record <output.mp4> <url>")
        sys.exit(1)

    output_dir = sys.argv[1]

    if sys.argv[2] == "--record":
        if len(sys.argv) < 5:
            print("Usage: screenshot.py <output_dir> --record <output.mp4> <url>")
            sys.exit(1)
        output_mp4 = sys.argv[3]
        url = sys.argv[4]
        ok = asyncio.run(record_browser(url, output_mp4))
        if ok:
            print(f"✅ 録画完了: {output_mp4}")
        else:
            print("⚠️  録画スキップ（スクリーンショットのみで続行）")
    else:
        urls = sys.argv[2:]
        saved = asyncio.run(take_screenshots(urls, output_dir))
        print(f"\n✅ スクリーンショット完了: {len(saved)}枚 → {output_dir}")


if __name__ == "__main__":
    main()
