
import os
import json
import datetime as dt
import requests
import feedparser
import hashlib
from pathlib import Path
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

P = Path("docs/data.json")
now = dt.datetime.now(ZoneInfo("Asia/Taipei"))
day = now.date() - dt.timedelta(days=1)

data = json.loads(P.read_text(encoding="utf8")) if P.exists() else {"items": []}
seen = {x["id"] for x in data["items"]}
status = {}
counts = {}


def add(source, id, title, url, date, **extra):
    id = source + ":" + str(id)

    if id in seen:
        return False

    seen.add(id)

    data["items"].append(dict(
        source=source,
        id=id,
        title=title,
        url=url,
        date=date,
        batch=str(now.date()),
        **extra
    ))

    counts[source] = counts.get(source, 0) + 1
    return True


def news():
    r = requests.get(
        "https://news.google.com/rss/search",
        params={
            "q": "설인아 when:7d",
            "hl": "ko",
            "gl": "KR",
            "ceid": "KR:ko"
        },
        timeout=35
    )

    r.raise_for_status()
    f = feedparser.parse(r.content)

    if f.bozo and not f.entries:
        raise ValueError("RSS parse error")

    for e in f.entries:
        add(
            "news",
            e.get("id", e.link),
            e.title,
            e.link,
            e.get("published", "")
        )


def normalize(url):
    u = urlsplit(url)

    query = "&".join(
        p for p in u.query.split("&")
        if p and not p.lower().startswith(
            ("utm_", "fbclid=", "gclid=")
        )
    )

    return u._replace(
        fragment="",
        query=query
    ).geturl()


def photos():
    key = os.getenv("SERPAPI_KEY")

    if not key:
        return "未設定 SERPAPI_KEY"

    added = 0
    skipped = 0
    total = 0

    images = set()

    for item in data["items"]:
        if item.get("source") == "photo":
            for field in ("image", "original_image"):
                value = item.get(field)
                if value:
                    images.add(normalize(value))

    queries = [
        "설인아 포토 뉴스",
        "설인아 기자 사진"
    ]

    for q in queries:
        r = requests.get(
            "https://serpapi.com/search.json",
            params={
                "engine": "google_images",
                "q": q,
                "gl": "kr",
                "hl": "ko",
                "api_key": key
            },
            timeout=45
        )

        r.raise_for_status()
        j = r.json()

        if j.get("error"):
            raise ValueError("SerpApi returned an error")

        rows = j.get("images_results", [])
        total += len(rows)

        print("Search:", q)
        print("Image results:", len(rows))

        for e in rows:
            title = e.get("title") or "설인아"
            url = e.get("link") or ""
            original = e.get("original") or ""
            thumbnail = e.get("thumbnail") or ""
            publisher = e.get("source") or ""

            image = next(
                (v for v in (thumbnail, original)
                 if isinstance(v, str)
                 and v.startswith("https://")),
                ""
            )

            if not image or not url.startswith("https://"):
                skipped += 1
                print("Skipped: missing image or link")
                continue

            keys = {
                normalize(v)
                for v in (image, original)
                if isinstance(v, str)
                and v.startswith("https://")
            }

            if keys & images:
                skipped += 1
                print("Skipped: duplicate image")
                continue

            photo_id = hashlib.sha256(
                normalize(original or image).encode()
            ).hexdigest()

            if add(
                "photo",
                photo_id,
                title,
                url,
                "",
                image=image,
                original_image=original,
                publisher=publisher,
                collected_at=now.isoformat(),
                candidate=True
            ):
                images.update(keys)
                added += 1
                print("Added:", title)
            else:
                skipped += 1

    print("Total image results:", total)
    print("Added:", added)
    print("Skipped:", skipped)

    return (
        f"搜尋 {total} 張照片；"
        f"新增 {added} 張；"
        f"略過 {skipped} 張"
    )


for name, fn in [
    ("news", news),
    ("photo", photos)
]:
    try:
        status[name] = fn() or "蒐集完成"

    except Exception as e:
        status[name] = (
            "蒐集失敗：" + type(e).__name__
        )
        print(name, status[name])


data.update(
    updated=now.isoformat(),
    target=str(day),
    status=status,
    counts=counts
)

P.parent.mkdir(parents=True, exist_ok=True)

P.write_text(
    json.dumps(data, ensure_ascii=False),
    encoding="utf8"
)
