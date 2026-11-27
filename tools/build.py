#!/usr/bin/env python3
"""サンダーバーズ.com のページを tools/content/*.html から生成する。
ファイル名 <dir>__<slug>.html → /<dir>/<slug>/、<dir>__index.html → /<dir>/、<name>.html → /<name>/、index.html → /
1行目 title、2行目 description、3行目以降 本文（h1・p.updated・h2 …・section.sources）。"""
import glob, html, os, re, datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOMAIN = "https://xn--vckkr8d3i3bb.com"
CSS_VER = "20261127h"
AD = '<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-1061443138303693" crossorigin="anonymous"></script>'
NAV = [("サンダーバーズとは", "/about/thunderbirds/")]
SECTION_NAME = {"about": ("基礎知識", "/about/")}

def esc(s): return html.escape(s, quote=True)
def strip(s): return re.sub(r"<[^>]+>", "", s).strip()

def url_of(fname):
    b = os.path.basename(fname)[:-5]
    if b == "index": return "/"
    if "__" in b:
        d, s = b.split("__", 1)
        return f"/{d}/" if s == "index" else f"/{d}/{s}/"
    return f"/{b}/"

def wrap_tables(s):
    return re.sub(r"(?<!<div class=\"table-wrap\">)(<table\b.*?</table>)", r'<div class="table-wrap">\1</div>', s, flags=re.S)

def blockify(body):
    tail = ""
    k = body.find('<section class="sources">')
    if k >= 0:
        tail = body[k:].replace('<section class="sources">', '<section class="sources block">', 1)
        body = body[:k]
    out = []
    for p in re.split(r"(?=<h2[ >])", body):
        if not p.strip(): continue
        if p.lstrip().startswith("<h2"): out.append(f'<section class="block">{p.rstrip()}</section>\n')
        elif strip(p): out.append(f'<div class="block lead-block">{p.strip()}</div>\n')
    return "".join(out) + tail

def load_photos():
    photos = {}
    f = os.path.join(ROOT, "tools", "photos", "commons.tsv")
    if not os.path.exists(f): return photos
    for line in open(f, encoding="utf-8").read().splitlines()[1:]:
        c = line.split("\t")
        if len(c) < 7 or not re.match(r"https://(upload|thumb)\.wikimedia\.org/", c[1]): continue
        c[1] = c[1].split("?")[0]
        a = re.sub(r"^No machine-readable author provided\.\s*(.+?) assumed.*$", r"\1", c[3])
        a = re.sub(r"\s*\(talk\).*$", "", a).strip()
        if re.search(r"unknown author", a, re.I): a = ""
        if not a or a == "不明":
            if "public domain" not in c[4].lower() and "cc0" not in c[4].lower(): continue
            a = "作者不明"
        c[3] = a
        photos[c[0].strip()] = c
    return photos

PHOTOS = None
# 自分の写真がないページは、関係の深いページの写真を「参考」と明記して使う
FALLBACK = {}
def dedupe_photos():
    # 同じ写真が複数のページで使われないように、重なったページにはギャラリーの別の写真を割り当てる
    global PHOTOS
    gal = {}
    gp = os.path.join(ROOT, "tools", "photos", "gallery.tsv")
    if os.path.exists(gp):
        for l in open(gp, encoding="utf-8").read().splitlines()[1:]:
            r = l.split("\t")
            if len(r) >= 7 and r[5]: gal.setdefault(r[0], []).append(r)
    used = set()
    order = sorted(PHOTOS, key=lambda u: (u.count("/") < 3, u))  # 個別ページを先に
    for u in order:
        r = list(PHOTOS[u])
        if r[1] in used:
            sec = "/" + u.strip("/").split("/")[0] + "/"
            pool = gal.get(u, []) + [g for k, v in sorted(gal.items()) if k.startswith(sec) and k != u for g in v] + [g for v in gal.values() for g in v]
            alt = next((g for g in pool if g[2] not in used), None)
            if alt:
                r = [u, alt[2], alt[3], alt[4], alt[5], alt[6], r[6]]
        used.add(r[1])
        PHOTOS[u] = r

