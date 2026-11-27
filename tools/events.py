"""展示飛行の予定（tools/events.json）から、トップの「次の展示飛行」の記事と予定の一覧を作る。
日付が過ぎた行事は、ページを開いた時に自動で一覧からアーカイブへ移り、次の行事に切り替わる（作り直しは要らない）。"""
import datetime, html, json, os, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEEK = "月火水木金土日"

def load():
    with open(os.path.join(ROOT, "tools", "events.json"), encoding="utf-8") as f:
        return json.load(f)

def today():
    return (datetime.datetime.utcnow() + datetime.timedelta(hours=9)).date().isoformat()

def ja_date(start, end):
    s = datetime.date.fromisoformat(start); e = datetime.date.fromisoformat(end)
    out = f"{s.year}年{s.month}月{s.day}日（{WEEK[s.weekday()]}）"
    if e != s:
        head = "" if e.year == s.year else f"{e.year}年"
        sep = "・" if (e - s).days == 1 else "〜"
        out += sep + head + (f"{e.month}月" if (e.month != s.month or head) else "") + f"{e.day}日（{WEEK[e.weekday()]}）"
        if e.month != s.month and not head:
            out = f"{s.year}年{s.month}月{s.day}日（{WEEK[s.weekday()]}）" + sep + f"{s.year}年{e.month}月{e.day}日（{WEEK[e.weekday()]}）"
    return out

def page_of(d, e):
    p = e.get("page")
    if p and os.path.exists(os.path.join(ROOT, p.strip("/"), "index.html")): return p, "この会場の面"
    p = d.get("list_pages", {}).get(e["start"][:4])
    return (p, f"{e['start'][:4]}年の予定の一覧") if p else (None, None)

def links(d, e):
    out = []
    p, label = page_of(d, e)
    if p: out.append(f'<a class="btn" href="{p}">{label}</a>')
    out.append(f'<a href="{html.escape(d["source"])}" target="_blank" rel="noopener">{html.escape(d["source_name"])}</a>')
    if e.get("url"): out.append(f'<a href="{html.escape(e["url"])}" target="_blank" rel="noopener">行事の公式サイト</a>')
    return " ".join(out)

JS_TODAY = "var n=new Date(),p=function(v){return ('0'+v).slice(-2)},t=n.getFullYear()+'-'+p(n.getMonth()+1)+'-'+p(n.getDate());"

def card_item(d, e):
    p, _ = page_of(d, e)
    name = f'<span class="ns-name">{html.escape(e["name"])}</span>' if e.get("name") else ""
    return (f'<article class="ns-item ns-sub" data-start="{e["start"]}" data-end="{e["end"]}">'
            f'<p class="ns-date">{ja_date(e["start"], e["end"])} <span class="ns-left"></span></p>'
            f'<p class="ns-place">{html.escape(e["ja"])}</p><p class="ns-en">{name} <small>{html.escape(e["place"])}</small></p>'
            f'<p class="ns-links">{links(d, e)}</p>'
            + (f'<a class="ns-cover" href="{p}" aria-label="{html.escape(e["ja"])}の案内"></a>' if p else "") + "</article>")

def pending_card(d, year, last):
    past = d.get("list_pages", {}).get(last)
    return (f'<div class="ns-pending"><p class="ns-date">{year}年の公式発表待ち</p>'
            f'<p>{year}年の展示飛行の日程は、公式の発表を待っています。発表された分から、ここに載せます。</p>'
            f'<p class="ns-links">' + (f'<a class="btn" href="{past}">{last}年の日程の一覧</a> ' if past else "")
            + f'<a href="{html.escape(d["source"])}" target="_blank" rel="noopener">{html.escape(d["source_name"])}</a></p></div>')

