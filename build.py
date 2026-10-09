#!/usr/bin/env python3
"""Generate the stocks site: index.html, per-post pages, sitemap.xml, feed.xml.

Source of truth: data/posts.json
  {"premarket": [...], "postmarket": [...], "review": [...], "stock": [...]}
  each entry: {"date": "YYYY-MM-DD", "title": "...", "body": ["...", ...]}
  "review" holds 每周复盘 (Saturdays) and 月度复盘 (1st of month) posts.
  "stock" holds 每周一股 (Sundays) single-stock profiles.
"""
import html
import json
import pathlib
from datetime import datetime, timezone, timedelta

ROOT = pathlib.Path(__file__).parent
SITE = "https://stocks.bjxihi.com"
# Google Analytics 4 Measurement ID — 用户在 analytics.google.com 建好媒体资源后替换
GA_ID = "G-4Y532TX5S0"

COL_NAMES = {"premarket": "早盘新闻", "postmarket": "晚盘个股", "review": "周月复盘", "stock": "每周一股"}
COL_ICONS = {"premarket": "☀", "postmarket": "🌙", "review": "📊", "stock": "🎯"}

BEIJING = timezone(timedelta(hours=8))


def eastern_offset(dt_beijing):
    """US Eastern UTC offset at the given Beijing datetime (EDT/EST)."""
    y = dt_beijing.year

    def nth_sunday(year, month, n):
        d = datetime(year, month, 1)
        days = (6 - d.weekday()) % 7
        return (d + timedelta(days=days + 7 * (n - 1))).date()

    dst_start = nth_sunday(y, 3, 2)   # 2nd Sunday of March
    dst_end = nth_sunday(y, 11, 1)    # 1st Sunday of November
    if dst_start <= dt_beijing.date() < dst_end:
        return timedelta(hours=-4)    # EDT
    return timedelta(hours=-5)        # EST


def publish_times(col, p):
    """Return (beijing_str, eastern_str, beijing_dt) for a post.

    Convention: 晚盘 posts go out ~08:21 Beijing, 早盘 ~20:21 Beijing,
    复盘 posts ~08:30 Beijing. A post may override with an
    explicit "published_beijing": "YYYY-MM-DD HH:MM" field.
    """
    explicit = p.get("published_beijing")
    if explicit:
        bj = datetime.strptime(explicit, "%Y-%m-%d %H:%M").replace(tzinfo=BEIJING)
    else:
        h, m = {"postmarket": (8, 21), "premarket": (20, 21),
                "review": (8, 30), "stock": (8, 30)}[col]
        bj = datetime.strptime(p["date"], "%Y-%m-%d").replace(
            tzinfo=BEIJING, hour=h, minute=m)
    et = bj.astimezone(timezone(eastern_offset(bj)))
    return bj.strftime("%Y-%m-%d %H:%M"), et.strftime("%Y-%m-%d %H:%M"), bj


def pubtime_html(col, p):
    _, et_s, _ = publish_times(col, p)
    return (f'<div class="pubtime">发布时间 {html.escape(et_s)}（美东时间）</div>')

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
<link rel="alternate" type="application/rss+xml" title="美股早晚盘 RSS" href="/feed.xml">
{ga_snippet()}"""


def header():
    return """<header class="site">
<h1><a href="/" style="color:inherit;text-decoration:none">美股<span>早晚盘</span></a></h1>
<p>盘前新闻 · 盘后个股 —— 每天两条，浓缩加一点解读 · <a href="/feed.xml">RSS 订阅</a></p>
</header>"""


def footer():
    return """<footer class="site">
<p>内容仅供参考，不构成投资建议。数据来自公开市场信息，正式决策请以券商行情为准。</p>
<p style="margin-top:8px"><a href="/feed.xml">RSS 订阅</a> · <a href="/sitemap.xml">网站地图</a></p>
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
for col in ("premarket", "postmarket", "review", "stock"):
    for p in posts.get(col, []):
        s = slug(col, p)
        url = f"{SITE}/posts/{s}"
        lis = "\n".join(f"<li>{html.escape(x)}</li>" for x in p["body"])
        body_html = f"""<main>
<nav style="margin-bottom:16px;font-size:14px"><a href="/">← 返回首页</a> · {COL_ICONS[col]} {COL_NAMES[col]}</nav>
<article class="card">
<div class="date">{html.escape(p['date'])} · {COL_NAMES[col]}</div>
{pubtime_html(col, p)}
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
{pubtime_html(col, p)}
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
{column('review', posts.get('review', []))}
{column('stock', posts.get('stock', []))}
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
items = []
for col, p, _, url in sorted(all_posts, key=lambda t: t[1]["date"], reverse=True)[:20]:
    _, _, bj_dt = publish_times(col, p)
    pub_str = bj_dt.strftime("%a, %d %b %Y %H:%M:%S %z")
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
