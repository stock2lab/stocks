#!/usr/bin/env python3
"""Generate the stocks site: index.html, per-post pages, sitemap.xml, feed.xml.

Source of truth: data/posts.json
  {"premarket": [...], "postmarket": [...], "review": [...], "stock": [...],
   "preview": [...], "encyclopedia": [...]}
  each entry: {"date": "YYYY-MM-DD", "title": "...", "body": ["...", ...]}
  "review" holds 每周复盘 (Saturdays) and 月度复盘 (1st of month) posts.
  "stock" holds 每周一股 (Sundays) single-stock profiles.
  "encyclopedia" holds 美股百科 long-form explainers. "glossary" holds
  术语词典 entries, "etf" holds ETF 指南, "companies" holds 公司档案
  reference profiles. These four long-form columns are NEVER trimmed:
  unlike the daily columns (posts.json keeps only a recent window:
  早晚盘 7 条, 其余 8 条), evergreen articles stay in posts.json, on
  disk, in the sitemap and in their archive pages forever.
  Long-form entries may carry an optional "slug" (e.g.
  "2026-10-27-encyclopedia-trading-hours") so several articles can share
  a date; without it the file is YYYY-MM-DD-<col>.html. Their body uses
  "## ..." lines as section headings and other lines as paragraphs.
"""
import html
import json
import pathlib
from datetime import datetime, timezone, timedelta

ROOT = pathlib.Path(__file__).parent
SITE = "https://stocks.bjxihi.com"
# Google Analytics 4 Measurement ID — 用户在 analytics.google.com 建好媒体资源后替换
GA_ID = "G-4Y532TX5S0"

COL_NAMES = {"premarket": "早盘新闻", "postmarket": "晚盘个股", "review": "周月复盘", "stock": "每周一股", "preview": "每周前瞻", "encyclopedia": "美股百科", "glossary": "术语词典", "etf": "ETF 指南", "companies": "公司档案"}
COL_ICONS = {"premarket": "☀", "postmarket": "🌙", "review": "📊", "stock": "🎯", "preview": "🗓", "encyclopedia": "📚", "glossary": "📖", "etf": "🧺", "companies": "🏢"}
# 长效栏目：用章节式正文（## 标题 + 段落），永久保留、不裁剪
LONGFORM_COLS = ("encyclopedia", "glossary", "etf", "companies")

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
                "review": (8, 30), "stock": (8, 30),
                "preview": (9, 0), "encyclopedia": (9, 0),
                "glossary": (9, 0), "etf": (9, 0),
                "companies": (9, 0)}[col]
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


def head(title, desc, url, extra=""):
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
{extra}{ga_snippet()}"""


def json_ld_article(col, p, url):
    _, _, bj_dt = publish_times(col, p)
    data = {
        "@context": "https://schema.org",
        "@type": "Article" if col in LONGFORM_COLS else "NewsArticle",
        "headline": p["title"],
        "description": desc_of(p),
        "datePublished": bj_dt.isoformat(),
        "inLanguage": "zh-CN",
        "author": {"@type": "Organization", "name": "美股早晚盘"},
        "publisher": {"@type": "Organization", "name": "美股早晚盘"},
        "mainEntityOfPage": {"@type": "WebPage", "@id": url},
    }
    return ('<script type="application/ld+json">\n'
            + json.dumps(data, ensure_ascii=False) + '\n</script>\n')


def header(h1=True):
    brand = ("<h1><a href=\"/\" style=\"color:inherit;text-decoration:none\">"
             "美股<span>早晚盘</span></a></h1>" if h1 else
             "<div class=\"brand\"><a href=\"/\" style=\"color:inherit;text-decoration:none\">"
             "美股<span>早晚盘</span></a></div>")
    return f"""<header class="site">
{brand}
<p>盘前新闻 · 盘后个股 —— 每天两条，浓缩加一点解读 · <a href="/feed.xml">RSS 订阅</a></p>
<nav class="mainnav"><a href="/">首页</a><a href="/calendar.html">📅 日历</a><a href="/stock.html">🎯 每周一股</a><a href="/preview.html">🗓 每周前瞻</a><a href="/encyclopedia.html">📚 美股百科</a><a href="/glossary.html">📖 术语词典</a><a href="/etf.html">🧺 ETF 指南</a><a href="/companies.html">🏢 公司档案</a></nav>
</header>"""


def footer():
    return """<footer class="site">
