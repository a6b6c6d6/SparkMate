# SparkMate

> 抖音火花伴侣 — 自动续火、发图、发表情、智能用户匹配，一站式抖音好友互动工具。

![Python](https://img.shields.io/badge/Python-3.8%2B-blue?logo=python)
![Playwright](https://img.shields.io/badge/Playwright-%E2%9C%94-green?logo=playwright)

## ✨ 核心功能

| 功能 | 说明 |
|------|------|
| 🖼️ 图片消息发送 | 支持远程 URL / 本地路径自动上传并发送 |
| 😊 表情组合发送 | 自定义表情包 + 文本组合消息 |
| 🔍 智能用户解析 | 昵称 / 备注 / 抖音号 / ShortID 多方式精准匹配 |
| 👥 好友列表构建 | 自动抓取关注/互关列表，生成结构化 JSON |
| 🎯 可视化配置器 | 纯前端好友选择 & 任务配置，一键生成 tasks.json |
| 🤖 无头浏览器 | 默认 Headless 模式，适配服务器 / 定时任务 |
| 📋 批量任务调度 | 通过 tasks.json 配置多目标，一键执行 |

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
playwright install chromium
```

### 🌐 Chromium 浏览器安装与配置

本项目依赖 Chromium 浏览器运行自动化任务。由于浏览器二进制文件体积较大（约 400MB），**不会包含在 Git 仓库中**，首次使用需按以下步骤安装：

#### 方式一：自动安装（强烈推荐）

执行完 `pip install -r requirements.txt` 后，运行以下命令即可自动下载与当前 Playwright 版本完全兼容的 Chromium：

```bash
# 仅安装 Chromium（体积最小，推荐）
playwright install chromium

# 如果系统缺少运行库（常见于 Linux 服务器），可同时安装依赖
playwright install --with-deps chromium
```

安装完成后浏览器会存放在 Playwright 默认缓存目录，脚本会自动识别，**无需任何额外配置**。

#### 方式二：使用本机已安装的 Chrome / Edge

如果你不想重复下载，可以直接复用系统中已有的浏览器：

```bash
# Windows (PowerShell)
$env:CHROME_PATH = "C:\Program Files\Google\Chrome\Application\chrome.exe"

# Windows (CMD)
set CHROME_PATH=C:\Program Files\Google\Chrome\Application\chrome.exe

# macOS
export CHROME_PATH="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

# Linux
export CHROME_PATH="/usr/bin/google-chrome"
```

设置环境变量后运行脚本即可生效。建议将该变量写入系统环境变量或 shell 配置文件（`.bashrc` / `.zshrc`）以持久化。

#### 方式三：手动放置到项目目录

适用于无法联网或需要固定版本的场景：

1. 从 [Playwright 浏览器仓库](https://github.com/microsoft/playwright-browsers) 或 [Chromium 官方快照](https://www.chromium.org/getting-involved/download-chromium/) 下载对应平台的 Chromium
2. 解压到项目根目录，并将文件夹重命名为 `chrome`
3. 确保目录结构为 `SparkMate/chrome/chromium-xxx/chrome.exe`（Windows）或 `chrome`（Linux/macOS）

> ⚠️ **注意：** 无论使用哪种方式，都请确认 `chrome/` 已添加到 `.gitignore`，避免将大文件误提交到仓库。

#### 验证安装

运行以下命令检查浏览器是否就绪：

```bash
python -c "from playwright.sync_api import sync_playwright; p = sync_playwright().start(); b = p.chromium.launch(headless=True); print('✅ Chromium 启动成功'); b.close(); p.stop()"
```

输出 `✅ Chromium 启动成功` 即表示配置完成。

### 2. 配置 Cookie

Cookie 通过 `.env` 文件配置，是维持登录态的核心。需包含以下关键字段：

| 字段 | 必要性 | 说明 |
|------|--------|------|
| `sessionid` | **必填** | 抖音登录会话 ID，最关键鉴权凭证 |
| `passport_csrf_token` | **必填** | CSRF 防护令牌，发消息等写操作必需 |
| `sid_tt` / `uid_tt` / `odin_tt` | 推荐 | 提升请求稳定性，降低风控触发概率 |

**获取方式：** 浏览器登录 [douyin.com](https://www.douyin.com) → F12 → Application → Cookies → 复制对应值。

> ⚠️ Cookie 等同于账号密码，`.env` 已默认加入 `.gitignore`，请勿手动删除该规则。

**`.env` 配置示例（敏感值已替换）：**

```env
# Cookie（JSON 数组格式，一行）
COOKIES_USER1=[{"name":"sessionid","value":"example_session_id","domain":".douyin.com","path":"/"},{"name":"passport_csrf_token","value":"example_csrf_token","domain":".douyin.com","path":"/"}]
```

> 💡 `run_tasks.py` 入口的任务列表从 `tasks.json` 读取（见下方「配置任务」），Cookie 从 `.env` 读取。
> `main.py` 入口支持多用户，任务和 Cookie 均从 `.env` 的 `TASKS` 和 `COOKIES_{UNIQUE_ID}` 读取。

### 3. 配置任务

**方式一：可视化配置器（推荐）**

1. 运行 `python build_friends_json.py` 生成好友数据（`friends.json`）
2. 运行 `python build_picker.py` 生成本地配置器（`docs/friend_picker.local.html`）
3. 浏览器打开 `docs/friend_picker.local.html`
4. 勾选好友、配置动作（文字/图片/表情/自定义），点击「导出 JSON」或「一键复制」
5. 将复制的内容保存为 `tasks.json`

> 💡 `friends.json` 和 `docs/friend_picker.local.html` 都包含真实好友信息，已加入 `.gitignore`，请不要提交。仓库中的 `docs/friend_picker.html` 仅保留空数据模板。

**方式二：手动编辑**

直接编辑 `tasks.json`，格式如下：

```json
{
  "tasks": [
    {"target": "好友昵称", "actions": [1, 2, 3]},
    {"target": "另一个好友", "actions": [3], "message": "自定义文字"}
  ]
}
```

其中 `actions`：`1`=文字（一言） `2`=图片 `3`=续火花表情 `0`=自定义文字

> 为避免聊天搜索把好友昵称误匹配到群聊或最近消息，`run_tasks.py` 会先从
> `friends.json` 读取目标好友的 `sec_uid`。如果命中缓存，会优先打开用户主页再点
> 「私信」；只有没有 `sec_uid` 或主页私信打开失败时，才回退到聊天页搜索。
> 因此建议在批量任务前先运行 `python build_friends_json.py` 更新好友缓存。

### 4. 运行

```bash
python run_tasks.py              # 批量执行任务（从 tasks.json 读取）
python send_image.py "好友昵称"   # 发送随机图片（支持昵称/抖音号/sec_uid）
python send_spark_emoji.py "好友昵称"  # 发送表情组合
python build_friends_json.py     # 构建/更新好友列表
python resolve_user.py "昵称或抖音号"  # 解析用户信息
```

**`send_image.py` 三种定位方式：**

```bash
python send_image.py "好友昵称"              # 昵称 → 自动从 friends.json 查 sec_uid → 主页私信
python send_image.py 46618889188           # 抖音号 → 搜索解析 → 主页私信
python send_image.py sec_uid:MS4wLjA...    # 直接 sec_uid → 最快，跳过搜索
python send_image.py "好友" --no-headless  # 有头模式（处理验证码时用）
```

> `send_image.py` 优先走「主页→私信」路由（比聊天搜索更稳定），昵称会自动从 `friends.json` 匹配 sec_uid。有 `friends.json` 时甚至不需要先搜索。

> **两种入口区别：**
> - `run_tasks.py` — **推荐**，从 `tasks.json` 读取任务列表，适合单用户场景
> - `main.py` — 从 `.env` 环境变量读取配置，支持多用户，通过 `core/tasks.py` 执行

### 无头模式（后台运行）

**首次使用建议用可视化浏览器（默认）**，因为抖音可能弹出风控验证（短信验证码 / 滑块验证 / 扫码等），需要手动操作完成。验证通过后浏览器会在 `browser_data/` 目录保存登录状态。

**验证通过后，可改为无头模式实现后台静默运行：**

| 入口 | 如何开启无头 |
|------|------------|
| `run_tasks.py` | 编辑脚本，把 `headless=False` 改为 `headless=True` |
| `build_friends_json.py` 等独立脚本 | 同上，改各自文件里的 `headless` 参数 |
| `main.py` | 编辑 `utils/config.py`，把 `DEBUG = True` 改为 `DEBUG = False` |
| `send_image.py` | 默认已开启无头，可用 `HEADLESS=0` 切换或 `--no-headless` 参数 |

```python
# 以 run_tasks.py 为例，找到这一行（约第 186 行）：
context = playwright.chromium.launch_persistent_context(
    USER_DATA_DIR, headless=True, viewport={"width": 1280, "height": 900}  # 改为 True
)
```

> **注意：** 改用无头后如再次触发风控验证，需要切回 `headless=False` 手动过验证，然后再改回去。

### 定时自动运行

火花每 24 小时不互动就会熄灭，建议每天定时跑一次即可。

#### Windows — 任务计划程序

1. 按 `Win+R`，输入 `taskschd.msc`，打开任务计划程序
2. 右侧点击「创建基本任务」→ 名称填 `SparkMate`
3. 触发器选「每天」，设置一个你电脑通常开机的时间（如 20:00）
4. 操作选「启动程序」：
   - 程序：`python`（或 Python 的完整路径，如 `C:\Users\你的用户名\AppData\Local\Programs\Python\Python311\python.exe`）
   - 参数：`run_tasks.py`
   - 起始于：`D:\aaaa\SparkMate`（项目目录路径）
5. 勾选「完成时打开属性对话框」→ 在「条件」选项卡取消勾选「只有在计算机使用交流电源时才…」（如果用笔记本）
6. 点击确定保存

> 运行 `python run_tasks.py` 会执行 `tasks.json` 中所有好友的续火花动作。若只想给特定好友发，提前编辑 `tasks.json`。

#### Linux / macOS — cron

```bash
# 编辑 crontab
crontab -e

# 添加一行：每天 20:00 执行（改成你的项目路径）
0 20 * * * cd /path/to/SparkMate && /usr/bin/python run_tasks.py >> logs/cron.log 2>&1
```

```bash
# 验证定时任务已添加
crontab -l

# 如果只需发图或发表情给单个好友：
0 20 * * * cd /path/to/SparkMate && /usr/bin/python send_image.py "好友昵称" >> logs/cron.log 2>&1
```

#### 运行频率建议

| 建议 | 说明 |
|------|------|
| 每天 1 次 | 推荐，足够维持火花，不会触发风控 |
| 每天 2 次 | 可接受，早晚各一次 |
| 每小时 | ⚠️ 不推荐，高频率易触发账号风控 |

### 环境变量配置（.env）

`.env` 主要用于配置 Cookie 凭据和全局参数。**推荐使用 `run_tasks.py` 入口**，任务从 `tasks.json` 读取，Cookie 从 `.env` 读取。

**`.env` 参考：**

| 变量 | 必填 | 说明 |
|------|------|------|
| `COOKIES_{UNIQUE_ID}` | **必填** | 对应用户的抖音 Cookie（JSON 数组格式） |
| `HEADLESS` | 可选 | `1`=无头模式（默认），`0`=有头模式（调试/过验证用） |
| `MATCH_MODE` | 可选 | 好友匹配模式：`nickname`（默认）或 `short_id` |
| `LOG_LEVEL` | 可选 | 日志级别：`DEBUG` / `INFO` / `WARNING` / `ERROR` |
| `MESSAGE_TEMPLATE` | 可选 | 消息模板，默认使用一言 API 随机内容 |
| `BROWSER_TIMEOUT` | 可选 | 浏览器操作超时（毫秒，默认 `120000`） |

> ⚠️ `.env` 包含你的 Cookie 凭据，已默认加入 `.gitignore`，请勿手动删除该规则。

## 📁 项目结构

```
├── core/                  # 核心模块（浏览器控制、消息构建、任务引擎）
├── utils/                 # 工具函数库（配置、日志、一言 API）
├── docs/                  # 文档 & 可视化配置器
│   ├── friend_picker.html       # 好友选择器模板（不含真实好友数据）
│   └── friend_picker.local.html # 本地生成的好友选择器（已 gitignore）
├── send_image.py          # 图片发送
├── send_combo.py          # 组合消息发送（文字+图片+表情）
├── send_spark_emoji.py    # 续火花表情发送
├── resolve_user.py        # 用户解析（昵称/抖音号/sec_uid）
├── resolve_shortid.py     # ShortID → 昵称解析
├── build_friends_json.py  # 好友列表抓取（互关好友）
├── build_picker.py        # 好友选择器 HTML 生成器
├── build_shortid_map.py   # ShortID 映射生成
├── run_tasks.py           # 批量任务调度器（读取 tasks.json）
├── main.py                # 入口（从 .env 读取配置，支持多用户）
├── .env                   # 环境配置（Cookie、任务参数，已 gitignore）
├── tasks.json             # 任务配置（由 friend_picker 生成，已 gitignore）
├── friends.json           # 好友数据缓存（自动生成，已 gitignore）
└── requirements.txt       # Python 依赖
```

## ⚠️ 免责声明

- 本项目仅供**开源学习与技术研究**，严禁用于商业用途或违反平台规则。
- 使用产生的一切风险（限流、封禁等）由使用者自行承担。
- 请合理控制运行频率，避免对平台服务器造成压力。
- 使用即表示已阅读并同意以上条款。

## 📄 开源协议

MIT License · 详见 [LICENSE](LICENSE)

## 🙏 致谢

感谢原项目 [DouYinSparkFlow](https://github.com/2061360308/DouYinSparkFlow) 作者及所有贡献者。