def photo_for(url):
    global PHOTOS
    if PHOTOS is None: PHOTOS = load_photos(); dedupe_photos()
    if url in PHOTOS: return PHOTOS[url]
    if url in FALLBACK and FALLBACK[url][0] in PHOTOS:
        r = list(PHOTOS[FALLBACK[url][0]])
        if FALLBACK[url][1]: r[6] = FALLBACK[url][1]
        return r
    return None

def photo_html(url):
    global PHOTOS
    if PHOTOS is None: PHOTOS = load_photos(); dedupe_photos()
    if url not in PHOTOS: return ""
    _, src, page, author, lic, lic_url, alt = PHOTOS[url][:7]
    lic_html = f'<a href="{esc(lic_url)}" rel="noopener license" target="_blank">{esc(lic)}</a>' if lic_url.startswith("http") else esc(lic)
    return (f'<figure class="photo"><img src="{esc(src)}" alt="{esc(alt)}" loading="lazy" decoding="async">'
            f'<figcaption>{esc(alt)}　写真：{esc(author)} / {lic_html}（<a href="{esc(page)}" rel="noopener" target="_blank">Wikimedia Commons</a>）</figcaption></figure>\n')

def read_body(name):
    f = os.path.join(ROOT, "tools", "content", name)
    return open(f, encoding="utf-8").read().split("\n", 2)[2] if os.path.exists(f) else ""

def table_rows(body, n=0):
    t = re.findall(r"<table.*?</table>", body, re.S)
    rows = []
    for tb in t[n:n + 1] if n >= 0 else t:
        for tr in re.findall(r"<tr>(.*?)</tr>", tb, re.S):
            tds = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
            if tds: rows.append(tds)
    return rows

def href_of(cell):
    m = re.search(r'href="(/[^"]+)"', cell)
    return m.group(1) if m else None

def fig_kaisen(url):
    body = read_body("kaisen__index.html")
    items = []
    for tb in range(2):
        for r in table_rows(body, tb):
            y = re.search(r"(1[89]\d\d)", strip(r[0]))
            if y: items.append((y.group(1), strip(r[1]), href_of(r[1])))
    if not items: return ""
    lis = "".join(f'<li class="{"me" if h == url else ""}"><span class="y">{y}</span>'
                  + (f'<a href="{h}">{esc(n)}</a>' if h and h != url else f'<span>{esc(n)}</span>') + "</li>" for y, n, h in items)
    return f'<figure class="figure"><ol class="tl">{lis}</ol><figcaption>近代日本の主な海戦の年表（色のついた行がこのページの海戦）</figcaption></figure>\n'

def fig_senkan(url, src="senkan__index.html", col=5, label="戦艦12隻", link="戦艦一覧"):
    if not os.path.exists(os.path.join(ROOT, "tools", "content", src)): return ""
    rows = table_rows(read_body(src), 0)
    by = {}
    for r in rows:
        if len(r) <= col: continue
        y = re.search(r"(19\d\d)", strip(r[col]))
        nc = next((c for c in r if "href" in c), r[1])
        if y: by.setdefault(y.group(1), []).append((strip(nc), href_of(nc)))
    if not by: return ""
    cols = ""
    for y in sorted(by):
        ships = "".join((f'<span class="ship me">{esc(n)}</span>' if h == url else
                         f'<a class="ship" href="{h}">{esc(n)}</a>' if h and os.path.exists(os.path.join(ROOT, h.strip("/"), "index.html")) else
                         f'<span class="ship">{esc(n)}</span>') for n, h in by[y])
        cols += f'<div class="yr"><b>{y}年</b>{ships}</div>'
    return f'<figure class="figure"><div class="fate">{cols}</div><figcaption>旧日本海軍の{label}の最期の年（色のついたものがこのページの艦）。資料：当サイトの{link}</figcaption></figure>\n'

