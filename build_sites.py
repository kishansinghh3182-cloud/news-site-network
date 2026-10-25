#!/usr/bin/env python3
"""
Shared static-site builder for every ENABLED site in sites_config.json.

Ad code is read from ads/<site-id>/<slot>.html and used ONLY when the slot is
enabled in sites_config.json and the file exists.

Slots (names match Adsterra unit names):
  Inside the article (placed after a paragraph number, set in config):
    native_banner, banner_300x250, banner_728x90, banner_320x50,
    banner_468x60, banner_160x300, banner_160x600
  Whole site (added before </body>):
    popunder, social_bar, in_page_push

Device setting per inline slot:
  "all"     shown on every screen
  "desktop" shown only on wide screens (>= 700px)
  "mobile"  shown only on small screens (< 700px)
"""

import html
import json
from datetime import datetime
from pathlib import Path

CONFIG = Path("sites_config.json")
OUT = Path("sites")
ADS_DIR = Path("ads")

INLINE_SLOTS = [
    "native_banner",
    "banner_300x250",
    "banner_728x90",
    "banner_320x50",
    "banner_468x60",
    "banner_160x300",
    "banner_160x600",
]
GLOBAL_SLOTS = ["popunder", "social_bar", "in_page_push"]

CSS = """
:root { --brand: BRAND; }
* { box-sizing: border-box; }
body { margin: 0; font-family: -apple-system, Segoe UI, Roboto, Arial, sans-serif;
       background: #f6f7f9; color: #1d1d1f; line-height: 1.75; }
header { background: var(--brand); color: #fff; padding: 16px; }
.name { color: #fff; font-weight: 700; font-size: 1.25rem; text-decoration: none; }
nav a { color: #fff; margin-right: 14px; text-decoration: none; font-size: .95rem; opacity: .92; }
main { max-width: 760px; margin: 0 auto; padding: 20px 16px 40px; }
.tagline { color: #6b7280; margin: 0 0 18px; }
.card { background: #fff; border-radius: 12px; padding: 18px; margin-bottom: 14px;
        box-shadow: 0 2px 8px rgba(0,0,0,.05); }
.card h2 { font-size: 1.1rem; margin: 0 0 6px; }
.card h2 a { color: #1d1d1f; text-decoration: none; }
.date { color: #6b7280; font-size: .85rem; }
.empty { color: #6b7280; background: #fff; padding: 18px; border-radius: 12px; }
.article { background: #fff; border-radius: 12px; padding: 22px 18px;
           box-shadow: 0 2px 8px rgba(0,0,0,.05); }
.article h1 { font-size: 1.6rem; line-height: 1.3; margin: 0 0 10px; }
.article p { font-size: 1.05rem; margin: 0 0 18px; }
.ad-slot { margin: 18px 0; text-align: center; overflow-x: auto; }
.desk-only { display: none; }
.mob-only { display: block; }
@media (min-width: 700px) {
  .desk-only { display: block; }
  .mob-only { display: none; }
}
.btn { display: inline-block; margin-top: 8px; background: var(--brand); color: #fff !important;
       padding: 12px 20px; border-radius: 8px; text-decoration: none; font-weight: 600; }
footer { text-align: center; color: #6b7280; font-size: .85rem; padding: 24px 16px; }
footer a { color: #6b7280; margin: 0 8px; }
"""

PAGES = [
    ("index.html", "Home"),
    ("about.html", "About"),
    ("contact.html", "Contact"),
    ("privacy.html", "Privacy Policy"),
]


def load_json(path, default):
    if Path(path).exists():
        return json.loads(Path(path).read_text(encoding="utf-8"))
    return default


def slot_code(site, slot):
    """Ad HTML for this slot, or '' if disabled or the file is missing."""
    cfg = site.get("ads", {}).get(slot, {})
    if not cfg.get("enabled"):
        return ""
    path = ADS_DIR / site["id"] / f"{slot}.html"
    if not path.exists():
        print(f"  [{site['id']}] ad '{slot}' is enabled but {path} does not exist")
        return ""
    return path.read_text(encoding="utf-8").strip()


def global_ads(site):
    codes = [slot_code(site, s) for s in GLOBAL_SLOTS]
    return "\n".join(c for c in codes if c)


def layout(site, title, body, description, canonical="", jsonld=""):
    nav = "".join(f'<a href="{href}">{label}</a>' for href, label in PAGES)
    name = html.escape(site["name"])
    css = CSS.replace("BRAND", site["color"])
    canon_tag = f'<link rel="canonical" href="{html.escape(canonical, quote=True)}">' if canonical else ""
    ads = global_ads(site)
    year = datetime.now().year
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{html.escape(title)} | {name}</title>
<meta name="description" content="{html.escape(description, quote=True)}">
{canon_tag}
{jsonld}
<style>{css}</style>
</head>
<body>
<header>
  <a class="name" href="index.html">{name}</a>
  <div><nav>{nav}</nav></div>
</header>
<main>
{body}
</main>
<footer>
  &copy; {year} {name}
  <a href="about.html">About</a><a href="privacy.html">Privacy</a><a href="contact.html">Contact</a>
