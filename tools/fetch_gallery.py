#!/usr/bin/env python3
"""GitHub Actions で実行：tools/photos/targets.tsv の艦（/kan/・/senkan/・/kubo/）ごとに、
Wikidata の Commons カテゴリから自由ライセンス（PD・CC0・CC BY・CC BY-SA）の写真を最大6枚選び、
tools/photos/gallery.tsv に書き出す。ファイル名・説明文から「前から」「横から」「後ろから」を判定し、
3方向を優先して選ぶ。判定できない写真は角度ラベルなし。"""
import json, os, re, time, urllib.parse, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UA = {"User-Agent": "thunderbirds-com-photo-bot/1.0 (https://xn--vckkr8d3i3bb.com/; info@chinanago.jp)"}
AVOID = ["map", "地図", "logo", "icon", "svg", "flag", "diagram", "chart", "emblem", "insignia", "ensign", "seal",
         "patch", "badge", "crest", "plan", "drawing", "model", "模型", "stamp", "postcard", "interior", "crew", 
         "memorial", "bridge of", "galley", "uniform"]
ANGLES = [("前から", ["bow", "front", "head on", "head-on", "艦首", "前方", "正面"]),
          ("後ろから", ["stern", "rear", "aft view", "from aft", "艦尾", "後方", "astern", "transom"]),
          ("横から", ["broadside", "side view", "port side", "starboard side", "portside", "starboard", "port bow", "側面", "profile", "underway", "航行"])]

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

def commons_category(ja_title):
    d = api("ja.wikipedia.org", {"action": "query", "titles": ja_title, "redirects": 1, "prop": "pageprops", "ppprop": "wikibase_item"})
    pages = d.get("query", {}).get("pages", {})
    if not pages or "-1" in pages:
        d = api("ja.wikipedia.org", {"action": "query", "list": "search", "srsearch": ja_title, "srlimit": 1})
        hits = d.get("query", {}).get("search", [])
        if not hits: return None
        d = api("ja.wikipedia.org", {"action": "query", "titles": hits[0]["title"], "prop": "pageprops", "ppprop": "wikibase_item"})
        pages = d.get("query", {}).get("pages", {})
    qid = next(iter(pages.values()), {}).get("pageprops", {}).get("wikibase_item")
    if not qid: return None
    w = api("www.wikidata.org", {"action": "wbgetclaims", "entity": qid, "property": "P373"})
    c = w.get("claims", {}).get("P373", [])
    return "Category:" + c[0]["mainsnak"]["datavalue"]["value"] if c else None

def files_in(cat, depth=1):
    out = []
    d = api("commons.wikimedia.org", {"action": "query", "list": "categorymembers", "cmtitle": cat, "cmtype": "file|subcat", "cmlimit": 500})
    subs = []
    for m in d.get("query", {}).get("categorymembers", []):
        if m["ns"] == 6: out.append(m["title"])
        elif m["ns"] == 14: subs.append(m["title"])
    if depth and len(out) < 30:
        for sc in subs[:6]:
            if any(a in sc.lower() for a in ["interior", "crew", "model", "insignia", "ceremon", "visit", "wreck"]): continue
            out += files_in(sc, 0)
    return out

def infos(files):
    res = []
    for i in range(0, len(files), 40):
        d = api("commons.wikimedia.org", {"action": "query", "titles": "|".join(files[i:i + 40]), "prop": "imageinfo",
                                          "iiprop": "url|extmetadata|size", "iiurlwidth": 960})
        for p in d.get("query", {}).get("pages", {}).values():
            ii = (p.get("imageinfo") or [None])[0]
            if not ii: continue
            md = ii.get("extmetadata", {})
            lic = md.get("LicenseShortName", {}).get("value", "")
            if not ok_license(lic) or ii.get("width", 0) < 800 or ii.get("width", 0) < ii.get("height", 1): continue
            author = strip(md.get("Artist", {}).get("value", ""))
            if not author or "unknown" in author.lower(): author = strip(md.get("Credit", {}).get("value", ""))[:80] or "不明"
            desc = strip(md.get("ImageDescription", {}).get("value", ""))[:400]
            res.append({"title": p["title"], "thumb": ii.get("thumburl") or ii.get("url"), "page": ii.get("descriptionurl"),
                        "author": author.replace("\t", " "), "license": strip(lic), "license_url": md.get("LicenseUrl", {}).get("value", ""),
                        "text": (p["title"] + " " + desc).lower()})
        time.sleep(0.3)
    return res

def angle(text):
    for label, keys in ANGLES:
        if any(k in text for k in keys): return label
    return ""

def pick(cands, n=40):
    chosen, used = [], set()
    for label, _ in ANGLES:
        for c in cands:
            if c["title"] not in used and angle(c["text"]) == label:
                chosen.append((label, c)); used.add(c["title"]); break
    for c in cands:
        if len(chosen) >= n: break
        if c["title"] not in used:
            chosen.append((angle(c["text"]), c)); used.add(c["title"])
    return chosen

# Wikidata が艦級のカテゴリを返す・カテゴリがない艦は、艦ごとのカテゴリを指定する（存在しなければ写真なし）
OVERRIDE = {"/about/thunderbirds/": "Category:United States Air Force Thunderbirds"}

# カテゴリがない艦は、ファイル名検索で補う
SEARCH = {}

def search_files(q):
    d = api("commons.wikimedia.org", {"action": "query", "list": "search", "srsearch": q, "srnamespace": 6, "srlimit": 50})
    return [h["title"] for h in d.get("query", {}).get("search", [])]

def main():
    rows = [l.split("\t") for l in open(os.path.join(ROOT, "tools/photos/targets.tsv"), encoding="utf-8").read().splitlines()[1:] if l.strip()]
    out = ["slug\tangle\tthumb_url\tfile_page_url\tauthor\tlicense\tlicense_url"]
    for slug, ja in rows:
        if not re.match(r"^/about/[a-z0-9]+/$", slug): continue
        cat = OVERRIDE.get(slug) or commons_category(ja)
        if not cat and slug in SEARCH: cat = ""
        if cat and slug not in OVERRIDE and " class" in cat.lower():
            print("class category skipped:", slug, cat)
            if slug not in SEARCH: continue
            cat = ""
        if cat is None:
            print("no category:", slug, ja); continue
        allf = files_in(cat) if cat else []
        if len(allf) < 3 and slug in SEARCH: allf += search_files(SEARCH[slug])
        files = [f for f in dict.fromkeys(allf) if re.search(r"\.(jpe?g|png)$", f, re.I) and not any(a in f.lower() for a in AVOID)]
        got = pick([c for c in infos(files[:300]) if not any(a in c["text"] for a in AVOID)])
        for label, c in got:
            out.append("\t".join([slug, label, c["thumb"], c["page"], c["author"], c["license"], c["license_url"]]))
        print(f"{slug} {cat} files={len(files)} picked={len(got)} angles={','.join(l for l, _ in got if l)}")
    tmp = os.path.join(ROOT, "tools/photos/gallery.tsv.tmp")
    open(tmp, "w", encoding="utf-8").write("\n".join(out) + "\n")
    os.replace(tmp, os.path.join(ROOT, "tools/photos/gallery.tsv"))

if __name__ == "__main__":
    main()
