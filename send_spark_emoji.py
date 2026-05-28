"""Send 续火花 emoji to a Douyin friend. Supports nickname / short_id / sec_uid.
Uses profile→DM route (reliable), looks up sec_uid from friends.json automatically.

Usage:
    python send_spark_emoji.py "好友昵称"       # by nickname
    python send_spark_emoji.py 46618889188     # by short_id
    python send_spark_emoji.py sec_uid:MS4...  # by sec_uid (fastest)
"""
import os, sys, time, json
from dotenv import load_dotenv
load_dotenv(".env")

from playwright.sync_api import sync_playwright
from utils.config import get_userData

USER_DATA_DIR = os.path.join(os.path.dirname(__file__), "browser_data")
FRIENDS_FILE = os.path.join(os.path.dirname(__file__), "friends.json")
HEADLESS = os.getenv("HEADLESS", "1") == "1"


def _lookup_secuid(nickname: str):
    if not os.path.exists(FRIENDS_FILE):
        return None
    try:
        with open(FRIENDS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        for f2 in data.get("friends", []):
            if f2.get("nickname") == nickname:
                return f2.get("sec_uid", "")
    except:
        pass
    return None


def _wait_react(page, selector: str, timeout=15000):
    try:
        page.wait_for_selector(selector, timeout=timeout)
        return True
    except:
        return False


def _dismiss_dialogs(page):
    for _ in range(5):
        for label in ["确认", "保存", "取消"]:
            for btn in page.locator(f"button:has-text('{label}')").all():
                try:
                    if btn.is_visible():
                        btn.click(timeout=2000)
                        time.sleep(2)
                except:
                    pass


def send_spark_emoji(target: str):
    """Send 续火花 emoji to target user."""
    user = get_userData()[0]
    cookies = user["cookies"]

    # Resolve target
    sec_uid = ""
    if target.startswith("sec_uid:"):
        sec_uid = target.split(":", 1)[1]
        nickname = "[sec_uid]"
        print(f"  Using sec_uid directly")
    elif target.isdigit():
        print(f"  Resolving short_id {target}...")
        from resolve_user import resolve_via_search
        resolved = resolve_via_search(target, cookies, USER_DATA_DIR, None)
        if resolved:
            nickname = resolved["nickname"]
            sec_uid = resolved["sec_uid"]
            print(f"  -> '{nickname}'")
        else:
            nickname = target
            print(f"  WARNING: could not resolve {target}")
    else:
        nickname = target
        cached = _lookup_secuid(nickname)
        if cached:
            sec_uid = cached
            print(f"  Found sec_uid in friends.json for '{nickname}'")

    if not sec_uid:
        print("  ERROR: no sec_uid available, cannot proceed")
        return

    # Open browser
    os.makedirs(USER_DATA_DIR, exist_ok=True)
    playwright = sync_playwright().start()
    context = playwright.chromium.launch_persistent_context(
        USER_DATA_DIR, headless=HEADLESS, viewport={"width": 1280, "height": 900}
    )
    page = context.pages[0] if context.pages else context.new_page()
    context.add_cookies(cookies)

    # Navigate profile → 私信
    print(f"  Opening profile→DM for {nickname}...")
    from resolve_user import open_chat_via_profile
    if not open_chat_via_profile(page, sec_uid, nickname):
        print("  ERROR: could not open chat")
        context.close()
        playwright.stop()
        return

    _wait_react(page, "svg.messageMsgInputiconAction", timeout=15000)
    time.sleep(2)

    # Send 续火花 emoji
    print("  Sending 续火花 emoji...")
    emoji_btn = page.locator("svg.messageMsgInputiconAction").first
    if emoji_btn.count() == 0:
        print("  ERROR: emoji button not found")
        context.close()
        playwright.stop()
        return

    emoji_btn.click(force=True, timeout=3000)
    time.sleep(3)

    emoji_items = page.locator("[class*='emojiEmojiItem']")
    count = emoji_items.count()
    print(f"  {count} emojis available")

    spark_idx = 0
    for i in range(count):
        text = (emoji_items.nth(i).text_content() or "").strip()
        if "火花" in text:
            spark_idx = i
            break

    emoji_items.nth(spark_idx).click(force=True, timeout=2000, delay=100)
    time.sleep(2)
    print("  续火花 sent!")

    context.close()
    playwright.stop()


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="Send 续火花 emoji to a Douyin friend")
    p.add_argument("target", nargs="?", default="你的好友昵称",
                   help="Nickname, short_id (digits), or sec_uid:<value>")
    p.add_argument("--no-headless", action="store_true", help="Show browser window")
    args = p.parse_args()
    if args.no_headless:
        HEADLESS = False
    send_spark_emoji(args.target)
