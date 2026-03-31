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
    # Linux
    for _cand in _glob.glob(os.path.expanduser(
        "~/.cache/ms-playwright/chromium_headless_shell-*/chrome-linux/headless_shell"
    )):
        _exec = _cand
        break
    # macOS arm64 (新しい headless_shell)
    if not _exec:
        for _cand in _glob.glob(os.path.expanduser(
            "~/Library/Caches/ms-playwright/chromium_headless_shell-*/chrome-headless-shell-mac-arm64/chrome-headless-shell"
        )):
            _exec = _cand
            break
    # macOS x64
    if not _exec:
        for _cand in _glob.glob(os.path.expanduser(
            "~/Library/Caches/ms-playwright/chromium_headless_shell-*/chrome-headless-shell-mac-x64/chrome-headless-shell"
        )):
            _exec = _cand
            break
    # macOS 旧パス (フルChromium)
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


def fetch_og_images(urls, output_dir):
    """
    Playwright が使えない場合のフォールバック。
    OGP/Twitter Card 画像を requests のみでダウンロードしてスクリーンショット代替に使用。
    """
    import requests
    import re
    from urllib.parse import urlparse

    os.makedirs(output_dir, exist_ok=True)
    saved = []
    print("   🌐 OG画像フォールバック（Playwright不要）...")

    for i, url in enumerate(urls[:5]):
        try:
            resp = requests.get(
                url,
                headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"},
                timeout=15,
                allow_redirects=True,
            )
            html = resp.text

            og_img = None
            for pattern in [
                r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
                r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']',
                r'<meta[^>]+name=["\']twitter:image["\'][^>]+content=["\']([^"\']+)["\']',
                r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']twitter:image["\']',
                r'<meta[^>]+property=["\']og:image:secure_url["\'][^>]+content=["\']([^"\']+)["\']',
            ]:
                m = re.search(pattern, html, re.IGNORECASE)
                if m:
                    og_img = m.group(1)
                    break

            if not og_img:
                print(f"   ⚠️  OG画像なし: {url}")
                continue

            # 相対URLを絶対URLに変換
            if og_img.startswith("//"):
                og_img = "https:" + og_img
            elif og_img.startswith("/"):
                p = urlparse(url)
                og_img = f"{p.scheme}://{p.netloc}{og_img}"

            img_resp = requests.get(
                og_img,
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=15,
            )
            if img_resp.status_code != 200:
                continue

            ctype = img_resp.headers.get("content-type", "")
            ext = "png" if "png" in ctype else ("webp" if "webp" in ctype else "jpg")
            domain = url.split("//")[-1].split("/")[0].replace(".", "-")[:30]
            filename = f"{i+1:02d}-{domain}-og.{ext}"
            filepath = os.path.join(output_dir, filename)
            with open(filepath, "wb") as f:
                f.write(img_resp.content)
            saved.append(filepath)
            print(f"   ✅ OG画像保存: {filename} ({len(img_resp.content)//1024}KB)")
        except Exception as e:
            print(f"   ⚠️  OG画像失敗 ({url}): {e}")

    if not saved:
        print("   ℹ️  OG画像も取得できませんでした")
    return saved


async def take_screenshots(urls, output_dir, width=1080, height=1920):
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        print("   ⚠️ Playwright未インストール — OG画像でフォールバック")
        return fetch_og_images(urls, output_dir)

    os.makedirs(output_dir, exist_ok=True)
    saved = []

    try:
      async with async_playwright() as p:
        try:
            browser = await p.chromium.launch(**_get_launch_kwargs())
        except Exception as e:
            print(f"   ⚠️ Chromiumブラウザ起動失敗: {e}")
            print("   → playwright install chromium で解決できます")
            print("   → 今回はOG画像でフォールバックします")
            return fetch_og_images(urls, output_dir)
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
                # ページを強制ダークモードに変換（白背景対策）
                await _apply_dark_mode(page)
                await asyncio.sleep(0.5)
                await page.screenshot(path=output_path, full_page=False, timeout=15000)
                saved.append(output_path)
                print(f"   ✅ 保存: {filename}")
            except Exception as e:
                print(f"   ⚠️  スキップ ({url}): {e}")

        await context.close()
        await browser.close()

    except Exception as e:
        print(f"   ⚠️ Playwright全体エラー: {e} — OG画像でフォールバック")
        if not saved:
            return fetch_og_images(urls, output_dir)

    return saved


DARK_MODE_CSS = """
    html { filter: invert(1) hue-rotate(180deg) !important; background:#000 !important; }
    img, video, picture, canvas, iframe,
    [style*="background-image"] {
        filter: invert(1) hue-rotate(180deg) !important;
    }
"""


async def _apply_dark_mode(page):
    try:
        await page.add_style_tag(content=DARK_MODE_CSS)
    except Exception:
        pass


