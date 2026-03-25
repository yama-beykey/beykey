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

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        context = await browser.new_context(
            viewport={"width": width, "height": height},
            device_scale_factor=1,
        )
        page = await context.new_page()

        for i, url in enumerate(urls):
            filename = f"{i+1:02d}-{url.split('//')[-1].split('/')[0].replace('.', '-')}"
            if len(url.split('/')) > 3 and url.split('/')[-1]:
                filename += f"-{url.split('/')[-1][:20]}"
            filename = filename[:50] + ".png"
            output_path = os.path.join(output_dir, filename)

            try:
                print(f"   📸 {url}")
                await page.goto(url, wait_until="networkidle", timeout=30000)
                # クッキーバナーを閉じる試み
                for selector in ["[id*=cookie] button", "[class*=cookie] button", "[data-testid*=accept]"]:
                    try:
                        btn = page.locator(selector).first
                        if await btn.is_visible(timeout=2000):
                            await btn.click()
                    except Exception:
                        pass
                await asyncio.sleep(1)
                await page.screenshot(path=output_path, full_page=False)
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