def next_card():
    """直近の4件だけを面に出す。残りと「発表待ち」の文はスクリプト用のデータに持ち、日が過ぎたら入れ替える（面の本文には入らない）"""
    d = load(); t = today()
    up = sorted((e for e in d["events"] if e["end"] >= t), key=lambda e: e["start"])
    last = max((e["start"][:4] for e in d["events"]), default=t[:4])
    pending = pending_card(d, int(last) + 1, last)
    shown = "".join(card_item(d, e).replace("ns-sub", "ns-first" if i == 0 else "ns-sub", 1) for i, e in enumerate(up[:4])) if up else pending
    data = json.dumps({"items": [{"end": e["end"], "html": card_item(d, e)} for e in up], "pending": pending}, ensure_ascii=False).replace("</", "<\\/")
    js = ("<script>(function(){var b=document.getElementById('nextshow');if(!b)return;" + JS_TODAY +
          "var day=function(s){var a=s.split('-');return Date.UTC(a[0],a[1]-1,a[2])},d=JSON.parse(document.getElementById('ns-data').textContent),l=b.querySelector('.ns-list');"
          "var rows=d.items.filter(function(x){return x.end>=t}).slice(0,4);l.innerHTML=rows.length?rows.map(function(x){return x.html}).join(''):d.pending;"
          "[].slice.call(l.querySelectorAll('.ns-item')).forEach(function(x,i){x.className='ns-item '+(i===0?'ns-first':'ns-sub');var k=Math.round((day(x.dataset.start)-day(t))/864e5);"
          "x.querySelector('.ns-left').textContent=k>0?'あと'+k+'日':'開催期間中'})})();</script>")
    return (f'<section class="block nextshow" id="nextshow"><h2>次の展示飛行</h2><div class="ns-list">{shown}</div>'
            f'<p class="note">日付は開催地の日付です。予定は変わることがあります。{html.escape(d["source_name"])}で{html.escape(d["checked_ja"])}に確かめた内容です。</p>'
            f'<script type="application/json" id="ns-data">{data}</script>{js}</section>\n')

def place_cell(e):
    p = e.get("page"); parts = e["ja"].split(" ", 1)
    state, venue = (parts[0], parts[1]) if len(parts) == 2 else ("", e["ja"])
    venue = html.escape(venue)
    if p and os.path.exists(os.path.join(ROOT, p.strip("/"), "index.html")): venue = f'<a href="{p}">{venue}</a>'
    return venue, html.escape(state)

def season_table(year):
    """その年の日程の表（日付・会場・州）。トップなどの本文に {{events:年}} と書いた場所に入る"""
    d = load()
    rows = sorted((e for e in d["events"] if e["start"].startswith(year)), key=lambda e: e["start"])
    if not rows: return ""
    body = "".join("<tr><td>{}</td><td>{}</td><td>{}</td></tr>".format(ja_date(e["start"], e["end"]), *place_cell(e)) for e in rows)
    return f'<div class="table-wrap season"><table><thead><tr><th>日付</th><th>会場</th><th>州・国</th></tr></thead><tbody>{body}</tbody></table></div>'

