"""Send a random image to a Douyin friend. Supports nickname / short_id / sec_uid.
Tries profile→DM route first if sec_uid is known, falls back to chat search.

Usage:
    python send_image.py "好友昵称"       # by nickname (auto-lookup sec_uid from friends.json)
    python send_image.py 46618889188     # by short_id (抖音号)
    python send_image.py sec_uid:MS4w...  # by sec_uid directly (fastest)

Mode: headless=True by default. Set HEADLESS=0 env var or edit below for visible browser.
"""
import json, os, tempfile
from dotenv import load_dotenv
load_dotenv(".env")

from playwright.sync_api import sync_playwright
from media_sources import download_image, fetch_random_image_data
from resolve_user import dismiss_dialogs, find_or_open_chat
from utils.config import get_userData

USER_DATA_DIR = os.path.join(os.path.dirname(__file__), "browser_data")
FRIENDS_FILE = os.path.join(os.path.dirname(__file__), "friends.json")
HEADLESS = os.getenv("HEADLESS", "1") == "1"


def _lookup_secuid(nickname: str):
    """Look up sec_uid from friends.json by nickname. Returns None if not found."""
    if not os.path.exists(FRIENDS_FILE):
        return None
    try:
        with open(FRIENDS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        for friend in data.get("friends", []):
            if friend.get("nickname") == nickname:
                return friend.get("sec_uid", "")
    except:
        pass
    return None


def send_image(target: str, image_url: str = None):
    """Send an image to a friend. Auto-resolves nickname/short_id to sec_uid."""
    user = get_userData()[0]
    cookies = user["cookies"]

    # Resolve target → nickname + sec_uid
    sec_uid = ""
    if target.startswith("sec_uid:"):
        sec_uid = target.split(":", 1)[1]
        nickname = "[sec_uid]"
        print(f"  Using sec_uid directly: {sec_uid[:30]}...")
    elif target.isdigit():
        print(f"  Resolving short_id {target}...")
        from resolve_user import resolve_via_search
        resolved = resolve_via_search(target, cookies, USER_DATA_DIR, None)
        if resolved:
            nickname = resolved["nickname"]
            sec_uid = resolved["sec_uid"]
            print(f"  -> '{nickname}' (sec_uid={sec_uid[:30]}...)")
        else:
            nickname = target
            print(f"  WARNING: could not resolve {target}")
    else:
        nickname = target
        # Try friends.json for known sec_uid (avoids an extra page navigation)
        cached = _lookup_secuid(nickname)
        if cached:
            sec_uid = cached
            print(f"  Found sec_uid in friends.json for '{nickname}'")

    tmp_name = None
    playwright = None
    context = None
    try:
        if image_url is None:
            image_data = fetch_random_image_data()
        else:
            image_data, final_url = download_image(image_url)
            print(f"    -> custom image: {final_url}")

        tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
        tmp.write(image_data)
        tmp.close()
        tmp_name = tmp.name

        os.makedirs(USER_DATA_DIR, exist_ok=True)
        playwright = sync_playwright().start()
        context = playwright.chromium.launch_persistent_context(
            USER_DATA_DIR,
            headless=HEADLESS,
            viewport={"width": 1280, "height": 900},
        )
        page = context.pages[0] if context.pages else context.new_page()
        context.add_cookies(cookies)
        page.goto("https://www.douyin.com/chat", wait_until="domcontentloaded")
        dismiss_dialogs(page)

        if not find_or_open_chat(page, nickname, sec_uid):
            print(f"  ERROR: could not open chat with '{nickname}'")
            return False

        print("  Uploading image...")
        file_input = page.locator("input[type='file']").first
        file_input.wait_for(state="attached", timeout=15000)
        file_input.set_input_files(tmp_name)

        modal_button = page.locator(
            "button.MsgInputSendFileModalbtnSure"
        ).first
        modal_button.wait_for(state="visible", timeout=30000)
        modal_button.click(timeout=5000)
        modal_button.wait_for(state="hidden", timeout=90000)
        page.wait_for_timeout(5000)
        print("  Image sent!")
        return True
    except Exception as exc:
        print(f"  ERROR: failed to send image: {exc}")
        return False
    finally:
        if context:
            context.close()
        if playwright:
            playwright.stop()
        if tmp_name and os.path.exists(tmp_name):
            os.unlink(tmp_name)


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="Send a random image to a Douyin friend")
    p.add_argument("target", nargs="?", default="你的好友昵称",
                   help="Nickname, short_id (digits), or sec_uid:<value>")
    p.add_argument("--url", help="Custom image URL (default: random 4K image)")
    p.add_argument("--no-headless", action="store_true", help="Show browser window")
    args = p.parse_args()
    if args.no_headless:
        HEADLESS = False
    send_image(args.target, args.url)