def fig_jinbutsu(url):
    rows = table_rows(read_body("jinbutsu__index.html"), 0)
    lo, hi = 1840, 1950
    bars = ""
    for r in rows:
        ys = re.findall(r"(1[89]\d\d)年", strip(r[1]))
        if len(ys) < 2: continue
        a, b = int(ys[0]), int(ys[-1]); h = href_of(r[0])
        left = (a - lo) / (hi - lo) * 100; w = (b - a) / (hi - lo) * 100
        bars += (f'<div class="life{" me" if h == url else ""}"><span class="name">{esc(strip(r[0]))}</span>'
                 f'<span class="track"><span class="span" style="left:{left:.1f}%;width:{w:.1f}%">{a}–{b}</span></span></div>')
    marks = "".join(f'<span class="m" style="left:{(y - lo) / (hi - lo) * 100:.1f}%">{y}</span>' for y in (1850, 1900, 1950))
    ev = "".join(f'<span class="ev" style="left:{(y - lo) / (hi - lo) * 100:.1f}%;top:{tp}px">▲{t}</span>' for y, t, tp in ((1894, "日清戦争", 20), (1904, "日露戦争", 34), (1941, "太平洋戦争", 20)))
    return f'<figure class="figure"><div class="lives">{bars}<div class="axis">{marks}{ev}</div></div><figcaption>海軍の人物の生きた時代（色のついた行がこのページの人物）</figcaption></figure>\n'

def hero_chips(body):
    t = re.search(r"<table.*?</table>", body, re.S)
    if not t: return ""
    chips = []
    for th, td in re.findall(r"<th>([^<]*)</th>\s*<td[^>]*>(.*?)</td>", t.group(0), re.S):
        if th in ("開催日", "お渡り式", "日時", "場所", "竣工", "造船所", "建造所", "生年月日", "没年月日", "出身", "結果", "所在地", "母港", "艦番号", "就役"):
            v = strip(td)
            v = re.sub(r"（.*?）", "", v)
            if 1 < len(v) <= 26 and "未確認" not in v and v != "—":
                chips.append(f'<span class="chip">{esc(th)} <b>{esc(v)}</b></span>')
        if len(chips) >= 3: break
    return f'<div class="chips">{"".join(chips)}</div>' if chips else ""

def related_cards(url):
    seg = url.strip("/").split("/")
    if not seg[0] or seg[0] not in SECTION_NAME: return ""
    d = seg[0]
    cards = []
    for f in sorted(glob.glob(os.path.join(ROOT, "tools", "content", f"{d}__*.html"))):
        u = url_of(f)
        if u == url: continue
        if '<section class="sources">' not in open(f, encoding="utf-8").read(): continue
        b = open(f, encoding="utf-8").read().split("\n", 2)
        m = re.search(r"<h1>(.*?)</h1>", b[2], re.S)
        dm = re.search(r'content="([^"]*)"', b[1]); dtext = html.unescape(dm.group(1)) if dm else strip(b[1])
        cards.append(f'<a class="card" href="{u}"><strong>{esc(strip(m.group(1)) if m else u)}</strong><small>{esc(dtext[:60])}…</small></a>')
    if not cards: return ""
    return f'<h2>{SECTION_NAME[d][0]}のほかのページ</h2><div class="cards">{"".join(cards[:9])}</div>\n'

def figure_for(url):
    return ""

GALLERY = None
GAL_ASSIGNED = None
# 行事ごとの記事には、その記事に登録された写真を表示する。
GALLERY_OWN_ONLY = {
    "/about/arcticthunder/",
    "/about/academygraduation/",
    "/about/hometownhero/",
    "/about/lukedays2024/",
    "/about/thunderovertherock2023/",
    "/about/soundofspeed/",
    "/about/wingsoverwyoming/",
}


def assign_galleries():
    # サイト全体で同じ写真が2回出ないよう、個別ページ→一覧ページの順に写真を割り当てる
    global GAL_ASSIGNED
    GAL_ASSIGNED = {}
    used = set()
    if PHOTOS:
        used |= {r[1] for r in PHOTOS.values()}
    pages = [url_of(f) for f in glob.glob(os.path.join(ROOT, "tools", "content", "*.html"))]
    pages.sort(key=lambda u: (u.count("/") < 3, u))
    for u in pages:
        own = [r for r in GALLERY.get(u, []) if r[2] not in used]
        if len(own) < 10 and u not in GALLERY_OWN_ONLY:
            sec = "/" + u.strip("/").split("/")[0] + "/"
            for k, v in sorted(GALLERY.items()):
                if k != u and k.startswith(sec):
                    own += [r for r in v if r[2] not in used and r not in own]
        own = own[:12]
        used |= {r[2] for r in own}
        GAL_ASSIGNED[u] = own