def schedule_block(year):
    """予定の一覧の面に足す一覧。これからの分と、過ぎた分（アーカイブ）。開いた日に過ぎていた行は自動でアーカイブへ移す"""
    d = load(); t = today()
    rows = sorted((e for e in d["events"] if e["start"].startswith(year)), key=lambda e: e["start"])
    if not rows: return ""
    def tr(e):
        p = e.get("page")
        place = html.escape(e["ja"])
        if p and os.path.exists(os.path.join(ROOT, p.strip("/"), "index.html")): place = f'<a href="{p}">{place}</a>'
        name = html.escape(e.get("name") or "")
        if e.get("url"): name = f'<a href="{html.escape(e["url"])}" target="_blank" rel="noopener">{name or "公式サイト"}</a>'
        return f'<tr data-end="{e["end"]}"><td>{ja_date(e["start"], e["end"])}</td><td>{place}</td><td>{name}</td></tr>'
    head = "<thead><tr><th>日付</th><th>開催地</th><th>行事</th></tr></thead>"
    def sec(title, ident, items):
        return f'<section class="block" data-list="{ident}"><h2>{title}</h2><div class="table-wrap"><table>{head}<tbody id="{ident}">{"".join(map(tr, items))}</tbody></table></div></section>\n'
    up = [e for e in rows if e["end"] >= t]; old = [e for e in rows if e["end"] < t]
    out = (sec(f"{year}年のこれからの展示飛行", f"up{year}", up) if up else "") + (sec(f"{year}年の展示飛行の日程（アーカイブ）", f"ar{year}", old) if old else "")
    if up:
        js = ("<script>(function(){" + JS_TODAY + f"var u=document.getElementById('up{year}');if(!u)return;"
              "var past=[].slice.call(u.querySelectorAll('tr[data-end]')).filter(function(r){return r.dataset.end<t});if(!past.length)return;"
              f"var a=document.getElementById('ar{year}');if(!a){{var s=u.closest('section'),c=s.cloneNode(true);c.querySelector('h2').textContent='{year}年の展示飛行の日程（アーカイブ）';a=c.querySelector('tbody');a.id='ar{year}';a.textContent='';s.after(c)}}"
              "past.forEach(function(r){a.appendChild(r)});if(!u.rows.length)u.closest('section').style.display='none'})();</script>")
        out += js + "\n"
    return out

def video_block(url):
    """この面の行事の動画（events.json の videos。埋め込みが許された公式の動画だけ）。押すまで YouTube は読み込まない"""
    d = load(); seen = set(); items = []
    for e in sorted((e for e in d["events"] if e.get("page") == url), key=lambda e: e["start"]):
        for v in e.get("videos", []):
            if v["id"] in seen: continue
            seen.add(v["id"])
            vid = html.escape(v["id"])
            items.append(f'<figure class="yt"><button type="button" class="yt-play" data-id="{vid}" aria-label="動画を再生：{html.escape(v["title"])}">'
                         f'<img src="https://i.ytimg.com/vi/{vid}/hqdefault.jpg" alt="{html.escape(v["title"])}" loading="lazy" width="480" height="360"><span></span></button>'
                         f'<figcaption><b>{e["start"][:4]}年 {html.escape(e["ja"])}</b><br>{html.escape(v["title"])}（{html.escape(v["channel"])}）</figcaption></figure>')
    if not items: return ""
    js = ("<script>(function(){document.querySelectorAll('.yt-play').forEach(function(b){b.addEventListener('click',function(){var f=document.createElement('iframe');"
          "f.src='https://www.youtube-nocookie.com/embed/'+b.dataset.id+'?autoplay=1&rel=0';f.title=b.getAttribute('aria-label');f.allow='autoplay; encrypted-media; picture-in-picture; fullscreen';f.allowFullscreen=true;f.referrerPolicy='strict-origin-when-cross-origin';b.replaceWith(f)})})})();</script>")
    return (f'<section class="block"><h2>行事の動画</h2><div class="yt-list">{"".join(items)}</div>'
            f'<p class="note">再生ボタンを押すと YouTube の動画を読み込みます。</p>{js}</section>\n')

def insert(url, main):
    """行事の面には動画を、予定の一覧を出す面（events.json の list_pages）には一覧を、本文の末尾（出典の前）に足す"""
    d = load()
    main = re.sub(r"(?:<p>)?\{\{events:(\d{4})\}\}(?:</p>)?", lambda m: season_table(m.group(1)), main)  # 本文の {{events:年}} は日程の表にする
    blocks = video_block(url)
    for year, page in sorted(d.get("list_pages", {}).items(), reverse=True):  # 新しい年を上に
        if page == url:
            blocks += schedule_block(year)
    if blocks:
        k = main.find('<section class="sources block">')
        main = main[:k] + blocks + main[k:] if k >= 0 else main + blocks
    return main
