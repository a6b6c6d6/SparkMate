"""Read tasks.json and execute spark-renewal actions for each target.

Actions: 0=custom text, 1=random text, 2=random image, 3=spark emoji,
4=random video. Multiple action codes run in sequence.
"""
import os, sys, time, json, tempfile, urllib.request
from dotenv import load_dotenv
load_dotenv(".env")

from playwright.sync_api import sync_playwright
from media_sources import fetch_random_image_data, fetch_random_video_url
from utils.config import get_userData
from resolve_user import dismiss_dialogs, find_or_open_chat, resolve_via_search

BASE_DIR = os.path.dirname(__file__)
USER_DATA_DIR = os.path.join(BASE_DIR, "browser_data")
TASKS_FILE = os.getenv("TASKS_FILE", os.path.join(BASE_DIR, "tasks.json"))
if not os.path.isabs(TASKS_FILE):
    TASKS_FILE = os.path.join(BASE_DIR, TASKS_FILE)
FRIENDS_FILE = os.path.join(BASE_DIR, "friends.json")
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


def find_friend_by_any_field(friends_list, target):
    """Match nickname, uid, sec_uid, short_id, or unique_id."""
    target_lower = target.lower().strip()
    for friend in friends_list:
        if target_lower == friend.get("nickname", "").lower():
            return friend["nickname"], friend
        for field in ("uid", "sec_uid", "short_id", "unique_id"):
            if target_lower == str(friend.get(field, "")).lower():
                return friend["nickname"], friend
    return None, None


def auto_update_task_target(tasks, index, new_nickname):
    """Update a task when a cached identifier resolves to a new nickname."""
    tasks[index]["target"] = new_nickname
    with open(TASKS_FILE, "w", encoding="utf-8") as file:
        json.dump(
            {
                "_说明": (
                    "target 填昵称或抖音号, actions: 0=自定义文字 "
                    "1=文字 2=图片 3=表情 4=视频"
                ),
                "tasks": tasks,
            },
            file,
            ensure_ascii=False,
            indent=2,
        )


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
    """Upload and send a random high-resolution image."""
    tmp_name = None
    try:
        image_data = fetch_random_image_data()
        tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
        tmp.write(image_data)
        tmp.close()
        tmp_name = tmp.name

        file_input = page.locator("input[type='file']").first
        file_input.set_input_files(tmp_name)

        modal_btn = page.locator("button.MsgInputSendFileModalbtnSure").first
        modal_btn.wait_for(state="visible", timeout=30000)
        modal_btn.click(timeout=5000)
        modal_btn.wait_for(state="hidden", timeout=90000)
        page.wait_for_timeout(5000)
        return True
    except Exception as exc:
        print(f"    Failed to send image: {exc}")
        return False
    finally:
        if tmp_name and os.path.exists(tmp_name):
            os.unlink(tmp_name)


def send_video(page, category=None):
    """Download, upload, and send a random video."""
    tmp_name = None
    try:
        video_url = fetch_random_video_url(category)
        request = urllib.request.Request(
            video_url, headers={"User-Agent": "Mozilla/5.0"}
        )
        with urllib.request.urlopen(request, timeout=60) as response:
            video_data = response.read()
        if len(video_data) < 1024:
            raise RuntimeError("video download returned an empty payload")

        tmp = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
        tmp.write(video_data)
        tmp.close()
        tmp_name = tmp.name

        file_input = page.locator("input[type='file']").first
        file_input.set_input_files(tmp_name)

        modal_btn = page.locator("button.MsgInputSendFileModalbtnSure").first
        modal_btn.wait_for(state="visible", timeout=30000)
        modal_btn.click(timeout=5000, delay=500)
        modal_btn.wait_for(state="hidden", timeout=90000)
        page.wait_for_timeout(10000)
        return True
    except Exception as exc:
        print(f"    Failed to send video: {exc}")
        return False
    finally:
        if tmp_name and os.path.exists(tmp_name):
            os.unlink(tmp_name)


