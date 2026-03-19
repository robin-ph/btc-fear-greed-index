"""Twitter/X posting via twikit (cookie-based auth, no API key needed)."""

import asyncio
import os

from twikit import Client


COOKIES_FILE = "twitter_cookies.json"


class TwitterPoster:
    def __init__(self):
        self.client = Client(language="en-US")
        self._logged_in = False

    async def login(self):
        """Login with cookie persistence. Try cookies first, fall back to password."""
        if self._logged_in:
            return

        if os.path.exists(COOKIES_FILE):
            self.client.load_cookies(COOKIES_FILE)
            self._logged_in = True
            print("[Twitter] Loaded session from cookies")
            return

        username = os.getenv("TWITTER_USERNAME", "")
        password = os.getenv("TWITTER_PASSWORD", "")
        totp_secret = os.getenv("TWITTER_TOTP_SECRET", "")

        if not username or not password:
            raise RuntimeError(
                "TWITTER_USERNAME and TWITTER_PASSWORD required in .env"
            )

        print("[Twitter] Logging in with username/password...")
        await self.client.login(
            auth_info_1=username,
            password=password,
            totp_secret=totp_secret or None,
        )
        self.client.save_cookies(COOKIES_FILE)
        self._logged_in = True
        print("[Twitter] Login successful, cookies saved")

    async def post(self, text: str, image_path: str = None) -> str:
        """Post tweet with optional image. Returns tweet ID."""
        await self.login()

        media_ids = []
        if image_path and os.path.exists(image_path):
            print(f"[Twitter] Uploading image: {image_path}")
            media_id = await self.client.upload_media(
                image_path, wait_for_completion=True
            )
            media_ids.append(media_id)
            print(f"[Twitter] Image uploaded: {media_id}")

        try:
            tweet = await self.client.create_tweet(
                text=text,
                media_ids=media_ids if media_ids else None,
            )
            print(f"[Twitter] Tweet posted: {tweet.id}")
            return tweet.id
        except Exception as e:
            # If auth expired, retry once with fresh login
            if "401" in str(e) or "403" in str(e):
                print("[Twitter] Session expired, re-authenticating...")
                if os.path.exists(COOKIES_FILE):
                    os.remove(COOKIES_FILE)
                self._logged_in = False
                await self.login()
                tweet = await self.client.create_tweet(
                    text=text,
                    media_ids=media_ids if media_ids else None,
                )
                print(f"[Twitter] Tweet posted (retry): {tweet.id}")
                return tweet.id
            raise


async def post_tweet(text: str, image_path: str = None) -> str:
    """Convenience function."""
    poster = TwitterPoster()
    return await poster.post(text, image_path)
