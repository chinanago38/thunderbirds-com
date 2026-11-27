"""展示飛行の予定（tools/events.json）から、トップの「次の展示飛行」の記事と予定の一覧を作る。
日付が過ぎた行事は、ページを開いた時に自動で一覧からアーカイブへ移り、次の行事に切り替わる（作り直しは要らない）。"""
import datetime, html, json, os

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

def next_card():
    d = load(); t = today()
    up = sorted((e for e in d["events"] if e["end"] >= t), key=lambda e: e["start"])
    items = []
    for i, e in enumerate(up):
        cls = "ns-first" if i == 0 else ("ns-sub" if i < 4 else "ns-more")
        p, _ = page_of(d, e)
        name = f'<span class="ns-name">{html.escape(e["name"])}</span>' if e.get("name") else ""
        items.append(
            f'<article class="ns-item {cls}" data-start="{e["start"]}" data-end="{e["end"]}">'
            f'<p class="ns-date">{ja_date(e["start"], e["end"])} <span class="ns-left"></span></p>'
            f'<p class="ns-place">{html.escape(e["ja"])}</p><p class="ns-en">{name} <small>{html.escape(e["place"])}</small></p>'
            f'<p class="ns-links">{links(d, e)}</p>'
            + (f'<a class="ns-cover" href="{p}" aria-label="{html.escape(e["ja"])}の案内"></a>' if p else "") + "</article>")
    last = max((e["start"][:4] for e in d["events"]), default=t[:4])
    year = int(last) + 1 if not up else None
    pending_year = year or int(last) + 1
    past = d.get("list_pages", {}).get(last)
    pending = (f'<div class="ns-pending"{" hidden" if up else ""}><p class="ns-date">{pending_year}年の公式発表待ち</p>'
               f'<p>{pending_year}年の展示飛行の日程は、公式の発表を待っています。発表された分から、ここに載せます。</p>'
               f'<p class="ns-links">' + (f'<a class="btn" href="{past}">{last}年の日程の一覧</a> ' if past else "")
               + f'<a href="{html.escape(d["source"])}" target="_blank" rel="noopener">{html.escape(d["source_name"])}</a></p></div>')
    js = ("<script>(function(){var b=document.getElementById('nextshow');if(!b)return;var n=new Date(),p=function(v){return ('0'+v).slice(-2)},"
          "t=n.getFullYear()+'-'+p(n.getMonth()+1)+'-'+p(n.getDate()),day=function(s){var a=s.split('-');return Date.UTC(a[0],a[1]-1,a[2])};"
          "var rows=[].slice.call(b.querySelectorAll('.ns-item')).filter(function(x){if(x.dataset.end<t){x.remove();return false}return true});"
          "rows.forEach(function(x,i){x.className='ns-item '+(i===0?'ns-first':i<4?'ns-sub':'ns-more');var l=x.querySelector('.ns-left'),k=Math.round((day(x.dataset.start)-day(t))/864e5);"
          "l.textContent=k>0?'あと'+k+'日':'開催期間中'});if(!rows.length){b.querySelector('.ns-pending').hidden=false}})();</script>")
    return (f'<section class="block nextshow" id="nextshow"><h2>次の展示飛行</h2>{pending}<div class="ns-list">{"".join(items)}</div>'
            f'<p class="note">日付は開催地の日付です。予定は変わることがあります。{html.escape(d["source_name"])}で{html.escape(d["checked_ja"])}に確かめた内容です。</p>{js}</section>\n')

def schedule_block(year):
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
    up = [e for e in rows if e["end"] >= t]; old = [e for e in rows if e["end"] < t]
    js = ("<script>(function(){var n=new Date(),p=function(v){return ('0'+v).slice(-2)},t=n.getFullYear()+'-'+p(n.getMonth()+1)+'-'+p(n.getDate());"
          f"var u=document.getElementById('up{year}'),a=document.getElementById('ar{year}');if(!u||!a)return;"
          "[].slice.call(u.querySelectorAll('tr[data-end]')).forEach(function(r){if(r.dataset.end<t)a.appendChild(r)});"
          "u.closest('section').style.display=u.rows.length?'':'none';a.closest('section').style.display=a.rows.length?'':'none'})();</script>")
    return (f'<section class="block"{"" if up else " style=display:none"}><h2>{year}年のこれからの展示飛行</h2><div class="table-wrap"><table>{head}<tbody id="up{year}">{"".join(map(tr, up))}</tbody></table></div></section>\n'
            f'<section class="block"{"" if old else " style=display:none"}><h2>{year}年の展示飛行の日程（アーカイブ）</h2><div class="table-wrap"><table>{head}<tbody id="ar{year}">{"".join(map(tr, old))}</tbody></table></div></section>\n{js}\n')

def insert(url, main):
    """予定の一覧を出す面（events.json の list_pages）の本文の末尾（出典の前）に一覧を足す"""
    d = load()
    for year, page in sorted(d.get("list_pages", {}).items(), reverse=True):  # 新しい年を上に
        if page == url:
            block = schedule_block(year)
            k = main.find('<section class="sources block">')
            main = main[:k] + block + main[k:] if k >= 0 else main + block
    return main
