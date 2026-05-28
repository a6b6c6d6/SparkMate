"""Send hitokoto text + random image + emoji to a Douyin friend"""
import os, sys, time, json, tempfile, urllib.request
from dotenv import load_dotenv
load_dotenv(".env")

from playwright.sync_api import sync_playwright
from utils.config import get_userData

user = get_userData()[0]
cookies = user["cookies"]
target = sys.argv[1] if len(sys.argv) > 1 else "没有名字"
USER_DATA_DIR = os.path.join(os.path.dirname(__file__), "browser_data")

# ====== PART 1: Send text via creator center ======
print("[1] Sending hitokoto...")
req = urllib.request.Request("https://api.ku.cm/hitokoto/?type=json", headers={"User-Agent": "Mozilla/5.0"})
hitokoto = json.loads(urllib.request.urlopen(req).read())["data"]["text"]
print(f"  {hitokoto}")

import json as _json
is_short_id = target.isdigit()
os.environ["MESSAGE_TEMPLATE"] = hitokoto
os.environ["HITOKOTO_TYPES"] = "[]"
os.environ["TASK_RETRY_TIMES"] = "1"
os.environ["MATCH_MODE"] = "short_id" if is_short_id else "nickname"
os.environ["TASKS"] = _json.dumps([{"username": target, "unique_id": "USER1", "targets": [target]}], ensure_ascii=False)

import utils.config as _cfg
_cfg.config = None
_cfg.userData = None

from core.tasks import runTasks
import core.tasks as _tasks
runTasks()
print("  Text sent!\n")

# Resolve nickname from short_id
if is_short_id:
    info = _tasks.userIDDict.get(target, {})
    chat_target = info.get("nickname", "")
    sec_uid = info.get("user_id", "")  # Not sec_uid from creator API
    if chat_target:
        print(f"  Resolved via creator API: {target} -> '{chat_target}'\n")
    else:
        # Fallback to douyin.com search
        from resolve_user import resolve_via_search
        resolved = resolve_via_search(target, cookies, USER_DATA_DIR, None)
        if resolved:
            chat_target = resolved["nickname"]
            sec_uid = resolved["sec_uid"]
            print(f"  Resolved via search: {target} -> '{chat_target}'\n")
        else:
            chat_target = target
            sec_uid = ""
            print(f"  WARNING: could not resolve {target}\n")
else:
    chat_target = target
    sec_uid = ""

# ====== PART 2: Send emoji + image via douyin.com/chat ======
print("[2] Fetching image...")
req = urllib.request.Request("https://api.ku.cm/images/?type=json", headers={"User-Agent": "Mozilla/5.0"})
img_url = _json.loads(urllib.request.urlopen(req).read())["data"]["url"]
print(f"  {img_url}")
req = urllib.request.Request(img_url, headers={"User-Agent": "Mozilla/5.0"})
img_data = urllib.request.urlopen(req).read()
tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
tmp.write(img_data)
tmp.close()

print("[3] Opening douyin.com/chat...")
os.makedirs(USER_DATA_DIR, exist_ok=True)
playwright = sync_playwright().start()
context = playwright.chromium.launch_persistent_context(
    USER_DATA_DIR, headless=False, viewport={"width": 1280, "height": 900}
)
page = context.pages[0] if context.pages else context.new_page()

context.add_cookies(cookies)
page.goto("https://www.douyin.com/chat", wait_until="domcontentloaded")
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

verify = page.locator("input[name='normal-input']")
if verify.count() > 0 and verify.first.is_visible():
    print("  *** 需要验证码 ***")
    for _ in range(60):
        if verify.count() == 0 or not verify.first.is_visible():
            break
        time.sleep(2)
    time.sleep(5)

# Search + open chat
print(f"[4] Opening chat with '{chat_target}'...")
from resolve_user import find_or_open_chat
if not find_or_open_chat(page, chat_target, sec_uid if is_short_id else ""):
    print(f"  ERROR: could not open chat with '{chat_target}'")
    context.close()
    playwright.stop()
    sys.exit(1)
print("  Chat opened!")
time.sleep(5)

# Close any side panel that might block the toolbar
page.evaluate("""() => {
    const panel = document.querySelector('[class*="ConversationInfoopen"]');
    if (panel) panel.classList.remove('conversationConversationInfoopen');
}""")
time.sleep(1)

# ====== SEND EMOJI (click = send directly) ======
print("[5] Sending emoji...")
# Click emoji button
page.locator("svg.messageMsgInputiconAction").first.click(force=True, timeout=3000)
time.sleep(3)

# Click a random fun emoji (not 续火花)
emoji_items = page.locator("[class*='emojiEmojiItem']")
count = emoji_items.count()
print(f"  {count} emojis available")

# Try a few fun ones: 比心(3), 送朵花(6), 在干嘛(9), 笑死(12), 躺平(18)
emoji_idx = 3  # 比心
text = emoji_items.nth(emoji_idx).text_content() or ""
print(f"  Clicking [{emoji_idx}] {text}")
emoji_items.nth(emoji_idx).click(force=True, timeout=2000, delay=100)
time.sleep(2)
print("  Emoji sent!")

# ====== SEND IMAGE ======
print("[6] Sending image...")

file_input = page.locator("input[type='file']").first
file_input.set_input_files(tmp.name)
print("  File selected, waiting for modal...")

# Wait for the modal send button to appear
for i in range(10):
    time.sleep(1)
    modal_btn = page.locator("button.MsgInputSendFileModalbtnSure").first
    if modal_btn.count() > 0 and modal_btn.is_visible():
        print(f"  Modal ready, clicking send...")
        time.sleep(0.5)
        # Click triggers the upload chain: upload config → TOS → batch_build_image → message/send
        modal_btn.click(force=True, timeout=3000, delay=500)
        page.evaluate("""() => {
            const btn = document.querySelector('button.MsgInputSendFileModalbtnSure');
            if (btn) btn.click();
        }""")
        print(f"  Send clicked!")
        break
else:
    print("  Modal did not appear, trying anyway...")
    modal_btn = page.locator("button.MsgInputSendFileModalbtnSure").first
    if modal_btn.count() > 0 and modal_btn.is_visible():
        modal_btn.click(force=True, timeout=3000, delay=500)

# Wait for modal to close (indicates message was sent)
for i in range(20):
    time.sleep(1.5)
    modal = page.locator("[class*='MsgInputSendFileModal']").first
    if modal.count() == 0 or not modal.is_visible():
        print(f"  Modal closed — image sent!")
        break
    if i % 4 == 0:
        print(f"  Waiting for modal to close... ({i})")
else:
    print(f"  Modal still open after wait, but message may have sent")

print("Done!")
context.close()
playwright.stop()