def gallery_for(url, hero_src):
    global GALLERY
    if GALLERY is None:
        GALLERY = {}
        p = os.path.join(ROOT, "tools", "photos", "gallery.tsv")
        if os.path.exists(p):
            for l in open(p, encoding="utf-8").read().splitlines()[1:]:
                r = l.split("\t")
                if len(r) >= 7 and r[5]: GALLERY.setdefault(r[0], []).append(r)
    if hero_src is None and url == "": return ""
    if GAL_ASSIGNED is None:
        photo_for("/"); assign_galleries()
    items = GAL_ASSIGNED.get(url, [])
    if len(items) < 2: return ""
    figs = "".join(
        f'<figure><a href="{esc(r[3])}" target="_blank" rel="noopener"><img src="{esc(r[2])}" alt="{esc((r[1] + "見た" if r[1] else "") + "写真")}" loading="lazy" decoding="async"></a>'
        f'<figcaption>{"<b>" + esc(r[1]) + "</b> " if r[1] else ""}{esc(r[4][:60])} / '
        f'{"<a href=" + chr(34) + esc(r[6]) + chr(34) + " target=_blank rel=" + chr(34) + "noopener license" + chr(34) + ">" + esc(r[5]) + "</a>" if r[6] else esc(r[5])}</figcaption></figure>'
        for r in items[:12])
    return (f'<section class="block"><h2>写真ギャラリー</h2><div class="gallery">{figs}</div>'
            f'<p class="note">写真はWikimedia Commonsの自由ライセンス画像です。クリックすると撮影者・ライセンスの詳細ページが開きます。角度の表記は画像の説明文から判定したもので、表記のない写真もあります。</p></section>\n')

def insert_after_first_section(main, fig):
    if not fig: return main
    i = main.find("</section>")
    title = "年表で見る" if "tl" in fig else ("図で見る" if "fate" in fig else "生きた時代を図で見る")
    fig = f'<section class="block"><h2>{title}</h2>{fig}</section>\n'
    return main[:i + 10] + "\n" + fig + main[i + 10:] if i >= 0 else main + fig

SHIPS = {}

def link_ships(url, body):
    if url != "/kan/": return body
    def rep(m):
        n = m.group(1); sl = SHIPS.get(n)
        if sl and complete(f"kan__{sl}.html"):
            return f'<td><a href="/kan/{sl}/">{n}</a></td>'
        return m.group(0)
    return re.sub(r"<td>([ぁ-ん]+)</td>", rep, body)

def top_hero(body):
    return (f'<section class="tophero art art-br"><img class="art-img" src="/assets/hero.webp?v=1127" alt="ちんあなご編集部のキャラクター" width="1344" height="752" fetchpriority="high">'
            f'<div class="inner"><p class="kicker">米空軍サンダーバーズのガイド</p>'
            f'<h1>サンダーバーズを<br>もっと知る</h1><p class="lead">米空軍のアクロバット飛行チーム「サンダーバーズ」の歴史と展示スケジュールを、米空軍の公式発表からまとめています。</p>'
            f'<div class="cta"><a class="btn" href="/about/thunderbirds/">サンダーバーズとは</a></div></div></section>\n')

SHIP_JA = {"CVN 68": "ニミッツ", "CVN 69": "ドワイト・D・アイゼンハワー", "CVN 70": "カール・ヴィンソン", "CVN 71": "セオドア・ルーズベルト",
           "CVN 72": "エイブラハム・リンカーン", "CVN 73": "ジョージ・ワシントン", "CVN 74": "ジョン・C・ステニス", "CVN 75": "ハリー・S・トルーマン",
           "CVN 76": "ロナルド・レーガン", "CVN 77": "ジョージ・H・W・ブッシュ", "CVN 78": "ジェラルド・R・フォード", "CVN 79": "ジョン・F・ケネディ"}
