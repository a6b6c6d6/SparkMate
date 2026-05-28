"""Resolve short_id to nickname by searching douyin.com and intercepting im/user/info API."""
import os, sys, time, json
from dotenv import load_dotenv
load_dotenv(".env")

from playwright.sync_api import sync_playwright
from utils.config import get_userData

USER_DATA_DIR = os.path.join(os.path.dirname(__file__), "browser_data")

def resolve_short_id(short_id, cookies, user_data_dir):
    """Resolve short_id → nickname by searching on douyin.com main site.
    The search triggers aweme/v1/web/im/user/info/ which contains user profile data."""
    print(f"  Resolving short_id {short_id}...")
    playwright = sync_playwright().start()
    context = playwright.chromium.launch_persistent_context(
        user_data_dir, headless=False, viewport={"width": 1280, "height": 900}
    )
    page = context.pages[0] if context.pages else context.new_page()
    context.add_cookies(cookies)

    result = {"nickname": None}

    def on_response(response):
        if "aweme/v1/web/im/user/info/" in response.url:
            try:
                data = response.json()
                for user in data.get("data", []):
                    sid = str(user.get("short_id", ""))
                    nick = user.get("nickname", "")
                    if sid == str(short_id) and nick:
                        result["nickname"] = nick
                        print(f"    API returned: short_id={sid}, nickname={nick}")
            except:
                pass

    page.on("response", on_response)

    # Step 1: Go to douyin.com to establish session
    page.goto("https://www.douyin.com", wait_until="domcontentloaded")
    time.sleep(5)

    # Dismiss trust login dialogs
    for _ in range(5):
        for label in ["确认", "保存", "取消"]:
            btn = page.locator(f"button:has-text('{label}')").first
            if btn.count() > 0 and btn.is_visible():
                try:
                    btn.click(timeout=2000)
                    time.sleep(2)
                except:
                    pass

    # Step 2: Search for the short_id
    search_box = page.locator("input[placeholder*='搜索']").first
    if search_box.count() > 0:
        search_box.click()
        time.sleep(0.5)
        search_box.fill(str(short_id))
        time.sleep(1)
        search_box.press("Enter")
        print("  Search submitted, waiting for API response...")
    else:
        # Fallback: navigate to search URL
        page.goto(f"https://www.douyin.com/search/{short_id}", wait_until="domcontentloaded")

    # Step 3: Wait for API — poll for up to 15s
    for _ in range(15):
        if result["nickname"]:
            break
        time.sleep(1)

    # Step 4: Fallback — try to extract from DOM / JS state
    if not result["nickname"]:
        print("  API not captured, trying DOM extraction...")
        try:
            info = page.evaluate("""() => {
                // Try to find user info in global state or DOM
                // Douyin often stores data in __INITIAL_STATE__ or similar
                const keys = Object.keys(window).filter(k => k.includes('STATE') || k.includes('data') || k.includes('SSR'));
                const result = {};
                for (const k of keys.slice(0, 5)) {
                    try {
                        const val = window[k];
                        result[k] = typeof val === 'object' ? JSON.stringify(val).slice(0, 500) : String(val).slice(0, 500);
                    } catch(e) {}
                }
                return JSON.stringify(result);
            }""")
            print(f"  Global state keys: {info[:500]}")
        except Exception as e:
            print(f"  DOM extraction error: {e}")

        # Try clicking first user-like search result
        try:
            clickable = page.locator("[class*='user-card'], [class*='UserCard'], [class*='user-item'], [class*='UserItem']").first
            if clickable.count() > 0:
                clickable.click()
                time.sleep(5)
                # Check if clicking triggered the API
        except:
            pass

    context.close()
    playwright.stop()
    return result["nickname"] or short_id


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "YOUR_SHORT_ID"
    user = get_userData()[0]
    cookies = user["cookies"]
    nickname = resolve_short_id(target, cookies, USER_DATA_DIR)
    print(f"Result: {target} -> '{nickname}'")
