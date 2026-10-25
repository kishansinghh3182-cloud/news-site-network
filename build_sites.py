#!/usr/bin/env python3
"""
Shared static-site builder for every ENABLED site in sites_config.json.

Automatically initializes ads/<site-id>/<slot>.html folders and files if missing!
Ad code is read from ads/<site-id>/<slot>.html and used ONLY when the slot is
enabled in sites_config.json and contains real script code.
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
ALL_SLOTS = INLINE_SLOTS + GLOBAL_SLOTS

B_HOST = "bauval" + "." + "org"
A_HOST = "abscloud" + "." + "org"

DEFAULT_WORLD_ADS = {
    "banner_300x250": f"""<script>
  atOptions = {{
    'key' : '755fb3e29d1681dc4c5a962229d5b139',
    'format' : 'iframe',
    'height' : 250,
    'width' : 300,
    'params' : {{}}
  }};
</script>
<script src="https://{B_HOST}/22/755fb3e29d1681dc4c5a962229d5b139"></script>""",
    "banner_728x90": f"""<script>
  atOptions = {{
    'key' : '9dbe511f25950d15216f7b4041fe5147',
    'format' : 'iframe',
    'height' : 90,
    'width' : 728,
    'params' : {{}}
  }};
</script>
<script src="https://{B_HOST}/22/9dbe511f25950d15216f7b4041fe5147"></script>""",
    "banner_320x50": f"""<script>
  atOptions = {{
    'key' : '877fc421d96cd4e6bd274c893ca69fb1',
    'format' : 'iframe',
    'height' : 50,
    'width' : 320,
    'params' : {{}}
  }};
</script>
<script src="https://{B_HOST}/22/877fc421d96cd4e6bd274c893ca69fb1"></script>""",
    "banner_468x60": f"""<script>
  atOptions = {{
    'key' : 'af982a20140c8e584a3dc97cfdde2d27',
    'format' : 'iframe',
    'height' : 60,
    'width' : 468,
    'params' : {{}}
  }};
</script>
<script src="https://{B_HOST}/22/af982a20140c8e584a3dc97cfdde2d27"></script>""",
    "banner_160x300": f"""<script>
  atOptions = {{
    'key' : '5cd810b4e41913729f223cab6e6420d7',
    'format' : 'iframe',
    'height' : 300,
    'width' : 160,
    'params' : {{}}
  }};
</script>
<script src="https://{B_HOST}/22/5cd810b4e41913729f223cab6e6420d7"></script>""",
    "banner_160x600": f"""<script>
  atOptions = {{
    'key' : '98f65f43b29a2d9d4e9771bf2511c037',
    'format' : 'iframe',
    'height' : 600,
    'width' : 160,
    'params' : {{}}
  }};
</script>
<script src="https://{B_HOST}/22/98f65f43b29a2d9d4e9771bf2511c037"></script>""",
    "native_banner": f"""<script async="async" data-cfasync="false" src="https://{B_HOST}/21/ea3e1551321654d2c4efcb7588937f56"></script>
<div id="container-ea3e1551321654d2c4efcb7588937f56"></div>""",
    "popunder": f"""<script data-cfasync="false" src="https://{A_HOST}/1/53846a5d076b4b34b98c6a99a31759cd"></script>""",
    "social_bar": f"""<script data-cfasync="false" src="https://{B_HOST}/14/10a88dac3b14668ae24c20eda10e2434"></script>""",
}

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


def ensure_ads_files(site):
    """Automatically create ads/<site_id>/<slot>.html folders and files if they don't exist."""
    sid = site["id"]
    site_ads_dir = ADS_DIR / sid
    site_ads_dir.mkdir(parents=True, exist_ok=True)
    for slot in ALL_SLOTS:
        path = site_ads_dir / f"{slot}.html"
        if not path.exists():
            if sid == "world" and slot in DEFAULT_WORLD_ADS:
                path.write_text(DEFAULT_WORLD_ADS[slot] + "\n", encoding="utf-8")
                print(f"  [{sid}] auto-created {path} with default Adsterra code")
            else:
                placeholder = f"<!-- Paste your Adsterra '{slot}' code for '{sid}' site here -->\n"
                path.write_text(placeholder, encoding="utf-8")
                print(f"  [{sid}] auto-created placeholder {path}")


def slot_code(site, slot):
    """Ad HTML for this slot, or '' if disabled, missing, or only a comment placeholder."""
    cfg = site.get("ads", {}).get(slot, {})
    if not cfg.get("enabled"):
        return ""
    path = ADS_DIR / site["id"] / f"{slot}.html"
    if not path.exists():
        return ""
    content = path.read_text(encoding="utf-8").strip()
    if not content or (content.startswith("<!--") and content.endswith("-->") and "<script" not in content.lower()):
        return ""
    return content


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
    schema_ctx = "https://schema" + ".org"
    data = {
        "@context": schema_ctx,
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
    ensure_ads_files(site)
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
    sm_ns = "http://www.sitemaps" + ".org/schemas/sitemap/0.9"
    (folder / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<urlset xmlns="{sm_ns}">\n'
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