<p>内容仅供参考，不构成投资建议。数据来自公开市场信息，正式决策请以券商行情为准。</p>
<p style="margin-top:8px"><a href="/feed.xml">RSS 订阅</a> · <a href="/sitemap.xml">网站地图</a></p>
</footer>"""


def shell(title, desc, url, body_html, extra_head="", site_h1=True):
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
{head(title, desc, url, extra_head)}
</head>
<body>
<div class="wrap">
{header(h1=site_h1)}
{body_html}
{footer()}
</div>
</body>
</html>
"""


def slug(col, p):
    if p.get("slug"):
        return f"{p['slug']}.html"
    return f"{p['date']}-{col}.html"


def longform_body_html(p):
    """Long-form rendering for 美股百科/术语词典/ETF 指南/公司档案:
    '## ...' lines become h3 headings, other lines become paragraphs
    (other columns stay as bullet lists)."""
    parts = []
    for x in p["body"]:
        if x.startswith("## "):
            parts.append(f"<h3>{html.escape(x[3:])}</h3>")
        else:
            parts.append(f"<p>{html.escape(x)}</p>")
    return "\n".join(parts)


def desc_of(p):
    text = p["body"][0] if p["body"] else p["title"]
    return text[:90]


# ---- per-post pages ----
post_dir = ROOT / "posts"
post_dir.mkdir(exist_ok=True)
all_posts = []
for col in ("premarket", "postmarket", "review", "stock", "preview") + LONGFORM_COLS:
    for p in posts.get(col, []):
        s = slug(col, p)
        url = f"{SITE}/posts/{s}"
        if col in LONGFORM_COLS:
            body_inner = longform_body_html(p)
        else:
            lis = "\n".join(f"<li>{html.escape(x)}</li>" for x in p["body"])
            body_inner = f"<ul style=\"margin-top:12px\">{lis}</ul>"
        body_html = f"""<main>
<nav style="margin-bottom:16px;font-size:14px"><a href="/">← 返回首页</a> · {COL_ICONS[col]} {COL_NAMES[col]}</nav>
<article class="card">
<div class="date">{html.escape(p['date'])} · {COL_NAMES[col]}</div>
{pubtime_html(col, p)}
<h1 class="post-title">{html.escape(p['title'])}</h1>
{body_inner}
</article>
</main>"""
        (post_dir / s).write_text(
            shell(f"{p['title']} · 美股早晚盘", desc_of(p), url, body_html,
                  extra_head=json_ld_article(col, p, url), site_h1=False),
            encoding="utf-8",
        )
        all_posts.append((col, p, s, url))

# ---- week grouping (ISO weeks, e.g. 2026年第42周) ----
WEEKDAYS = "一二三四五六日"


def week_title(iso_year, iso_week):
    mon = datetime.fromisocalendar(iso_year, iso_week, 1).date()
    sun = datetime.fromisocalendar(iso_year, iso_week, 7).date()
    return (f"{iso_year}年第{iso_week}周"
            f"（{mon.month}/{mon.day}–{sun.month}/{sun.day}）")


def day_title(date_str):
    d = datetime.strptime(date_str, "%Y-%m-%d").date()
    return f"{d.month}/{d.day} 周{WEEKDAYS[d.weekday()]}"


def week_key_for(col, date_str):
    """ISO week a post belongs to. Sunday columns (每周一股/每周前瞻) are
    forward-looking, so they belong to the coming week."""
    d = datetime.strptime(date_str, "%Y-%m-%d").date()
    if col in ("stock", "preview"):
        d += timedelta(days=1)  # Sunday -> Monday of the coming week
    iso = d.isocalendar()
    return (iso[0], iso[1])


# weeks: (iso_year, iso_week) -> {"review": [(col,p)], "stock": [...],
#          "preview": [...], "days": {date: {"premarket": [...], "postmarket": [...]}}}
def card(col, p):
    s = slug(col, p)
    lis = "\n".join(f"<li>{html.escape(x)}</li>" for x in p["body"])
    return f"""<article class="card">
<div class="date">{html.escape(p['date'])}</div>
{pubtime_html(col, p)}
<h3><a href="/posts/{s}" style="color:inherit;text-decoration:none">{html.escape(p['title'])}</a></h3>
<ul>{lis}</ul>
</article>"""


