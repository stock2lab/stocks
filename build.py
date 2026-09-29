#!/usr/bin/env python3
"""Generate the stocks site: index.html, per-post pages, sitemap.xml, feed.xml.

Source of truth: data/posts.json
  {"premarket": [{"date": "YYYY-MM-DD", "title": "...", "body": ["...", ...]}], "postmarket": [...]}
"""
import html
import json
import pathlib
from datetime import datetime, timezone, timedelta

ROOT = pathlib.Path(__file__).parent
SITE = "https://stocks.bjxihi.com"
# Google Analytics 4 Measurement ID — 用户在 analytics.google.com 建好媒体资源后替换
GA_ID = "G-XXXXXXXXXX"

COL_NAMES = {"premarket": "早盘新闻", "postmarket": "晚盘个股"}
COL_ICONS = {"premarket": "☀", "postmarket": "🌙"}

posts = json.loads((ROOT / "data" / "posts.json").read_text(encoding="utf-8"))
CSS = (ROOT / "styles.css").read_text(encoding="utf-8")


def ga_snippet():
    return (
        f'<script async src="https://www.googletagmanager.com/gtag/js?id={GA_ID}"></script>\n'
        f"<script>window.dataLayer=window.dataLayer||[];"
        f"function gtag(){{dataLayer.push(arguments)}};"
        f"gtag('js',new Date());gtag('config','{GA_ID}');</script>"
    )


def head(title, desc, url):
    return f"""<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<meta name="description" content="{html.escape(desc)}">
<link rel="canonical" href="{url}">
<meta property="og:type" content="article">
<meta property="og:title" content="{html.escape(title)}">
<meta property="og:description" content="{html.escape(desc)}">
<meta property="og:url" content="{url}">
<meta property="og:site_name" content="美股早晚盘">
<link rel="stylesheet" href="/styles.css">
{ga_snippet()}"""


def header():
    return """<header class="site">
<h1><a href="/" style="color:inherit;text-decoration:none">美股<span>早晚盘</span></a></h1>
<p>盘前新闻 · 盘后个股 —— 每天两条，浓缩加一点解读</p>
</header>"""


def footer():
    return """<footer class="site">
<p>内容仅供参考，不构成投资建议。数据来自公开市场信息，正式决策请以券商行情为准。</p>
</footer>"""


def shell(title, desc, url, body_html):
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
{head(title, desc, url)}
</head>
<body>
<div class="wrap">
{header()}
{body_html}
{footer()}
</div>
</body>
</html>
"""


def slug(col, p):
    return f"{p['date']}-{col}.html"


def desc_of(p):
    text = p["body"][0] if p["body"] else p["title"]
    return text[:90]


# ---- per-post pages ----
post_dir = ROOT / "posts"
post_dir.mkdir(exist_ok=True)
all_posts = []
for col in ("premarket", "postmarket"):
    for p in posts.get(col, []):
        s = slug(col, p)
        url = f"{SITE}/posts/{s}"
        lis = "\n".join(f"<li>{html.escape(x)}</li>" for x in p["body"])
        body_html = f"""<main>
<nav style="margin-bottom:16px;font-size:14px"><a href="/">← 返回首页</a> · {COL_ICONS[col]} {COL_NAMES[col]}</nav>
<article class="card">
<div class="date">{html.escape(p['date'])} · {COL_NAMES[col]}</div>
<h3 style="font-size:20px">{html.escape(p['title'])}</h3>
<ul style="margin-top:12px">{lis}</ul>
</article>
</main>"""
        (post_dir / s).write_text(
            shell(f"{p['title']} · 美股早晚盘", desc_of(p), url, body_html),
            encoding="utf-8",
        )
        all_posts.append((col, p, s, url))

# ---- index.html ----
def card(col, p):
    s = slug(col, p)
    lis = "\n".join(f"<li>{html.escape(x)}</li>" for x in p["body"])
    return f"""<article class="card">
<div class="date">{html.escape(p['date'])}</div>
<h3><a href="/posts/{s}" style="color:inherit;text-decoration:none">{html.escape(p['title'])}</a></h3>
<ul>{lis}</ul>
</article>"""


def column(col, items):
    inner = "\n".join(card(col, p) for p in items) or '<p class="empty">敬请期待</p>'
    return f"""<section class="col {col}">
<h2>{COL_ICONS[col]} {COL_NAMES[col]}</h2>
{inner}
</section>"""


index_body = f"""<main class="cols">
{column('premarket', posts.get('premarket', []))}
{column('postmarket', posts.get('postmarket', []))}
</main>"""
(ROOT / "index.html").write_text(
    shell(
        "美股早晚盘 · 盘前新闻 盘后个股",
        "美股早晚盘：每天两条，盘前新闻与盘后个股复盘，浓缩加一点解读。",
        SITE + "/",
        index_body,
    ),
    encoding="utf-8",
)

# ---- sitemap.xml ----
urls = [(SITE + "/", max(
    (p["date"] for _, p, _, _ in all_posts), default="2026-09-29"
))]
for _, p, _, url in all_posts:
    urls.append((url, p["date"]))
sm = ['<?xml version="1.0" encoding="UTF-8"?>',
      '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
for loc, lastmod in urls:
    sm.append(f"  <url><loc>{loc}</loc><lastmod>{lastmod}</lastmod></url>")
sm.append("</urlset>")
(ROOT / "sitemap.xml").write_text("\n".join(sm), encoding="utf-8")

# ---- feed.xml (RSS 2.0) ----
tz = timezone(timedelta(hours=8))
items = []
for col, p, _, url in sorted(all_posts, key=lambda t: t[1]["date"], reverse=True)[:20]:
    pub = datetime.strptime(p["date"], "%Y-%m-%d").replace(tzinfo=tz, hour=12)
    pub_str = pub.strftime("%a, %d %b %Y %H:%M:%S %z")
    lis = "".join(f"<li>{html.escape(x)}</li>" for x in p["body"])
    items.append(
        f"    <item><title>{html.escape(p['title'])}（{COL_NAMES[col]}）</title>"
        f"<link>{url}</link><guid>{url}</guid><pubDate>{pub_str}</pubDate>"
        f"<description>{html.escape(f'<ul>{lis}</ul>')}</description></item>"
    )
rss = ("<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<rss version=\"2.0\">\n"
       f"  <channel><title>美股早晚盘</title><link>{SITE}/</link>"
       f"<description>盘前新闻 · 盘后个股</description><language>zh-CN</language>\n"
       + "\n".join(items) + "\n  </channel>\n</rss>")
(ROOT / "feed.xml").write_text(rss, encoding="utf-8")

# ---- robots.txt ----
(ROOT / "robots.txt").write_text(
    f"User-agent: *\nAllow: /\nSitemap: {SITE}/sitemap.xml\n", encoding="utf-8"
)

print(f"built: index.html, {len(all_posts)} post pages, sitemap.xml, feed.xml, robots.txt")