def navy_block(n, heading):
    import json
    f = os.path.join(ROOT, "data", "navy_news.json")
    if not os.path.exists(f): return ""
    d = json.load(open(f, encoding="utf-8"))
    items = [i for i in d.get("items", []) if i.get("ships")][:n]
    if not items: return ""
    rows = []
    for i in items:
        ships = "・".join(f"{SHIP_JA.get(h, h)}（{h}）" for h in i["ships"])
        rows.append(f'<tr><td>{esc(i["date"])}</td><td>{esc(ships)}</td><td><a href="{esc(i["link"])}" target="_blank" rel="noopener">{esc(html.unescape(i["title"]))}</a></td></tr>')
    upd = esc(d.get("updated", "").replace("T", " ").replace("Z", " UTC"))
    return (f'<section class="block"><h2>{esc(heading)}</h2><p class="lead">米海軍の公式サイト（navy.mil）のニュースのうち、空母に関係するものを6時間ごとに自動で取り込んでいます。'
            f'見出しは原文（英語）のままで、押すと米海軍の記事が開きます。日付は米国東部時間の配信日です。最終取得：{upd}</p>'
            f'<div class="table-wrap"><table><tr><th>日付</th><th>空母</th><th>米海軍の発表（原文）</th></tr>{"".join(rows)}</table></div></section>\n')

def next_events():
    f = os.path.join(ROOT, "tools", "content", "calendar.html")
    if not os.path.exists(f): return ""
    src = open(f, encoding="utf-8").read()
    evs = []
    for t in re.findall(r"<table.*?</table>", src, re.S):
        hd = re.search(r"<th>(開催日[^<]*)</th>", t)
        if not hd: continue
        yr = re.search(r"(20\d\d)", hd.group(1)); yr = int(yr.group(1)) if yr else 2026
        for tr in re.findall(r"<tr>(.*?)</tr>", t, re.S):
            td = re.findall(r"<td>(.*?)</td>", tr, re.S)
            if len(td) < 6: continue
            m = re.search(r"(?:(20\d\d)年)?(\d{1,2})月(\d{1,2})日", strip(td[0]))
            if not m: continue
            y = int(m.group(1) or yr)
            link = re.search(r'href="([^"]+)"', td[5])
            evs.append((f"{y:04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}", strip(td[0]), strip(td[1]), strip(td[2]), strip(td[3]), strip(td[4]), link.group(1) if link else "/calendar/"))
    if not evs: return ""
    evs.sort()
    today = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=9)).strftime("%Y-%m-%d")
    up = [e for e in evs if e[0] >= today]
    show = up[:3] if up else evs[-3:]
    def card(e, i):
        d, dt, n, pref, unit, veh, u = e
        lab = ["次のお祭り", "その次", "その次の次"][i] if up else "最近のお祭り"
        vv = veh or "見どころは公式発表を確認"
        return (f'<a class="ev-card{" featured" if i == 0 and up else ""}" data-date="{d}" href="{esc(u)}"{"" if u.startswith("/") else " target=_blank rel=noopener"}>'
                f'<span class="ev-next">{lab}</span><span class="ev-date">{esc(d[:4])}年{esc(dt)}</span>'
                f'<strong>{esc(n)}</strong><small>{esc(pref)}・{esc(unit[:40])}</small><em>{esc(vv[:60])}</em></a>')
    cards = "".join(card(e, i) for i, e in enumerate(show))
    ld = [{"@context": "https://schema.org", "@type": "Event", "name": n, "startDate": d,
           "eventAttendanceMode": "https://schema.org/OfflineEventAttendanceMode", "eventStatus": "https://schema.org/EventScheduled",
           "location": {"@type": "Place", "name": n, "address": {"@type": "PostalAddress", "addressRegion": pref, "addressCountry": "JP"}},
           "url": (DOMAIN + u) if u.startswith("/") else u}
          for d, dt, n, pref, unit, veh, u in (up[:3])]
    import json
    ldtag = f'<script type="application/ld+json">{json.dumps(ld, ensure_ascii=False)}</script>' if ld else ""
    none = "" if up else '<p class="note">いま発表されている今後のお祭りはありません。新しい日程は、発表されしだい追加します。下は最近開かれたお祭りです。</p>'
    return (f'<section class="block next-events"><h2>次のお祭り</h2>'
            f'<p class="lead">これから開かれる全国のお祭りを、近い順に3つ紹介します。日付は主催者・自治体・観光協会の公式発表で確認したものだけです。'
            f'お出かけの前に、必ず公式ページで最新の情報を確かめてください。</p>{none}'
            f'<div class="ev-grid">{cards}</div><p class="cta"><a class="btn" href="/calendar/">お祭りカレンダーをすべて見る</a></p>{ldtag}</section>\n')

