#!/usr/bin/env python3
"""Generate index.html for the stocks site from data/posts.json."""
import json, html, pathlib

ROOT = pathlib.Path(__file__).parent
posts = json.loads((ROOT / "data" / "posts.json").read_text(encoding="utf-8"))

def card(p):
    lis = "\n".join(f"<li>{html.escape(x)}</li>" for x in p["body"])
    return f"""<article class="card">
<div class="date">{html.escape(p['date'])}</div>
<h3>{html.escape(p['title'])}</h3>
<ul>{lis}</ul>
</article>"""

def column(items):
    if not items:
        return '<p class="empty">敬请期待</p>'
    return "\n".join(card(p) for p in items)

page = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>美股早晚盘 · 盘前新闻 盘后个股</title>
<link rel="stylesheet" href="styles.css">
</head>
<body>
<div class="wrap">
<header class="site">
<h1>美股<span>早晚盘</span></h1>
<p>盘前新闻 · 盘后个股 —— 每天两条，浓缩加一点解读</p>
</header>
<main class="cols">
<section class="col premarket">
<h2>☀ 早盘新闻</h2>
{column(posts.get("premarket", []))}
</section>
<section class="col postmarket">
<h2>🌙 晚盘个股</h2>
{column(posts.get("postmarket", []))}
</section>
</main>
<footer class="site">
<p>内容仅供参考，不构成投资建议。数据来自公开市场信息，正式决策请以券商行情为准。</p>
</footer>
</div>
</body>
</html>
"""
(ROOT / "index.html").write_text(page, encoding="utf-8")
print("index.html generated")