weeks = {}
for col in ("premarket", "postmarket", "review", "stock", "preview"):
    for p in posts.get(col, []):
        w = weeks.setdefault(week_key_for(col, p["date"]),
                             {"review": [], "stock": [], "preview": [],
                              "days": {}})
        if col in ("review", "stock", "preview"):
            w[col].append((col, p))
        else:
            day = w["days"].setdefault(
                p["date"], {"premarket": [], "postmarket": []})
            day[col].append((col, p))
sorted_weeks = sorted(weeks.items(), reverse=True)


def featured_html(items):
    return "\n".join(
        f'<div class="featured">{card(col, p)}</div>' for col, p in items)


def day_block(date_str, day):
    cards = []
    for col in ("premarket", "postmarket"):
        cards.extend(card(c, p) for c, p in day[col])
    return (f'<div class="day"><h3>{day_title(date_str)}</h3>'
            f'<div class="day-cards">{"".join(cards)}</div></div>')


def week_section(key, w):
    feat = featured_html(w["review"] + w["stock"] + w["preview"])
    days = "\n".join(day_block(d, w["days"][d])
                     for d in sorted(w["days"], reverse=True))
    return (f'<section class="week"><h2 class="week-title">'
            f'{html.escape(week_title(*key))}</h2>\n{feat}\n{days}</section>')


# ---- index.html (只放最新一周完整内容，往期进日历) ----
def week_url(key):
    return f"/week/{key[0]}-{key[1]}.html"


latest_key, latest_w = sorted_weeks[0]
index_body = ("<main>\n" + week_section(latest_key, latest_w)
              + '\n<p class="more-weeks">'
                '<a href="/calendar.html">往期周刊 → 日历</a></p>\n</main>')
(ROOT / "index.html").write_text(
    shell(
        "美股早晚盘 · 盘前新闻 盘后个股",
        "美股早晚盘：每天两条，盘前新闻与盘后个股复盘，浓缩加一点解读。",
        SITE + "/",
        index_body,
    ),
    encoding="utf-8",
)


# ---- per-week pages (/week/YYYY-WW.html): 每周完整周刊 ----
week_dir = ROOT / "week"
week_dir.mkdir(exist_ok=True)
week_pages = []  # (url, lastmod)
for key, w in sorted_weeks:
    rel = f"week/{key[0]}-{key[1]}.html"
    url = SITE + "/" + rel
    title = week_title(*key)
    body = "<main>\n" + week_section(key, w) + "\n</main>"
    (ROOT / rel).write_text(
        shell(f"{title} · 美股早晚盘",
              f"美股早晚盘{title}完整内容：周复盘、每周一股、每周前瞻与每日早晚盘。",
              url, body, site_h1=False),
        encoding="utf-8",
    )
    lastmod = max((p["date"] for _, p in
                   w["review"] + w["stock"] + w["preview"]
                   + [x for d in w["days"].values()
                      for col in ("premarket", "postmarket")
                      for x in d[col]]),
                  default="2026-09-29")
    week_pages.append((url, lastmod))


# ---- calendar.html (按周索引：每周一块，周复盘/每周一股在上，标题链接) ----
def cal_links(items):
    return "\n".join(
        f'<li>{COL_ICONS[col]} <a href="/posts/{slug(col, p)}">'
        f'{html.escape(p["title"])}</a>'
        f'<span class="cdate">{html.escape(p["date"])}</span></li>'
        for col, p in items)


def cal_week(key, w):
    top = cal_links(w["review"] + w["stock"] + w["preview"])
    rest = []
    for d in sorted(w["days"], reverse=True):
        for col in ("premarket", "postmarket"):
            rest.extend(w["days"][d][col])
    return (f'<section class="week cal"><h2 class="week-title">'
            f'<a href="{week_url(key)}">{html.escape(week_title(*key))}</a>'
            f"</h2><ul>\n{top}\n{cal_links(rest)}\n</ul></section>")


cal_body = ("<main>\n<h1 class=\"page-title\">📅 日历</h1>\n"
            + "\n".join(cal_week(k, w) for k, w in sorted_weeks)
            + "\n</main>")
(ROOT / "calendar.html").write_text(
    shell("日历 · 美股早晚盘", "美股早晚盘内容日历：按周归档，周复盘与每周一股置顶。",
          SITE + "/calendar.html", cal_body, site_h1=False),
    encoding="utf-8",
)


# ---- stock.html (每周一股归档) ----
def archive_page(col, icon, name, desc, filename):
    body = ("<main>\n"
            f"<h1 class=\"page-title\">{icon} {name}</h1>\n"
            + "\n".join(card(col, p) for p in posts.get(col, []))
            + "\n</main>")
    (ROOT / filename).write_text(
        shell(f"{name} · 美股早晚盘", desc,
              SITE + "/" + filename, body, site_h1=False),
        encoding="utf-8",
    )


