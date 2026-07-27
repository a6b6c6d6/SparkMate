"""Resolve Douyin users and open verified direct-message conversations."""
import re
import time

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError


CHAT_INPUT_SELECTOR = "[contenteditable='true']"


def dismiss_dialogs(page):
    """Dismiss currently visible confirmation dialogs without fixed delays."""
    for _ in range(3):
        clicked = False
        for label in ["确认", "保存", "取消"]:
            button = page.get_by_role("button", name=label, exact=True).first
            try:
                if button.is_visible():
                    button.click(timeout=1500)
                    clicked = True
            except Exception:
                pass
        if not clicked:
            break


def wait_for_chat_ready(page, timeout=10000):
    """Return as soon as the chat composer is usable."""
    try:
        page.locator(CHAT_INPUT_SELECTOR).first.wait_for(
            state="visible", timeout=timeout
        )
        return True
    except PlaywrightTimeoutError:
        return False

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
    dismiss_dialogs(page)

    button = page.get_by_role(
        "button", name=re.compile(r"^(私信|发消息|聊天)$")
    ).first
    try:
        button.wait_for(state="visible", timeout=15000)
        button.click(force=True, timeout=5000)
        if wait_for_chat_ready(page):
            return True
        print("    open_chat_via_profile: chat input did not become ready")
    except Exception as exc:
        print(f"    open_chat_via_profile: click failed - {exc}")

    # Fallback: JS click bypasses Playwright pointer-event interception.
    js_result = page.evaluate("""() => {
        const btns = document.querySelectorAll('button');
        for (const btn of btns) {
            const text = btn.textContent?.trim();
            if (text === '私信' || text === '发消息' || text === '聊天') {
                if (btn.offsetParent !== null) {
                    btn.click();
                    return 'clicked: ' + text;
                }
            }
        }
        return 'not found';
    }""")
    if js_result.startswith('clicked'):
        print(f"    open_chat_via_profile: {js_result} (JS fallback)")
        return wait_for_chat_ready(page)

    print(
        "    open_chat_via_profile: no 私信/发消息/聊天 button found "
        f"(url={page.url})"
    )
    return False


def find_or_open_chat(page, nickname, sec_uid):
    """Try to find user via chat search, fallback to profile→私信.
    Returns True if chat was opened."""
    # Only click a search result when its profile link proves the expected
    # sec_uid. Nickname-only search can otherwise select a group or namesake.
    search_box = page.locator("input[placeholder*='搜索']").first
    try:
        search_box.wait_for(state="visible", timeout=3000)
        search_box.fill(nickname)
        page.locator(".SearchPanelitemchat_btn").first.wait_for(
            state="visible", timeout=5000
        )
    except PlaywrightTimeoutError:
        search_box = None

    if search_box and sec_uid:
        profile_link = page.locator(f"a[href*='/user/{sec_uid}']").first
        try:
            profile_link.wait_for(state="visible", timeout=2000)
            result = profile_link.locator(
                "xpath=ancestor::*[.//*[contains(@class, "
                "'SearchPanelitemchat_btn')]][1]"
            )
            chat_button = result.locator(".SearchPanelitemchat_btn").first
            if chat_button.is_visible():
                chat_button.click(timeout=3000)
                chat_button.wait_for(state="hidden", timeout=5000)
                if wait_for_chat_ready(page):
                    return True
        except Exception:
            pass

    # Method 2: Check conversation list
    # Without an identity key, accept only a direct conversation whose first
    # visible line exactly matches the nickname.
    if not sec_uid:
        conversation_items = page.locator("[data-e2e='conversation-item']")
        for index in range(conversation_items.count()):
            lines = [
                line.strip()
                for line in (
                    conversation_items.nth(index).inner_text() or ""
                ).splitlines()
                if line.strip()
            ]
            if lines and lines[0] == nickname:
                conversation_items.nth(index).click()
                if wait_for_chat_ready(page):
                    return True

    # Method 3: Navigate via profile → 私信
    if sec_uid:
        return open_chat_via_profile(page, sec_uid, nickname)

    return False