def send_spark_emoji(page):
    """Open emoji panel and click 续火花 emoji."""
    emoji_button_selectors = [
        "svg.messageMsgInputiconAction",
        "[class*='iconAction']",
        "[class*='emojiIcon']",
        "[class*='MsgInput'] [class*='icon']",
    ]
    clicked = False
    for selector in emoji_button_selectors:
        try:
            locator = page.locator(selector).first
            if locator.count() > 0 and locator.is_visible():
                locator.click(force=True, timeout=3000)
                clicked = True
                break
        except Exception:
            continue
    if not clicked:
        page.evaluate("""() => {
            const input = document.querySelector('[contenteditable="true"]');
            const root = input?.closest('[class*="Input"]') || input?.parentElement;
            const icons = root?.querySelectorAll('svg') || [];
            for (const icon of icons) {
                const cls = icon.className?.baseVal || '';
                if (cls.includes('iconAction') || cls.includes('emoji')) {
                    icon.click();
                    return;
                }
            }
        }""")

    emoji_selectors = [
        "[class*='emojiEmojiItem']",
        "[class*='emojiItem']",
        "[class*='EmojiItem']",
    ]
    try:
        page.wait_for_selector(
            ", ".join(emoji_selectors), state="visible", timeout=5000
        )
    except Exception:
        return False

    emoji_items = None
    for selector in emoji_selectors:
        candidates = page.locator(selector)
        if any(
            candidates.nth(index).is_visible()
            for index in range(candidates.count())
        ):
            emoji_items = candidates
            break
    if emoji_items is None:
        return False
    count = emoji_items.count()

    spark_index = None
    for index in range(count):
        if not emoji_items.nth(index).is_visible():
            continue
        text = (emoji_items.nth(index).text_content() or "").strip()
        if "火花" in text:
            spark_index = index
            break

    if spark_index is None:
        return False
    emoji_items.nth(spark_index).click(
        force=True, timeout=2000, delay=100
    )
    time.sleep(0.5)
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
        elif action_code == 4:
            video_category = (
                task.get("video_msg")
                or task.get("video_category")
                or task.get("msg")
            )
            handler = lambda p, category=video_category: send_video(
                p, category
            )
            name = f"随机视频({video_category or '随机'})"
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

    page = context.pages[0] if context.pages else context.new_page()
    context.add_cookies(cookies)
    page.goto("https://www.douyin.com/chat", wait_until="domcontentloaded")
    try:
        page.wait_for_selector(
            "input[placeholder*='搜索'], [data-e2e='conversation-item'], "
            "[contenteditable='true']",
            state="visible",
            timeout=15000,
        )
    except Exception:
        pass
    dismiss_dialogs(page)

    verification = page.locator("input[name='normal-input']")
    if verification.count() > 0 and verification.first.is_visible():
        print("*** 需要验证码 ***")
        try:
            verification.first.wait_for(state="hidden", timeout=120000)
        except Exception:
            print("Verification timed out; stopping without sending.")
            context.close()
            playwright.stop()
            return

    for idx, task in enumerate(tasks):
        target = str(task.get("target", "")).strip()
        if not target:
            continue

        print(f"[Task {idx+1}/{len(tasks)}] {target}")

        # Resolve the target to a nickname and stable identity key.
        sec_uid = ""
        if target.isdigit():
            cached = next(
                (
                    friend
                    for friend in friends.values()
                    if str(friend.get("short_id", "")) == target
                ),
                None,
            )
            if cached:
                nickname = cached["nickname"]
                sec_uid = cached.get("sec_uid", "")
                print(
                    f"  -> found in cache (short_id={target}, "
                    f"nickname='{nickname}')"
                )
            else:
                resolved = resolve_via_search(
                    target, cookies, USER_DATA_DIR, None
                )
                if resolved:
                    nickname = resolved["nickname"]
                    sec_uid = resolved["sec_uid"]
                    print(f"  -> '{nickname}'")
                else:
                    print(f"  WARNING: could not resolve {target}, skipping")
                    continue
        else:
            nickname = target
            friend = friends.get(nickname)
            if friend:
                sec_uid = friend.get("sec_uid", "")
                print(f"  -> found in friends cache (sec_uid={sec_uid[:30]}...)")
            else:
                current_nickname, matched = find_friend_by_any_field(
                    list(friends.values()), target
                )
                if matched:
                    nickname = current_nickname
                    sec_uid = matched.get("sec_uid", "")
                    print(
                        f"  >> Nickname changed: '{target}' -> "
                        f"'{current_nickname}', updating tasks.json"
                    )
                    auto_update_task_target(tasks, idx, current_nickname)
                else:
                    print(
                        "  [!] Not in friends cache; trying exact chat "
                        "fallback"
                    )

        if sec_uid:
            print("  Opening verified direct chat...")
            if not find_or_open_chat(page, nickname, sec_uid):
                print(f"  ERROR: could not open chat with '{nickname}'")
                continue
        elif not find_or_open_chat(page, nickname, ""):
            print(
                f"  ERROR: could not open chat with '{nickname}' "
                "(no sec_uid fallback)"
            )
            continue

        page.evaluate("""() => {
            const panel = document.querySelector('[class*="ConversationInfoopen"]');
            if (panel) panel.classList.remove('conversationConversationInfoopen');
        }""")
        # Execute actions
        run_single_target(page, task)
        print()

    context.close()
    playwright.stop()
    print("All tasks done!")


if __name__ == "__main__":
    main()
