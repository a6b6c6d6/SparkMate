"""Fetch ALL mutual-follow friends from douyin.com/chat im/user/info API."""
import os, sys, time, json
from dotenv import load_dotenv
load_dotenv(".env")

from playwright.sync_api import sync_playwright
from utils.config import get_userData

USER_DATA_DIR = os.path.join(os.path.dirname(__file__), "browser_data")
OUTPUT_FILE = os.path.join(os.path.dirname(__file__), "friends.json")

user = get_userData()[0]
cookies = user["cookies"]

print("[1] Opening douyin.com/chat...")
playwright = sync_playwright().start()
context = playwright.chromium.launch_persistent_context(
    USER_DATA_DIR, headless=False, viewport={"width": 1280, "height": 900}
)
page = context.pages[0] if context.pages else context.new_page()
context.add_cookies(cookies)

friends = {}  # short_id -> friend_data

def on_response(response):
    if "aweme/v1/web/im/user/info/" in response.url:
        try:
            for u in response.json().get("data", []):
                sid = str(u.get("short_id", ""))
                if not sid or sid in friends:
                    continue
                fs = u.get("follow_status", 0)
                frs = u.get("follower_status", 0)
                if fs != 2 or frs != 1:
                    continue
                nick = u.get("nickname", "")
                avatars = []
                for key in ["avatar_small", "avatar_thumb", "avatar_medium"]:
                    if key in u:
                        avatars.extend(u[key].get("url_list", []))
                friends[sid] = {
                    "nickname": nick,
                    "short_id": sid,
                    "unique_id": u.get("unique_id", sid),
                    "sec_uid": u.get("sec_uid", ""),
                    "uid": u.get("uid", ""),
                    "avatars": avatars[:3]
                }
                print(f"  {sid:16s}  {nick}")
        except:
            pass

page.on("response", on_response)
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

time.sleep(10)
print(f"  Initial: {len(friends)} mutual")

# Click + scroll in rounds
print("\n[2] Clicking & scrolling to trigger all APIs...")
conv_selector = "[data-e2e='conversation-item']"
prev_conv_count = 0

for round_num in range(30):
    before = len(friends)

    # Get visible conversations and click them all
    conv_items = page.locator(conv_selector)
    conv_count = conv_items.count()

    for i in range(conv_count):
        try:
            conv_items.nth(i).click(delay=100)
            time.sleep(1.5)
        except:
            pass

    # Scroll aggressively
    for x in [150, 200, 250, 300]:
        page.mouse.move(x, 350)
        for _ in range(4):
            page.mouse.wheel(0, 4000)
            time.sleep(0.3)

    time.sleep(4)

    after = len(friends)
    new_conv = conv_count - prev_conv_count

    if after > before or new_conv > 0:
        print(f"  Round {round_num}: {before}->{after} mutual, {prev_conv_count}->{conv_count} conv")
    elif round_num > 4:
        print(f"  Round {round_num}: all loaded, {after} mutual")
        break

    prev_conv_count = conv_count

context.close()
playwright.stop()

# Save
friend_list = list(friends.values())
friend_list.sort(key=lambda f: f["nickname"])

output = {"friends": friend_list, "total": len(friend_list)}
with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print(f"\n[3] Saved {len(friend_list)} mutual-follow friends to {OUTPUT_FILE}")
for f in friend_list:
    try:
        print(f"  {f['short_id']:16s}  {f['nickname']}")
    except UnicodeEncodeError:
        print(f"  {f['short_id']:16s}  <name>")