</footer>
{ads}
</body>
</html>
"""


def index_body(site, articles):
    if articles:
        cards = "\n".join(
            f'<div class="card"><h2><a href="{html.escape(a["slug"])}.html">'
            f'{html.escape(a["headline"])}</a></h2>'
            f'<div class="date">{html.escape(a["date"])}</div></div>'
            for a in articles[:50]
        )
    else:
        cards = '<p class="empty">First stories are on the way. Check back soon.</p>'
    return f'<p class="tagline">{html.escape(site["tagline"])}</p>\n{cards}'


def placed_inline_ads(site, paragraph_count):
    """Map paragraph number -> list of ad HTML blocks to show after it."""
    placements = {}
    for slot in INLINE_SLOTS:
        cfg = site.get("ads", {}).get(slot, {})
        code = slot_code(site, slot)
        if not code:
            continue
        after = int(cfg.get("after_paragraph", 1))
        after = max(1, min(after, paragraph_count))  # never before 1, never past the last paragraph
        device = cfg.get("device", "all")
        cls = {"desktop": "desk-only", "mobile": "mob-only"}.get(device, "")
        block = f'<div class="ad-slot {cls}">{code}</div>'
        placements.setdefault(after, []).append(block)
    return placements


def article_body(site, article):
    paras = article["paragraphs"]
    placements = placed_inline_ads(site, len(paras))

    parts = []
    for i, p in enumerate(paras, 1):
        parts.append(f"<p>{html.escape(p)}</p>")
        parts.extend(placements.get(i, []))
    paragraphs_html = "\n".join(parts)

    source_url = html.escape(article["source_url"], quote=True)
    return f"""<article class="article">
<h1>{html.escape(article["headline"])}</h1>
<div class="date">{html.escape(article["date"])} &middot; Source: {html.escape(article["source_name"])}</div>
<br>
{paragraphs_html}
<a class="btn" href="{source_url}" target="_blank" rel="noopener noreferrer">Read Full Article / Continue</a>
<p><a href="index.html">&larr; Back to all stories</a></p>
</article>"""


def jsonld_for(article, canonical):
    data = {
        "@context": "https://schema.org",
        "@type": "NewsArticle",
        "headline": article["headline"],
        "description": article["paragraphs"][0][:150],
        "datePublished": article["iso"],
        "dateModified": article["iso"],
        "mainEntityOfPage": canonical,
    }
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    return f'<script type="application/ld+json">{payload}</script>'


def about_body(site):
    name = html.escape(site["name"])
    return f"""
<h1>About {name}</h1>
<p>{name} covers {html.escape(site["tagline"].lower())}. Our stories come from public RSS feeds.
Each story is rewritten in our own words, and every article links to the original source so you can
read the full report.</p>
<p>We are not the original reporters. For important decisions, please check official sources.</p>
"""


def contact_body(site):
    email = html.escape(site["email"])
    return f"""
<h1>Contact</h1>
<p>For questions, corrections or takedown requests, email <a href="mailto:{email}">{email}</a>.</p>
"""


def privacy_body(site):
    name = html.escape(site["name"])
    return f"""
<h1>Privacy Policy</h1>
<p>{name} does not require you to create an account. We may use cookies and basic analytics to
understand traffic. If we show third-party advertising, that provider may also set cookies as described
in its own policy.</p>
<p>Contact us through the Contact page for any privacy question.</p>
<p><em>Note: review this text with a qualified adviser before you rely on it.</em></p>
"""


def build_site(site, articles=None):
    folder = OUT / site["id"]
    folder.mkdir(parents=True, exist_ok=True)
    if articles is None:
        articles = load_json(folder / "articles.json", [])

    base = site["url"].rstrip("/") + "/"

    (folder / "index.html").write_text(
        layout(site, site["name"], index_body(site, articles), site["tagline"]), encoding="utf-8")
    (folder / "about.html").write_text(
        layout(site, "About", about_body(site), "About this site"), encoding="utf-8")
    (folder / "contact.html").write_text(
        layout(site, "Contact", contact_body(site), "Contact us"), encoding="utf-8")
    (folder / "privacy.html").write_text(
        layout(site, "Privacy Policy", privacy_body(site), "Privacy policy"), encoding="utf-8")

    for a in articles:
        canonical = base + a["slug"] + ".html"
        page = layout(
            site, a["headline"], article_body(site, a), a["paragraphs"][0][:150],
            canonical=canonical, jsonld=jsonld_for(a, canonical),
        )
        (folder / f"{a['slug']}.html").write_text(page, encoding="utf-8")

    urls = [base] + [base + a["slug"] + ".html" for a in articles]
    locs = "\n".join(f"  <url><loc>{html.escape(u)}</loc></url>" for u in urls)
    (folder / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{locs}\n</urlset>\n",
        encoding="utf-8",
    )
    (folder / "robots.txt").write_text(
        f"User-agent: *\nAllow: /\nSitemap: {base}sitemap.xml\n", encoding="utf-8")
    (folder / ".nojekyll").write_text("", encoding="utf-8")


def main():
    sites = load_json(CONFIG, [])
    for site in sites:
        if not site.get("enabled"):
            continue
        if "REPLACE-ME" in site["url"] or "REPLACE-ME" in site["email"]:
            print(f"[{site['id']}] WARNING: set real 'url' and 'email' in sites_config.json")
        build_site(site)
        print(f"[{site['id']}] built -> sites/{site['id']}/ ({site['platform']})")


if __name__ == "__main__":
    main()