async def record_with_actions(script_json_path, output_path, timeline_out, width=1080, height=1920):
    """
    script.json の actions 配列に従いPlaywrightで操作しながら録画。
    - 各アクション (navigate / scroll / highlight) をタイムスタンプ通りに実行
    - actions_timeline.json に実際の操作ログ（focusX/Y/scale）を保存
    - 完成映像を MP4 で出力
    """
    import json
    import tempfile
    import subprocess

    try:
        from playwright.async_api import async_playwright
    except ImportError:
        print("❌ Playwright がインストールされていません")
        return False

    try:
        with open(script_json_path, encoding="utf-8") as f:
            script = json.load(f)
    except Exception as e:
        print(f"❌ script.json 読み込み失敗: {e}")
        return False

    actions = script.get("actions", [])
    if not actions:
        print("⚠️  actions が空です。通常録画にフォールバックします...")
        # フォールバック: partsからURLを推定してスクロール録画
        first_url = script.get("url") or ""
        if not first_url and script.get("parts"):
            pass
        return await record_browser(first_url or "", output_path, width, height)

    # アクションを時刻順にソート
    actions = sorted(actions, key=lambda a: a.get("t", 0))
    total_sec = actions[-1].get("t", 0) + 5  # 最後のアクションの後 5 秒録り続ける

    tmp_dir = tempfile.mkdtemp()
    recorded_timeline = []

    print(f"   🎬 操作録画開始: {len(actions)}アクション, 約{total_sec:.0f}秒")

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

            loop_start = asyncio.get_event_loop().time()

            for action in actions:
                target_t = action.get("t", 0)
                elapsed = asyncio.get_event_loop().time() - loop_start
                wait_sec = target_t - elapsed
                if wait_sec > 0:
                    await asyncio.sleep(wait_sec)

                atype = action.get("type", "")

                if atype == "navigate":
                    nav_url = action.get("url", "")
                    scroll_after = action.get("scrollY", 0)
                    try:
                        await page.goto(nav_url, wait_until="domcontentloaded", timeout=20000)
                        await asyncio.sleep(1.5)
                        await _apply_dark_mode(page)
                        await asyncio.sleep(0.5)
                        if scroll_after:
                            await page.evaluate(
                                f"window.scrollTo({{top: {scroll_after}, behavior: 'smooth'}})"
                            )
                            await asyncio.sleep(0.8)
                    except Exception as e:
                        print(f"   ⚠️  navigate失敗 ({nav_url}): {e}")
                    recorded_timeline.append({
                        "t": target_t,
                        "type": "navigate",
                        "focusX": width // 2,
                        "focusY": height // 2,
                        "scale": 1.0,
                    })

                elif atype == "scroll":
                    scroll_y = action.get("scrollY", 0)
                    await page.evaluate(
                        f"window.scrollTo({{top: {scroll_y}, behavior: 'smooth'}})"
                    )
                    await asyncio.sleep(0.8)
                    recorded_timeline.append({
                        "t": target_t,
                        "type": "scroll",
                        "focusX": width // 2,
                        "focusY": height // 2,
                        "scale": 1.2,
                    })

                elif atype == "highlight":
                    selector = action.get("selector", "")
                    try:
                        if selector:
                            el = await page.query_selector(selector)
                            if el:
                                box = await el.bounding_box()
                                if box:
                                    cx = int(box["x"] + box["width"] / 2)
                                    cy = int(box["y"] + box["height"] / 2)
                                    await page.mouse.move(cx, cy)
                                    recorded_timeline.append({
                                        "t": target_t,
                                        "type": "highlight",
                                        "focusX": cx,
                                        "focusY": cy,
                                        "scale": 1.35,
                                    })
                                    continue
                    except Exception:
                        pass
                    recorded_timeline.append({
                        "t": target_t,
                        "type": "highlight",
                        "focusX": width // 2,
                        "focusY": height // 2,
                        "scale": 1.2,
                    })

            # 最後まで録画を引き延ばす
            elapsed = asyncio.get_event_loop().time() - loop_start
            if elapsed < total_sec:
                await asyncio.sleep(total_sec - elapsed)

            video_path = await page.video.path()
            await context.close()
            await browser.close()

        # タイムラインを保存
        with open(timeline_out, "w", encoding="utf-8") as f:
            json.dump(recorded_timeline, f, ensure_ascii=False, indent=2)
        print(f"   📍 タイムライン保存: {timeline_out} ({len(recorded_timeline)}件)")

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
        print(f"   ⚠️  操作録画失敗: {e}")
        return False


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

            # 強制ダークモード（白背景対策）
            await _apply_dark_mode(page)
            await asyncio.sleep(1)

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
        print("  screenshot.py <output_dir> --record-actions <script.json> <output.mp4> <timeline.json>")
        sys.exit(1)

    output_dir = sys.argv[1]

    if sys.argv[2] == "--record-actions":
        # actions に従いながら録画 → MP4 + actions_timeline.json
        if len(sys.argv) < 6:
            print("Usage: screenshot.py <output_dir> --record-actions <script.json> <output.mp4> <timeline.json>")
            sys.exit(1)
        script_json = sys.argv[3]
        output_mp4 = sys.argv[4]
        timeline_json = sys.argv[5]
        ok = asyncio.run(record_with_actions(script_json, output_mp4, timeline_json))
        if not ok:
            print("⚠️  操作録画スキップ")

    elif sys.argv[2] == "--record":
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
