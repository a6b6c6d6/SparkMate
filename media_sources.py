"""Random image and video providers used by the sending commands."""

import json
import random
import urllib.parse
import urllib.request


VIDEO_CATEGORIES = ["明星", "热舞", "风景", "游戏", "动物", "动漫"]


def download_image(url):
    """Download an image and reject HTML/error payloads."""
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        content_type = response.headers.get("Content-Type", "").lower()
        image_data = response.read()
        final_url = response.geturl()
    if not content_type.startswith("image/") or len(image_data) < 1024:
        raise RuntimeError(
            f"invalid image response ({content_type or 'unknown type'})"
        )
    return image_data, final_url


def _fetch_bing_uhd_image():
    api_url = (
        "https://www.bing.com/HPImageArchive.aspx"
        "?format=js&idx=0&n=8&mkt=zh-CN"
    )
    request = urllib.request.Request(
        api_url, headers={"User-Agent": "Mozilla/5.0"}
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        images = json.loads(response.read()).get("images", [])
    if not images:
        raise RuntimeError("Bing returned no images")
    image = random.choice(images)
    image_url = "https://www.bing.com" + image["urlbase"] + "_UHD.jpg"
    return download_image(image_url)


def fetch_random_image_data():
    """Fetch a random 4K image, with tested HD services as fallbacks."""
    four_k_sources = [
        ("Bing UHD 4K", _fetch_bing_uhd_image),
        ("Picsum 4K", lambda: download_image("https://picsum.photos/3840/2160")),
    ]
    hd_fallbacks = [
        ("dmoe HD", lambda: download_image("https://www.dmoe.cc/random.php")),
        (
            "mtyqx HD",
            lambda: download_image("https://api.mtyqx.cn/tapi/random.php"),
        ),
    ]
    random.shuffle(four_k_sources)
    random.shuffle(hd_fallbacks)

    errors = []
    for source_name, fetcher in four_k_sources + hd_fallbacks:
        try:
            image_data, final_url = fetcher()
            print(f"    -> {source_name}: {final_url}")
            return image_data
        except Exception as exc:
            errors.append(f"{source_name}: {exc}")
            print(f"    Image source failed ({source_name}): {exc}")
    raise RuntimeError("; ".join(errors))


def fetch_random_video_url(category=None):
    """Return a random MP4 URL from api.4qb.cn."""
    if not category or category == "随机":
        category = random.choice(VIDEO_CATEGORIES)
    params = urllib.parse.urlencode({"msg": category, "type": "json"})
    api_url = "http://api.4qb.cn/api/suiji-sp?" + params
    request = urllib.request.Request(
        api_url, headers={"User-Agent": "Mozilla/5.0"}
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        payload = json.loads(response.read().decode("utf-8", errors="replace"))

    if str(payload.get("code")) != "1":
        raise RuntimeError(
            payload.get("text")
            or f"unexpected response code: {payload.get('code')}"
        )

    data = payload.get("data")
    if isinstance(data, list):
        if not data:
            raise RuntimeError("empty video data")
        data = data[0]
    if not isinstance(data, dict) or not data.get("url"):
        raise RuntimeError("video url missing in response")

    mold = data.get("mold") or category
    print(f"    -> {mold}: {data['url']}")
    return data["url"]
