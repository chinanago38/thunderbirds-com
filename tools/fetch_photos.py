#!/usr/bin/env python3
"""GitHub Actions で実行：tools/photos/targets.tsv のダムごとに、日本語版ウィキペディアの記事に載っている
Wikimedia Commons の写真から、自由ライセンス（PD・CC0・CC BY・CC BY-SA）の写真を1枚選び、
撮影者・ライセンスと一緒に tools/photos/commons.tsv に書き出す。放流・放水の写真を優先する。"""
import json, os, re, time, urllib.parse, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UA = {"User-Agent": "thunderbirds-com-photo-bot/1.0 (https://xn--vckkr8d3i3bb.com/; info@chinanago.jp)"}
PREFER = []
AVOID = ["map", "地図", "location", "logo", "icon", "card", "カード", "svg", "flag", "diagram", "位置", "chart", "emblem", "insignia", "ensign", "seal"]

def api(host, params):
    params = dict(params, format="json")
    url = f"https://{host}/w/api.php?" + urllib.parse.urlencode(params)
    for _ in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
                return json.load(r)
        except Exception:
            time.sleep(2)
    return {}

def strip(s):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", s or "")).strip()

def ok_license(name):
    n = (name or "").lower().replace("-", " ")
    if "nc" in n.split() or " nd" in n or "noncommercial" in n or "noderiv" in n:
        return False
    return n.startswith("cc by") or n.startswith("cc0") or "public domain" in n or n.startswith("pd")

def resolve_title(t):
    d = api("ja.wikipedia.org", {"action": "query", "titles": t, "redirects": 1})
    pages = d.get("query", {}).get("pages", {})
    if pages and "-1" not in pages:
        return list(pages.values())[0]["title"]
    d = api("ja.wikipedia.org", {"action": "query", "list": "search", "srsearch": t, "srlimit": 1})
    hits = d.get("query", {}).get("search", [])
    return hits[0]["title"] if hits else None

def candidates(title):
    files = []
    d = api("ja.wikipedia.org", {"action": "query", "titles": title, "prop": "pageimages|images", "piprop": "name", "imlimit": 50, "redirects": 1})
    for p in d.get("query", {}).get("pages", {}).values():
        if p.get("pageimage"):
            files.append("File:" + p["pageimage"])
        for im in p.get("images", []):
            files.append(im["title"].replace("ファイル:", "File:"))
    seen, out = set(), []
    for f in files:
        if f not in seen and re.search(r"\.(jpe?g|png)$", f, re.I) and not any(a in f.lower() for a in AVOID):
            seen.add(f); out.append(f)
    # 放流・放水の写真を優先
    out.sort(key=lambda f: 0 if any(k in f.lower() for k in PREFER) else 1)
    return out

def info(file):
    d = api("commons.wikimedia.org", {"action": "query", "titles": file, "prop": "imageinfo", "iiprop": "url|extmetadata|size", "iiurlwidth": 1280})
    for p in d.get("query", {}).get("pages", {}).values():
        ii = (p.get("imageinfo") or [None])[0]
        if not ii:
            return None
        md = ii.get("extmetadata", {})
        lic = md.get("LicenseShortName", {}).get("value", "")
        if not ok_license(lic) or ii.get("width", 0) < 500:
            return None
        return {"thumb": ii.get("thumburl") or ii.get("url"), "page": ii.get("descriptionurl"),
                "author": strip(md.get("Artist", {}).get("value", "")) or "不明",
                "license": strip(lic), "license_url": md.get("LicenseUrl", {}).get("value", ""),
                "discharge": any(k in file.lower() for k in PREFER)}
    return None

def main():
    rows = [l.split("\t") for l in open(os.path.join(ROOT, "tools/photos/targets.tsv"), encoding="utf-8").read().splitlines()[1:] if l.strip()]
    out = ["slug\tthumb_url\tfile_page_url\tauthor\tlicense\tlicense_url\talt"]
    for slug, ja in rows:
        if ja.startswith("-"): continue  # 記事写真を使わない（ギャラリーのみ）
        title = resolve_title(ja)
        if not title:
            print("no article:", slug, ja); continue
        chosen = None
        for f in candidates(title)[:15]:
            i = info(f)
            if i:
                chosen = i; break
            time.sleep(0.2)
        if not chosen:
            print("no free photo:", slug, title); continue
        name = re.sub(r"\s*\(.*?\)$", "", title)
        alt = name
        out.append("\t".join([slug, chosen["thumb"], chosen["page"], chosen["author"].replace("\t", " "), chosen["license"], chosen["license_url"], alt]))
        print("ok:", slug, chosen["license"], "discharge" if chosen["discharge"] else "")
        time.sleep(0.3)
    open(os.path.join(ROOT, "tools/photos/commons.tsv"), "w", encoding="utf-8").write("\n".join(out) + "\n")

if __name__ == "__main__":
    main()