def photo_wall():
    global PHOTOS
    if PHOTOS is None: PHOTOS = load_photos(); dedupe_photos()
    items = []
    for u in sorted(PHOTOS):
        if re.match(r"^/about/[a-z0-9]+/$", u) and os.path.exists(os.path.join(ROOT, u.strip("/"), "index.html")):
            ph = PHOTOS[u]
            items.append(f'<figure><a href="{u}"><img src="{esc(ph[1])}" alt="{esc(ph[6])}" loading="lazy"><span class="cap">{esc(ph[6])}</span></a>'
                         f'<figcaption>{esc(ph[3][:40])} / <a href="{esc(ph[2])}" target="_blank" rel="noopener">{esc(ph[4])}</a></figcaption></figure>')
    if not items: return ""
    return (f'<section class="block"><h2>写真</h2><div class="gallery wall">{"".join(items)}</div>'
            f'<p class="note">写真はWikimedia Commonsの自由ライセンス画像です。写真を押すとそのページへ、ライセンス表記を押すと元の写真のページへ移動します。</p></section>\n')

FESTIVAL = {}  # カレンダーの祭り名 → /matsuri/<slug>/（calendar.html の表で直接リンクする）
def link_garrisons(body):
    return body

def archive_rows(body):
    def tag(t):
        hd = re.search(r"<th>(開催日[^<]*)</th>", t)
        if not hd: return t
        yr = re.search(r"(20\d\d)", hd.group(1)); yr = int(yr.group(1)) if yr else 2026
        def tr(m):
            d = re.search(r"<td>(?:(20\d\d)年)?(\d{1,2})月(\d{1,2})日", m.group(0))
            if not d: return m.group(0)
            return f'<tr data-date="{int(d.group(1) or yr):04d}-{int(d.group(2)):02d}-{int(d.group(3)):02d}">' + m.group(0)[4:]
        return re.sub(r"<tr><td>.*?</tr>", tr, t, flags=re.S)
    body = re.sub(r"<table.*?</table>", lambda m: tag(m.group(0)), body, flags=re.S)
    js = ("<section class=\"block\" id=\"archive\" style=\"display:none\"><h2>アーカイブ（終了したお祭り）</h2>"
          "<p>開催日が過ぎたお祭りは、ここにまとめて残しています。来年の日程の目安にしてください（毎年同じ日とは限りません）。</p>"
          "<div class=\"table-wrap\"><table><thead><tr><th>開催日</th><th>お祭り</th><th>都道府県</th><th>場所</th><th>見どころ</th><th>公式ページ</th></tr></thead><tbody id=\"archive-body\"></tbody></table></div></section>"
          "<script>(function(){var t=new Date();t.setHours(0,0,0,0);var rows=[].slice.call(document.querySelectorAll('tr[data-date]')),b=document.getElementById('archive-body'),n=0;"
          "rows.sort(function(a,c){return a.dataset.date<c.dataset.date?1:-1});"
          "rows.forEach(function(r){if(new Date(r.dataset.date+'T00:00:00')<t){r.cells[0].innerHTML+=' <span class=ended>終了</span>';b.appendChild(r);n++}});"
          "if(n)document.getElementById('archive').style.display='';"
          "document.querySelectorAll('main table').forEach(function(tb){if(tb.querySelector('th')&&/開催日/.test(tb.querySelector('th').textContent)&&tb.id!=='x'&&!tb.querySelector('tbody#archive-body')&&!tb.querySelector('tr[data-date]')&&tb.rows.length<=1){var s=tb.closest('section');if(s)s.style.display='none'}})})();</script>")
    k = body.find('<section class="sources">')
    return body[:k] + js + body[k:] if k >= 0 else body + js

