"""Post BTC Fear & Greed infographic to Twitter/X via Edge browser.

Anti-detection: random delays, human-like mouse movement, realistic typing speed.
Uses Playwright with persistent session state.

Usage:
    python edge_poster.py --login              # First time: manual login
    python edge_poster.py --post image.png     # Post image with text
"""

import argparse
import asyncio
import os
import random
import sys

from playwright.async_api import async_playwright

SESSION_FILE = "edge_twitter_session.json"


# ── Human behavior simulation ──

async def human_delay(min_s=0.5, max_s=2.0):
    """Random delay to mimic human timing."""
    await asyncio.sleep(random.uniform(min_s, max_s))


async def human_type(page, text: str):
    """Type like a human: variable speed, occasional pauses."""
    for char in text:
        delay = random.randint(30, 90)  # ms per char
        if char in " .,!?":
            delay += random.randint(50, 150)  # Pause after punctuation
        await page.keyboard.type(char, delay=delay)
        # Occasional micro-pause (thinking)
        if random.random() < 0.05:
            await asyncio.sleep(random.uniform(0.2, 0.6))


async def human_mouse_move(page):
    """Random mouse movement to look human."""
    x = random.randint(200, 800)
    y = random.randint(200, 600)
    await page.mouse.move(x, y, steps=random.randint(5, 15))
    await human_delay(0.3, 0.8)


async def login_twitter():
    print("[Edge] Opening Edge for Twitter login...")
    print("[Edge] Please log in manually.\n")

    async with async_playwright() as p:
        browser = await p.chromium.launch(channel="msedge", headless=False)
        context = await browser.new_context(
            viewport={"width": 1280, "height": 900},
            locale="en-US",
            timezone_id="America/New_York",
        )
        page = await context.new_page()
        await page.goto("https://x.com/login", wait_until="domcontentloaded")

        try:
            await page.wait_for_url("**/home**", timeout=300000)
            print("[Edge] Login detected!")
        except Exception:
            print("[Edge] Timeout — saving session anyway...")

        await page.wait_for_timeout(3000)
        await context.storage_state(path=SESSION_FILE)
        print(f"[Edge] Session saved to {SESSION_FILE}")
        await browser.close()


async def post_tweet(image_path: str, text: str):
    if not os.path.exists(SESSION_FILE):
        print("[Edge] No session. Run: python edge_poster.py --login")
        sys.exit(1)

    abs_image = os.path.abspath(image_path)

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            channel="msedge",
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled",
            ],
        )
        context = await browser.new_context(
            storage_state=SESSION_FILE,
            viewport={"width": 1280, "height": 900},
            locale="en-US",
            timezone_id="America/New_York",
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36 Edg/125.0.0.0"
            ),
        )

        # Remove webdriver flag
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => false });
        """)

        page = await context.new_page()

        try:
            # 1. Open home with human-like behavior
            print("[Edge] Opening Twitter home...")
            await page.goto("https://x.com/home", wait_until="domcontentloaded", timeout=60000)
            await human_delay(3, 5)

            if "login" in page.url:
                print("[Edge] Session expired! Run: python edge_poster.py --login")
                await browser.close()
                sys.exit(1)

            # Move mouse around like a human browsing
            await human_mouse_move(page)
            await human_delay(1, 3)

            # 2. Find and click compose box
            print("[Edge] Clicking compose box...")
            compose = None
            for selector in [
                '[data-testid="tweetTextarea_0"]',
                '[contenteditable="true"][role="textbox"]',
            ]:
                try:
                    loc = page.locator(selector).first
                    await loc.wait_for(timeout=10000)
                    compose = loc
                    break
                except Exception:
                    continue

            if not compose:
                # Fallback: click sidebar "Post" button to open compose modal
                print("[Edge] Using compose modal...")
                sidebar_btn = page.locator('a[data-testid="SideNav_NewTweet_Button"]').or_(
                    page.locator('a[href="/compose/post"]')
                )
                await sidebar_btn.first.click()
                await human_delay(2, 4)
                compose = page.locator('[data-testid="tweetTextarea_0"]').or_(
                    page.locator('[contenteditable="true"][role="textbox"]')
                ).first
                await compose.wait_for(timeout=15000)

            await human_mouse_move(page)
            await compose.click()
            await human_delay(0.5, 1.5)

            # 3. Type text like a human
            print("[Edge] Typing tweet...")
            for i, line in enumerate(text.split("\n")):
                if i > 0:
                    await page.keyboard.press("Enter")
                    await human_delay(0.2, 0.5)
                if line.strip():
                    await human_type(page, line)
            await human_delay(1, 2)

            # 4. Upload image
            print("[Edge] Uploading image...")
            await human_mouse_move(page)
            file_input = page.locator('input[type="file"][accept*="image"]')
            await file_input.first.set_input_files(abs_image)

            print("[Edge] Waiting for image to process...")
            try:
                await page.wait_for_selector(
                    '[data-testid="attachments"] img, [data-testid="imagePreview"]',
                    timeout=20000,
                )
                print("[Edge] Image preview loaded")
            except Exception:
                await human_delay(5, 8)
                print("[Edge] Image wait timeout, proceeding...")

            await human_delay(2, 4)

            # 5. Click Post with human-like hover first
            print("[Edge] Clicking Post...")
            post_btn = page.locator('[data-testid="tweetButtonInline"]')
            await post_btn.wait_for(timeout=10000)
            await post_btn.hover()
            await human_delay(0.3, 0.8)
            await post_btn.click()

            await human_delay(4, 6)

            # 6. Verify
            print("[Edge] Verifying...")
            await human_mouse_move(page)
            await page.goto("https://x.com/whataidoing", wait_until="domcontentloaded", timeout=60000)
            await human_delay(5, 8)

            tweets = await page.query_selector_all('article[data-testid="tweet"]')
            if tweets:
                first_text = await tweets[0].inner_text()
                if "Fear" in first_text or "BTC" in first_text:
                    print("[Edge] SUCCESS — tweet verified on profile!")
                else:
                    print("[Edge] Posted, latest tweet doesn't match. Check manually.")
            else:
                print("[Edge] Could not load tweets. Check manually.")

            await context.storage_state(path=SESSION_FILE)

        except Exception as e:
            print(f"[Edge] Error: {e}")
            try:
                await page.screenshot(path="edge_error.png", timeout=5000)
            except Exception:
                pass
            raise
        finally:
            await browser.close()


def main():
    parser = argparse.ArgumentParser(description="Post to Twitter via Edge")
    parser.add_argument("--login", action="store_true", help="Manual Twitter login")
    parser.add_argument("--post", type=str, help="Image path to post")
    parser.add_argument("--text", type=str, default="", help="Tweet text")
    args = parser.parse_args()

    if args.login:
        asyncio.run(login_twitter())
    elif args.post:
        text = args.text or "BTC Fear & Greed Index — Daily Update"
        asyncio.run(post_tweet(args.post, text))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
