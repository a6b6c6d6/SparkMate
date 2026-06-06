"""Read tasks.json and execute spark-renewal actions for each target.
Actions: 1=random text(一言), 2=random image, 3=续火花 emoji, 0=custom text (needs "message" field).
Supports 一键三连: actions: [1, 2, 3] sends all three in sequence."""
import os, sys, time, json, tempfile, urllib.request
from dotenv import load_dotenv
load_dotenv(".env")

from playwright.sync_api import sync_playwright
from utils.config import get_userData
from resolve_user import resolve_via_search, find_or_open_chat, open_chat_via_profile

USER_DATA_DIR = os.path.join(os.path.dirname(__file__), "browser_data")
TASKS_FILE = os.path.join(os.path.dirname(__file__), "tasks.json")
FRIENDS_FILE = os.path.join(os.path.dirname(__file__), "friends.json")
HEADLESS = os.getenv("HEADLESS", "1") == "1"


def load_tasks():
    with open(TASKS_FILE, "r", encoding="utf-8") as f:
        config = json.load(f)
    return config["tasks"]


def load_friends():
    """Load friends.json for nickname → sec_uid fallback lookup."""
    if not os.path.exists(FRIENDS_FILE):
        return {}
    try:
        with open(FRIENDS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return {f["nickname"]: f for f in data.get("friends", [])}
    except:
        return {}


def send_hitokoto(page):
    """Send a random hitokoto text via the current chat input."""
    try:
        req = urllib.request.Request("https://api.ku.cm/hitokoto/?type=json",
                                     headers={"User-Agent": "Mozilla/5.0"})
        text = json.loads(urllib.request.urlopen(req).read())["data"]["text"]
    except:
        text = "火花🔥"
    print(f"    -> {text}")

    editable = page.locator("[contenteditable='true']").first
    if editable.count() > 0:
        editable.click()
        time.sleep(0.3)
        # Clear and type
        page.evaluate(f"""(t) => {{
            const el = document.querySelector('[contenteditable="true"]');
            if (el) {{
                el.textContent = t;
                el.dispatchEvent(new Event('input', {{bubbles: true}}));
            }}
        }}""", text)
        time.sleep(0.5)
        # Click send button
        send_btn = page.locator(".e2e-send-msg-btn").first
        if send_btn.count() > 0:
            send_btn.click(force=True, timeout=3000)
        else:
            page.keyboard.press("Enter")
        time.sleep(2)
        return True
    return False


def send_image(page):
    """Upload and send a random image."""
    try:
        req = urllib.request.Request("https://api.ku.cm/images/?type=json",
                                     headers={"User-Agent": "Mozilla/5.0"})
        img_url = json.loads(urllib.request.urlopen(req).read())["data"]["url"]
    except:
        print("    Failed to fetch image")
        return False

    req = urllib.request.Request(img_url, headers={"User-Agent": "Mozilla/5.0"})
    img_data = urllib.request.urlopen(req).read()
    tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
    tmp.write(img_data)
    tmp.close()

    file_input = page.locator("input[type='file']").first
    file_input.set_input_files(tmp.name)

    for i in range(10):
        time.sleep(1)
        modal_btn = page.locator("button.MsgInputSendFileModalbtnSure").first
        if modal_btn.count() > 0 and modal_btn.is_visible():
            modal_btn.click(force=True, timeout=3000, delay=500)
            page.evaluate("""() => {
                const btn = document.querySelector('button.MsgInputSendFileModalbtnSure');
                if (btn) btn.click();
            }""")
            break
    else:
        os.unlink(tmp.name)
        return False

    for i in range(20):
        time.sleep(1.5)
        modal = page.locator("[class*='MsgInputSendFileModal']").first
        if modal.count() == 0 or not modal.is_visible():
            break

    os.unlink(tmp.name)
    return True


def send_spark_emoji(page):
    """Open emoji panel and click 续火花 emoji."""
    # Click emoji button
    page.locator("svg.messageMsgInputiconAction").first.click(force=True, timeout=3000)
    time.sleep(3)

    emoji_items = page.locator("[class*='emojiEmojiItem']")
    count = emoji_items.count()

    spark_idx = 0
    for i in range(count):
        text = (emoji_items.nth(i).text_content() or "").strip()
        if "火花" in text:
            spark_idx = i
            break

    emoji_items.nth(spark_idx).click(force=True, timeout=2000, delay=100)
    time.sleep(2)
    return True


def send_custom_text(page, message):
    """Send a custom text message."""
    print(f"    -> {message}")
    editable = page.locator("[contenteditable='true']").first
    if editable.count() > 0:
        editable.click()
        time.sleep(0.3)
        page.evaluate(f"""(t) => {{
            const el = document.querySelector('[contenteditable="true"]');
            if (el) {{
                el.textContent = t;
                el.dispatchEvent(new Event('input', {{bubbles: true}}));
            }}
        }}""", message)
        time.sleep(0.5)
        send_btn = page.locator(".e2e-send-msg-btn").first
        if send_btn.count() > 0:
            send_btn.click(force=True, timeout=3000)
        else:
            page.keyboard.press("Enter")
        time.sleep(2)
        return True
    return False


ACTION_MAP = {
    1: ("随机文字", send_hitokoto),
    2: ("随机图片", send_image),
    3: ("续火花",   send_spark_emoji),
}


def run_single_target(page, task):
    """Execute all actions for one target."""
    actions = task.get("actions", [3])
    print(f"  Actions: {actions}")

    for i, action_code in enumerate(actions):
        if action_code == 0:
            # Custom text
            message = task.get("message", "火花")
            handler = lambda p: send_custom_text(p, message)
            name = f"自定义文字"
        elif action_code in ACTION_MAP:
            name, handler = ACTION_MAP[action_code]
        else:
            print(f"    Unknown action {action_code}, skipping")
            continue

        print(f"  [{i+1}/{len(actions)}] {name}...", end=" ", flush=True)
        ok = handler(page)
        print("OK" if ok else "FAIL")

        if i < len(actions) - 1:
            time.sleep(2)  # Brief pause between actions


def main():
    user = get_userData()[0]
    cookies = user["cookies"]
    tasks = load_tasks()
    friends = load_friends()

    print(f"Loaded {len(tasks)} task(s), {len(friends)} friends in cache\n")

    playwright = sync_playwright().start()
    context = playwright.chromium.launch_persistent_context(
        USER_DATA_DIR, headless=HEADLESS, viewport={"width": 1280, "height": 900}
    )

    for idx, task in enumerate(tasks):
        target = str(task.get("target", "")).strip()
        if not target:
            continue

        print(f"[Task {idx+1}/{len(tasks)}] {target}")

        # Resolve target → nickname + sec_uid
        sec_uid = ""
        if target.isdigit():
            resolved = resolve_via_search(target, cookies, USER_DATA_DIR, None)
            if resolved:
                nickname = resolved["nickname"]
                sec_uid = resolved["sec_uid"]
                print(f"  -> '{nickname}'")
            else:
                print(f"  WARNING: could not resolve {target}, skipping")
                continue
        else:
            nickname = target
            # Look up sec_uid from friends.json as fallback
            friend = friends.get(nickname)
            if friend:
                sec_uid = friend.get("sec_uid", "")
                print(f"  -> found in friends cache (sec_uid={sec_uid[:30]}...)")

        # Open browser for this target
        page = context.pages[0] if context.pages else context.new_page()
        context.add_cookies(cookies)

        # Route A: sec_uid known → profile→DM (most reliable)
        # Prefer profile -> 私信 when sec_uid is available. Chat search can return
        # group conversations whose recent messages/member names match the nickname.
        chat_opened = False
        if sec_uid:
            print(f"  Opening via profile -> 私信 (sec_uid exact match)...")
            chat_opened = open_chat_via_profile(page, sec_uid, nickname)
            if chat_opened:
                # Wait for chat UI to render
                try:
                    page.wait_for_selector("[contenteditable='true']", timeout=15000)
                except:
                    pass
            else:
                print(f"  Profile open failed, trying chat search...")

        # Route B: fallback → /chat page
        if not chat_opened:
            page.goto("https://www.douyin.com/chat", wait_until="domcontentloaded")
            time.sleep(3)
            try:
                page.wait_for_selector("[data-e2e='conversation-item']", timeout=15000)
            except:
                pass

            # Dismiss dialogs
            for _ in range(5):
                for label in ["确认", "保存", "取消"]:
                    for btn in page.locator(f"button:has-text('{label}')").all():
                        try:
                            if btn.is_visible():
                                btn.click(timeout=2000)
                                time.sleep(2)
                        except:
                            pass

            verify = page.locator("input[name='normal-input']")
            if verify.count() > 0 and verify.first.is_visible():
                print("  *** 需要验证码 ***")
                for _ in range(60):
                    if verify.count() == 0 or not verify.first.is_visible():
                        break
                    time.sleep(2)
                time.sleep(5)

            chat_opened = find_or_open_chat(page, nickname, sec_uid)

        if not chat_opened:
            print(f"  ERROR: could not open chat with '{nickname}'")
            continue

        page.evaluate("""() => {
            const panel = document.querySelector('[class*="ConversationInfoopen"]');
            if (panel) panel.classList.remove('conversationConversationInfoopen');
        }""")
        time.sleep(1)

        # Execute actions
        run_single_target(page, task)
        print()

    context.close()
    playwright.stop()
    print("All tasks done!")


if __name__ == "__main__":
    main()