SEEN_THUMBS = {}
USED_SRC = set()
def ul_to_cards(main):
    SEEN_THUMBS.clear(); USED_SRC.clear()
    def rep(m):
        items = re.findall(r'<li><a href="([^"]+)">(.*?)</a>(?:：|・)?(.*?)</li>', m.group(0), re.S)
        if not items or len(items) < 3: return m.group(0)
        def th(u):
            if not u.startswith("/"): return ""
            ph = photo_for(u)
            k = SEEN_THUMBS.get(u, 0); SEEN_THUMBS[u] = k + 1
            src, alt = (ph[1], ph[6]) if ph else (None, "")
            if k or not src:
                gallery_for(u, None)
                sec = "/" + u.strip("/").split("/")[0] + "/"
                pool = [r for r in GALLERY.get(u, []) if not ph or r[2] != ph[1]]
                pool += [r for kk, v in sorted(GALLERY.items()) if kk.startswith(u) and kk != u for r in v]
                pool += [r for kk, v in sorted(GALLERY.items()) if kk.startswith(sec) and kk != u for r in v]
                pool = [r for r in pool if r[2] not in USED_SRC]
                if not pool: return ""
                src = pool[0][2]
            USED_SRC.add(src)
            return f'<img class="thumb" src="{esc(src)}" alt="{esc(alt)}" loading="lazy">'
        return '<div class="cards">' + "".join(f'<a class="card{" has-thumb" if th(u) else ""}" href="{u}">{th(u)}<strong>{strip(t)}</strong><small>{strip(d)}</small></a>' for u, t, d in items) + "</div>"
    return re.sub(r"<ul>(?:\s*<li><a href=.*?</li>)+\s*</ul>", rep, main, flags=re.S)

def complete(name):
    f = os.path.join(ROOT, "tools", "content", name)
    return os.path.exists(f) and '<section class="sources">' in open(f, encoding="utf-8").read()

def unlink_missing(body):
    def rep(m):
        d, sl = m.group(1), m.group(2)
        return m.group(0) if complete(f"{d}__{sl}.html") else m.group(3)
    return re.sub(r'<a href="/(about)/([a-z0-9]+)/"[^>]*>(.*?)</a>', rep, body)

def render(url, title, desc, body):
    body = unlink_missing(link_ships(url, body))
    m = re.search(r"<h1>(.*?)</h1>\s*(<p class=\"updated\">.*?</p>)?", body, re.S)
    hero = ""
    if m:
        body = body[:m.start()] + body[m.end():]
        global PHOTOS
        if PHOTOS is None: PHOTOS = load_photos(); dedupe_photos()
        ph = photo_for(url)
        if ph:
            credit = (f'<p class="credit">写真：{esc(ph[6])} {esc(ph[3])} / <a href="{esc(ph[5])}" rel="noopener license" target="_blank">{esc(ph[4])}</a>'
                      f'（<a href="{esc(ph[2])}" rel="noopener" target="_blank">Wikimedia Commons</a>）</p>')
            hero = (f'<div class="page-hero photo-hero" style="background-image:linear-gradient(180deg,rgba(6,22,44,.35),rgba(6,22,44,.88)),url({esc(ph[1])})">'
                    f'<h1>{m.group(1)}</h1>{m.group(2) or ""}{hero_chips(body)}{credit}</div>\n')
        else:
            hero = f'<div class="page-hero"><h1>{m.group(1)}</h1>{m.group(2) or ""}{hero_chips(body)}</div>\n'
    k = body.find('<section class="sources">')
    rel = related_cards(url)
    body = (body[:k] + rel + body[k:]) if k >= 0 else body + rel
    gal = gallery_for(url, PHOTOS.get(url, [None, None])[1] if PHOTOS else None)
    crumbs = [("サンダーバーズ.com", "/")]
    seg = url.strip("/").split("/")
    if url != "/":
        if len(seg) == 2 and seg[0] in SECTION_NAME: crumbs.append(SECTION_NAME[seg[0]])
        crumbs.append((strip(m.group(1)) if m else title, None))
    crumb = " › ".join(f'<a href="{u}">{esc(t)}</a>' if u else esc(t) for t, u in crumbs)
    if url == "/":
        hero = top_hero(body) + photo_wall()
    if url == "/calendar/":
        body = link_garrisons(archive_rows(body))
    body = ul_to_cards(body)
    main = (f'  <div class="crumb">{crumb}</div>\n' if url != "/" else "") + hero + insert_after_first_section(blockify(wrap_tables(body)), figure_for(url))
    if gal:
        j = main.find('<section class="sources block">')
        main = main[:j] + gal + main[j:] if j >= 0 else main + gal
    nav = "".join(f'<a href="{u}">{t}</a>' for t, u in NAV if os.path.exists(os.path.join(ROOT, u.strip("/"), "index.html")) )
    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
