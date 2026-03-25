#!/usr/bin/env python3
"""
URLリスト → スクリーンショット (1080x1920 縦動画用)
Playwright を使用
"""
import sys
import os
import json
import asyncio


async def take_screenshots(urls, output_dir, width=1080, height=1920):
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        print("❌ Playwright がインストールされていません")
        print("   npm install playwright && npx playwright install chromium")
        sys.exit(1)

    os.makedirs(output_dir, exist_ok=True)
    saved = []

    # 既存の headless_shell を自動検出
    import glob as _glob
    _exec = None
    for _cand in _glob.glob(os.path.expanduser(
        "~/.cache/ms-playwright/chromium_headless_shell-*/chrome-linux/headless_shell"
    )):
        _exec = _cand
        break
    _launch_kwargs = {"executable_path": _exec} if _exec else {}

    async with async_playwright() as p:
        _launch_kwargs["args"] = [
            "--disable-remote-fonts",
            "--disable-web-security",
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-extensions",
            "--font-render-hinting=none",
        ]
        browser = await p.chromium.launch(**_launch_kwargs)
        context = await browser.new_context(
            viewport={"width": width, "height": height},
            device_scale_factor=1,
        )
        page = await context.new_page()
        # 外部フォント・重いリソースをブロックしてタイムアウトを防ぐ
        async def _block_heavy(route):
            if route.request.resource_type in ("font", "media"):
                await route.abort()
            else:
                await route.continue_()
        await page.route("**/*", _block_heavy)

        for i, url in enumerate(urls):
            filename = f"{i+1:02d}-{url.split('//')[-1].split('/')[0].replace('.', '-')}"
            if len(url.split('/')) > 3 and url.split('/')[-1]:
                filename += f"-{url.split('/')[-1][:20]}"
            filename = filename[:50] + ".png"
            output_path = os.path.join(output_dir, filename)

            try:
                print(f"   📸 {url}")
                try:
                    await page.goto(url, wait_until="domcontentloaded", timeout=20000)
                except Exception:
                    pass  # タイムアウトでもスクリーンショットを試みる
                await asyncio.sleep(1)
                await page.screenshot(path=output_path, full_page=False, timeout=10000)
                saved.append(output_path)
                print(f"   ✅ 保存: {filename}")
            except Exception as e:
                print(f"   ⚠️  スキップ ({url}): {e}")

        await browser.close()

    return saved


def main():
    if len(sys.argv) < 3:
        print("Usage: screenshot.py <output_dir> <url1> [url2] ...")
        sys.exit(1)

    output_dir = sys.argv[1]
    urls = sys.argv[2:]

    saved = asyncio.run(take_screenshots(urls, output_dir))
    print(f"\n✅ スクリーンショット完了: {len(saved)}枚 → {output_dir}")


if __name__ == "__main__":
    main()