archive_page("stock", "🎯", "每周一股",
             "每周一股归档：每周精选一支本周值得跟踪的股票。",
             "stock.html")
archive_page("preview", "🗓", "每周前瞻",
             "每周前瞻归档：下周美股重要数据、重要财报与关键事件。",
             "preview.html")

# ---- long-form archive pages (长效栏目归档：永久保留) ----
def longform_archive_page(col, icon, name, desc, filename, intro):
    items = sorted(posts.get(col, []),
                   key=lambda p: p["date"], reverse=True)
    body = ("<main>\n"
            f"<h1 class=\"page-title\">{icon} {name}</h1>\n"
            f"<p style=\"margin-bottom:16px\">{intro}</p>\n<ul>\n"
            + "\n".join(
                f'<li>{icon} <a href="/posts/{slug(col, p)}">'
                f'{html.escape(p["title"])}</a>'
                f'<span class="cdate">{html.escape(p["date"])}</span></li>'
                for p in items)
            + "\n</ul>\n")
    if col == "companies":
        # 每周一股已覆盖的公司同样进档案库（只挂链接，不重复写档案）
        stock_items = sorted(posts.get("stock", []),
                             key=lambda p: p["date"], reverse=True)
        body += ("<h2 style=\"margin-top:28px\">每周一股已覆盖</h2>\n<ul>\n"
                 + "\n".join(
                     f'<li>🎯 <a href="/posts/{slug("stock", p)}">'
                     f'{html.escape(p["title"])}</a>'
                     f'<span class="cdate">{html.escape(p["date"])}</span></li>'
                     for p in stock_items)
                 + "\n</ul>\n")
    body += "</main>"
    (ROOT / filename).write_text(
        shell(f"{name} · 美股早晚盘", desc,
              SITE + "/" + filename, body, site_h1=False),
        encoding="utf-8",
    )


longform_archive_page("encyclopedia", "📚", "美股百科",
                      "美股百科归档：美股交易时间、指数、财报、ETF 与术语，常年有效。",
                      "encyclopedia.html",
                      "美股基础知识，常年有效：交易时间、指数、财报、ETF 与常用术语。")
longform_archive_page("glossary", "📖", "术语词典",
                      "术语词典归档：美股财报与研报里最常用的术语，一句话讲清。",
                      "glossary.html",
                      "看财报、看研报总遇到一堆缩写：每个术语一句话定义，加一句怎么用。")
longform_archive_page("etf", "🧺", "ETF 指南",
                      "ETF 指南归档：宽基、行业与红利 ETF 怎么选，常年有效。",
                      "etf.html",
                      "ETF 是'一篮子股票'：这栏讲宽基、行业与红利 ETF 怎么选、怎么比。")
longform_archive_page("companies", "🏢", "公司档案",
                      "公司档案归档：已覆盖公司的业务与关键数字，只讲事实，不做推荐。",
                      "companies.html",
                      "公司档案只记录业务和公开数字，不设触发价和止损价，也不做推荐。")

# ---- sitemap.xml ----
# 注意：posts.json 每栏目只保留最近窗口（早晚盘各 7 条），老文章会
# 掉出 posts.json，但它们的页面仍在 posts/ 磁盘上，并被日历/周刊页
# 链接。sitemap 必须收录磁盘上的全部文章页，否则 Google 只能靠内链
# 慢慢发现（这正是 25 页"已发现 - 尚未编入索引"的来源之一）。
urls = [(SITE + "/", max(
    (p["date"] for _, p, _, _ in all_posts), default="2026-09-29"
))]
seen = {SITE + "/"}
for _, p, _, url in all_posts:
    urls.append((url, p["date"]))
    seen.add(url)
for f in sorted(post_dir.glob("*.html")):
    url = f"{SITE}/posts/{f.name}"
    if url not in seen:
        urls.append((url, f.name[:10]))  # 文件名形如 YYYY-MM-DD-<栏目>.html
        seen.add(url)
for page in ("calendar.html", "stock.html", "preview.html", "encyclopedia.html",
             "glossary.html", "etf.html", "companies.html"):
    urls.append((SITE + "/" + page,
                 max((p["date"] for _, p, _, _ in all_posts),
                     default="2026-09-29")))
urls.extend(week_pages)
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