<link rel="canonical" href="{DOMAIN}{url}">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(desc)}">
<meta property="og:type" content="{'website' if url == '/' else 'article'}">
<meta property="og:url" content="{DOMAIN}{url}">
<link rel="stylesheet" href="/assets/style.css?v={CSS_VER}">
{AD}
</head>
<body>
<header class="site"><div class="wrap">
  <a class="logo" href="/">サンダーバーズ<span>.com</span></a>
  <nav class="global">{nav}</nav>
</div></header>

<main><div class="wrap">
{main}</div></main>

<footer class="site"><div class="wrap">
  <p>サンダーバーズ.com は、米空軍サンダーバーズの情報を米空軍の公式発表から日本語でまとめた情報サイトです。米空軍・米国政府とは関係のない、ちんあなご編集部のサイトです。</p>
  <p>{" ・ ".join(f'<a href="{u}">{t}</a>' for t, u in [("トップ", "/")] + NAV)}</p>
  <p><a href="/operator/">運営者情報</a> ・ <a href="/editorial-policy/">編集方針</a> ・ <a href="/contact/">お問い合わせ</a> ・ <a href="/privacy/">プライバシーポリシー</a> ・ <a href="/disclaimer/">免責事項</a></p>
  <p>© 2026 サンダーバーズ.com</p>
</div></footer>
</body>
</html>
"""

def main():
    urls = []
    for f in sorted(glob.glob(os.path.join(ROOT, "tools", "content", "*.html"))):
        lines = open(f, encoding="utf-8").read().split("\n", 2)
        if len(lines) < 3 or '<section class="sources">' not in lines[2] or not lines[2].rstrip().endswith("</section>"): continue
        url = url_of(f)
        out = os.path.join(ROOT, url.strip("/"), "index.html") if url != "/" else os.path.join(ROOT, "index.html")
        os.makedirs(os.path.dirname(out), exist_ok=True)
        title = strip(lines[0])
        dm = re.search(r'content="([^"]*)"', lines[1])
        desc = html.unescape(dm.group(1)) if dm else strip(lines[1])
        open(out, "w", encoding="utf-8").write(render(url, html.unescape(title), desc, lines[2]))
        urls.append(url)
    today = datetime.date.today().isoformat()
    sm = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    sm += [f"  <url><loc>{DOMAIN}{u}</loc><lastmod>{today}</lastmod></url>" for u in urls]
    sm.append("</urlset>")
    open(os.path.join(ROOT, "sitemap.xml"), "w").write("\n".join(sm) + "\n")
    open(os.path.join(ROOT, "robots.txt"), "w").write(f"User-agent: *\nAllow: /\nSitemap: {DOMAIN}/sitemap.xml\n")
    print("pages", len(urls))

if __name__ == "__main__":
    main()
