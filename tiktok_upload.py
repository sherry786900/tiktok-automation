import os
import time
import json
from playwright.sync_api import sync_playwright

COOKIES_FILE = 'tiktok_cookies.json'


class TikTokUploader:

    def upload(self, video_path, title, hashtags):
        caption = f"{title}\n\n{hashtags}"

        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=['--no-sandbox', '--disable-dev-shm-usage']
            )
            ctx = browser.new_context(
                user_agent=(
                    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                    'AppleWebKit/537.36 (KHTML, like Gecko) '
                    'Chrome/120.0.0.0 Safari/537.36'
                )
            )

            if os.path.exists(COOKIES_FILE):
                with open(COOKIES_FILE) as f:
                    ctx.add_cookies(json.load(f))

            page = ctx.new_page()

            try:
                page.goto('https://www.tiktok.com/tiktokstudio/upload', timeout=30000)
                time.sleep(3)

                if 'login' in page.url.lower():
                    raise RuntimeError('TikTok login expire ho gaya — cookies dobara banao.')

                page.wait_for_selector('input[type="file"]', timeout=15000)
                page.set_input_files('input[type="file"]', os.path.abspath(video_path))
                time.sleep(10)

                for sel in [
                    '[data-testid="caption-input"]',
                    '.public-DraftEditor-content',
                    '[contenteditable="true"]',
                ]:
                    try:
                        el = page.wait_for_selector(sel, timeout=4000)
                        if el:
                            el.click()
                            el.type(caption, delay=20)
                            break
                    except:
                        continue

                time.sleep(2)

                for sel in [
                    'button:has-text("Post")',
                    'button:has-text("Publish")',
                    '[data-testid="post-button"]',
                ]:
                    try:
                        btn = page.wait_for_selector(sel, timeout=4000)
                        if btn:
                            btn.click()
                            break
                    except:
                        continue

                time.sleep(5)
                url = page.url

                # Cookies refresh karo
                with open(COOKIES_FILE, 'w') as f:
                    json.dump(ctx.cookies(), f)

                return url

            except Exception as e:
                page.screenshot(path=f'outputs/error_{int(time.time())}.png')
                raise RuntimeError(str(e))
            finally:
                browser.close()


def save_cookies_from_browser():
    """
    Laptop pe run karo — TikTok login karo — cookies save ho jayengi.
    Command: python save_cookies.py
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        ctx = browser.new_context()
        page = ctx.new_page()
        page.goto('https://www.tiktok.com/login')
        print('➡️  TikTok login karo browser mein...')
        input('✅ Login hone ke baad yahan Enter dabao: ')
        cookies = ctx.cookies()
        with open(COOKIES_FILE, 'w') as f:
            json.dump(cookies, f)
        print(f'✅ Cookies save ho gayi! ({len(cookies)} cookies)')
        browser.close()
