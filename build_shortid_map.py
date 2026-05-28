"""Build short_id → nickname mapping from douyin.com/chat im/user/info API.
Saves to shortid_map.json for use by other scripts."""
import os, sys, time, json
from dotenv import load_dotenv
load_dotenv(".env")

from playwright.sync_api import sync_playwright
from utils.config import get_userData

USER_DATA_DIR = os.path.join(os.path.dirname(__file__), "browser_data")

user = get_userData()[0]
cookies = user["cookies"]

print("[1] Opening douyin.com/chat, intercepting im/user/info...")
playwright = sync_playwright().start()
context = playwright.chromium.launch_persistent_context(
    USER_DATA_DIR, headless=False, viewport={"width": 1280, "height": 900}
)
page = context.pages[0] if context.pages else context.new_page()
context.add_cookies(cookies)

id_map = {}

def on_response(response):
    if "aweme/v1/web/im/user/info/" in response.url:
        try:
            body = response.json()
            for user in body.get("data", []):
                sid = user.get("short_id", "")
                nick = user.get("nickname", "")
                uid = user.get("unique_id", "")
                if sid:
                    id_map[str(sid)] = {"nickname": nick, "unique_id": uid}
                    print(f"  {sid:16s} → {nick}")
        except Exception as e:
            print(f"  Parse error: {e}")

page.on("response", on_response)
page.goto("https://www.douyin.com/chat", wait_until="load")
time.sleep(12)

# Dismiss dialogs
for _ in range(5):
    for label in ["确认", "保存", "取消"]:
        btn = page.locator(f"button:has-text('{label}')").first
        if btn.count() > 0 and btn.is_visible():
            try:
                btn.click(timeout=2000)
                time.sleep(2)
            except:
                pass

time.sleep(5)

print(f"\n[2] Total: {len(id_map)} users mapped")
for sid, info in id_map.items():
    print(f"  {sid:16s} → {info['nickname']}")

# Save to file
map_file = os.path.join(os.path.dirname(__file__), "shortid_map.json")
with open(map_file, "w", encoding="utf-8") as f:
    json.dump(id_map, f, ensure_ascii=False, indent=2)
print(f"\n  Saved to {map_file}")

# Check for target
target = sys.argv[1] if len(sys.argv) > 1 else None
if target:
    if target in id_map:
        print(f"\n[3] Target {target} → '{id_map[target]['nickname']}'")
    else:
        print(f"\n[3] Target {target} NOT FOUND in mapping")

context.close()
playwright.stop()
