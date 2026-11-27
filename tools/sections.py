"""本文の節のうち、写真も表も箱も無い節に、写真を1枚ずつ置く。写真は tools/photos/section.tsv（米軍の公式写真・米政府の著作物。同じ写真はサイトで1回）。"""
import html, os, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VISUAL = re.compile(r'<img |<table|class="(points|steps|faq|cards|gallery|nextshow|ns-|yt|ev-grid|bars|bignum|tl)|<figure')

def rows():
    out = {}
    p = os.path.join(ROOT, "tools", "photos", "section.tsv")
    if os.path.exists(p):
        for l in open(p, encoding="utf-8").read().splitlines()[1:]:
            c = l.split("\t")
            if len(c) >= 7 and c[1].startswith("https://"): out.setdefault(c[0], []).append(c)
    return out

def insert(url, main):
    pool = list(rows().get(url, []))
    if not pool: return main
    def rep(m):
        if not pool or VISUAL.search(m.group(1)): return m.group(0)
        c = [html.escape(x) for x in pool.pop(0)]
        fig = (f'<figure class="photo"><img src="{c[1]}" alt="{c[6]}の公式写真" loading="lazy" decoding="async">'
               f'<figcaption>写真：{c[6]}（撮影：{c[3]}）／<a href="{c[2]}" target="_blank" rel="noopener">Wikimedia Commons</a></figcaption></figure>')
        body = m.group(1)
        k = body.find("</h2>")
        body = body[:k + 5] + "\n" + fig + body[k + 5:] if k >= 0 else fig + body
        return f'<section class="block">{body}</section>'
    return re.sub(r'<section class="block">((?:(?!</section>).)*)</section>', rep, main, flags=re.S)
