"""Send a random image to a Douyin friend. Supports nickname / short_id / sec_uid.
Tries profile→DM route first if sec_uid is known, falls back to chat search.

Usage:
    python send_image.py "好友昵称"       # by nickname (auto-lookup sec_uid from friends.json)
    python send_image.py 46618889188     # by short_id (抖音号)
    python send_image.py sec_uid:MS4w...  # by sec_uid directly (fastest)

Mode: headless=True by default. Set HEADLESS=0 env var or edit below for visible browser.
"""
import os, sys, time, json, tempfile, urllib.request
from dotenv import load_dotenv
load_dotenv(".env")

from playwright.sync_api import sync_playwright
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


def _wait_react(page, selector: str, timeout=15000):
    """Wait for a React-rendered element to appear (douyin.com SPA)."""
    try:
        page.wait_for_selector(selector, timeout=timeout)
        return True
    except:
        return False


def _dismiss_dialogs(page):
    """Dismiss trust-login / save dialogs."""
    for _ in range(5):
        for label in ["确认", "保存", "取消"]:
            for btn in page.locator(f"button:has-text('{label}')").all():
                try:
                    if btn.is_visible():
                        btn.click(timeout=2000)
                        time.sleep(2)
                except:
                    pass


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

    # Fetch image
    if image_url is None:
        req = urllib.request.Request("https://api.ku.cm/images/?type=json",
                                     headers={"User-Agent": "Mozilla/5.0"})
        image_url = json.loads(urllib.request.urlopen(req).read())["data"]["url"]

    print(f"Image: {image_url}")
    req = urllib.request.Request(image_url, headers={"User-Agent": "Mozilla/5.0"})
    img_data = urllib.request.urlopen(req).read()
    tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
    tmp.write(img_data)
    tmp.close()

    # Open browser
    os.makedirs(USER_DATA_DIR, exist_ok=True)
    playwright = sync_playwright().start()
    context = playwright.chromium.launch_persistent_context(
        USER_DATA_DIR, headless=HEADLESS, viewport={"width": 1280, "height": 900}
    )
    page = context.pages[0] if context.pages else context.new_page()
    context.add_cookies(cookies)

    opened = False
    # Route A: sec_uid known → profile page → 私信 (most reliable)
    if sec_uid:
        print(f"  Opening profile→DM for {nickname}...")
        from resolve_user import open_chat_via_profile
        opened = open_chat_via_profile(page, sec_uid, nickname)
        if opened:
            # Chat panel opens within the same page (SPA), wait for it to render
            _wait_react(page, "input[type='file']", timeout=15000)
        else:
            print(f"  Profile DM failed, falling back to chat search...")

    # Route B: fallback → /chat page → search for user
    if not opened:
        page.goto("https://www.douyin.com/chat", wait_until="domcontentloaded")
        time.sleep(3)
        _wait_react(page, "[data-e2e='conversation-item']")
        _dismiss_dialogs(page)

        from resolve_user import find_or_open_chat
        if not find_or_open_chat(page, nickname, sec_uid):
            print(f"  ERROR: could not open chat with '{nickname}'")
            context.close()
            playwright.stop()
            os.unlink(tmp.name)
            return

        _dismiss_dialogs(page)
        time.sleep(2)

    # Send image
    print("  Uploading image...")
    file_input = page.locator("input[type='file']").first
    if file_input.count() == 0:
        print("  ERROR: no file input found on page")
        context.close()
        playwright.stop()
        os.unlink(tmp.name)
        return

    file_input.set_input_files(tmp.name)
    time.sleep(3)

    for i in range(15):
        time.sleep(1)
        modal_btn = page.locator("button.MsgInputSendFileModalbtnSure").first
        if modal_btn.count() > 0 and modal_btn.is_visible():
            modal_btn.click(force=True, timeout=3000)
            print("  Send clicked!")
            break
    else:
        print("  Modal button did not appear")

    for i in range(15):
        time.sleep(1.5)
        modal = page.locator("[class*='MsgInputSendFileModal']").first
        if modal.count() == 0 or not modal.is_visible():
            print("  Image sent!")
            break

    os.unlink(tmp.name)
    context.close()
    playwright.stop()


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="Send a random image to a Douyin friend")
    p.add_argument("target", nargs="?", default="你的好友昵称",
                   help="Nickname, short_id (digits), or sec_uid:<value>")
    p.add_argument("--url", help="Custom image URL (default: random from api.ku.cm)")
    p.add_argument("--no-headless", action="store_true", help="Show browser window")
    args = p.parse_args()
    if args.no_headless:
        HEADLESS = False
    send_image(args.target, args.url)
