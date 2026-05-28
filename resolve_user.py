"""Resolve Douyin short_id → nickname + sec_uid + uid via douyin.com search API."""
import time

def resolve_via_search(short_id, cookies, user_data_dir, playwright_module):
    """Search short_id on douyin.com main page, intercept im/user/info API.
    Returns dict with nickname, unique_id, sec_uid, uid or None."""
    from playwright.sync_api import sync_playwright

    playwright = sync_playwright().start()
    context = playwright.chromium.launch_persistent_context(
        user_data_dir, headless=False, viewport={"width": 1280, "height": 900}
    )
    page = context.pages[0] if context.pages else context.new_page()
    context.add_cookies(cookies)

    result = {}

    def on_response(response):
        if "aweme/v1/web/im/user/info/" in response.url:
            try:
                for user in response.json().get("data", []):
                    if str(user.get("short_id", "")) == str(short_id):
                        result["nickname"] = user.get("nickname", "")
                        result["unique_id"] = user.get("unique_id", "")
                        result["sec_uid"] = user.get("sec_uid", "")
                        result["uid"] = user.get("uid", "")
            except:
                pass

    page.on("response", on_response)

    page.goto("https://www.douyin.com", wait_until="domcontentloaded")
    time.sleep(5)

    for _ in range(5):
        for label in ["确认", "保存", "取消"]:
            btn = page.locator(f"button:has-text('{label}')").first
            if btn.count() > 0 and btn.is_visible():
                try:
                    btn.click(timeout=2000)
                    time.sleep(2)
                except:
                    pass

    search_box = page.locator("input[placeholder*='搜索']").first
    if search_box.count() > 0:
        search_box.click()
        time.sleep(0.5)
        search_box.fill(str(short_id))
        time.sleep(1)
        search_box.press("Enter")

    for _ in range(15):
        if result.get("sec_uid"):
            break
        time.sleep(1)

    context.close()
    playwright.stop()
    return result if result.get("sec_uid") else None


def open_chat_via_profile(page, sec_uid, nickname):
    """Navigate to user profile and click 私信 (private message) button to open chat.
    Returns True if chat was opened."""
    page.goto(f"https://www.douyin.com/user/{sec_uid}", wait_until="domcontentloaded")
    time.sleep(3)

    # Wait for React SPA to render (douyin.com is client-side rendered)
    try:
        page.wait_for_selector("button:has-text('私信')", timeout=15000)
    except:
        pass

    for _ in range(5):
        for label in ["确认", "保存", "取消"]:
            for btn in page.locator(f"button:has-text('{label}')").all():
                try:
                    if btn.is_visible():
                        btn.click(timeout=2000)
                        time.sleep(2)
                except:
                    pass

    # Try all visible 私信 buttons (there may be multiple with semi-button design system)
    for btn in page.locator("button:has-text('私信')").all():
        try:
            if btn.is_visible():
                btn.click(timeout=5000, force=True)
                time.sleep(8)
                return True
        except:
            continue

    return False


def find_or_open_chat(page, nickname, sec_uid):
    """Try to find user via chat search, fallback to profile→私信.
    Returns True if chat was opened."""
    # Method 1: Search in chat panel
    page.evaluate(f"""(term) => {{
        const input = document.querySelector('input[placeholder="搜索"]');
        if (input) {{
            const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
            setter.call(input, term);
            input.dispatchEvent(new Event('input', {{bubbles: true}}));
        }}
    }}""", nickname)
    time.sleep(4)

    chat_btn = page.locator(".SearchPanelitemchat_btn").first
    if chat_btn.count() > 0 and chat_btn.is_visible():
        chat_btn.click(timeout=3000)
        time.sleep(5)
        return True

    # Method 2: Check conversation list
    conv_items = page.locator("[data-e2e='conversation-item']")
    for i in range(conv_items.count()):
        if nickname in (conv_items.nth(i).text_content() or ""):
            conv_items.nth(i).click()
            time.sleep(5)
            return True

    # Method 3: Navigate via profile → 私信
    if sec_uid:
        return open_chat_via_profile(page, sec_uid, nickname)

    return False
