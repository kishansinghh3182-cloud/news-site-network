#!/usr/bin/env python3
"""
Each run: for every ENABLED site, fetch its RSS feeds, rewrite ONE new story
in that site's editorial angle, save it to sites/<id>/articles.json, rebuild
the site, and send a copy to Telegram (for Google Sites, which has no API).
"""

import os
import re
import json
import time
import html
import hashlib
from datetime import datetime, timezone
from itertools import zip_longest
from pathlib import Path

import requests
import feedparser
import google.generativeai as genai

import build_sites

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

STATE_DIR = Path("state")
MAX_SEEN = 500

PROMPT = """You write for a news website. Editorial angle: {angle}.
Rewrite the news item below as an ORIGINAL English article.
Rules:
- Use your own words and sentence structure. Do not copy phrases from the input.
- Write exactly two engaging paragraphs (about 120 to 160 words in total).
- Use only facts given in the input. Do not invent names, numbers or quotes.
- Output format: first line "HEADLINE: <new catchy headline>", then a blank line,
  then paragraph 1, a blank line, then paragraph 2.
- Plain text only. No markdown, no bullet points.

NEWS TITLE: {title}
NEWS DESCRIPTION: {summary}
"""


def load_json(path, default):
    path = Path(path)
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return default


def save_json(path, data):
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def strip_html(text):
    text = re.sub(r"<[^>]+>", " ", text or "")
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def slugify(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def parse_feed(url):
    feed = feedparser.parse(url)
    source_name = feed.feed.get("title", url)
    items = []
    for e in feed.entries:
        link = e.get("link")
        if not link:
            continue
        title = strip_html(e.get("title", ""))
        summary = strip_html(e.get("summary", "")) or title
        raw_key = e.get("id") or link
        items.append({
            "key": hashlib.sha256(raw_key.encode("utf-8")).hexdigest(),
            "title": title,
            "summary": summary,
            "link": link,
            "source": source_name,
        })
    return items


def fetch_items(urls):
    per_feed = []
    for url in urls:
        try:
            items = parse_feed(url)
            per_feed.append(items)
            print(f"  feed OK: {url} ({len(items)} items)")
        except Exception as ex:
            print(f"  feed failed: {url}: {ex}")
    merged = []
    for group in zip_longest(*per_feed):  # round-robin for topic variety
        merged.extend(x for x in group if x)
    if not merged:
        raise RuntimeError("no feed items available")
    return merged


def parse_article(text):
    lines = [l.rstrip() for l in text.strip().splitlines()]
    headline = ""
    if lines and lines[0].upper().startswith("HEADLINE:"):
        headline = lines[0][len("HEADLINE:"):].strip()
        lines = lines[1:]
    body = "\n".join(lines).strip()
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip()]
    if not headline or len(paragraphs) < 2:
        raise ValueError("unexpected model output format")
    return headline, paragraphs[:2]


def ask_gemini(prompt):
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel(GEMINI_MODEL)
    return model.generate_content(prompt).text


def ask_groq(prompt):
    r = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
        json={"model": GROQ_MODEL,
              "messages": [{"role": "user", "content": prompt}],
              "temperature": 0.8},
        timeout=60,
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


def generate_article(angle, title, summary):
    prompt = PROMPT.format(angle=angle, title=title, summary=summary)
    providers = []
    if GEMINI_API_KEY:
        providers.append(("gemini", ask_gemini))
    if GROQ_API_KEY:
        providers.append(("groq", ask_groq))
    errors = []
    for name, fn in providers:
        for attempt in range(1, 3):
            try:
                return parse_article(fn(prompt))
            except Exception as ex:
                errors.append(f"{name}#{attempt}: {ex}")
                time.sleep(10 * attempt)
    raise RuntimeError(" | ".join(errors) or "no AI provider configured")


def send_telegram(site, article):
    if not (TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID):
        print("  Telegram not configured, skipping.")
        return
    text = (
        f"<b>[{html.escape(site['name'])}] {html.escape(article['headline'])}</b>\n\n"
        + "\n\n".join(html.escape(p) for p in article["paragraphs"])
        + f"\n\nSource: {html.escape(article['source_name'])}"
    )
    r = requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
        json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": text[:4096],
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
            "reply_markup": {"inline_keyboard": [[
                {"text": "Read Full Article / Continue", "url": article["source_url"]}
            ]]},
        },
        timeout=30,
    )
    r.raise_for_status()


def process_site(site):
    sid = site["id"]
    seen_path = STATE_DIR / f"{sid}_seen.json"
    seen = load_json(seen_path, [])

    items = fetch_items(site["feeds"])
    fresh = [it for it in items if it["key"] not in seen]
    if not fresh:
        print(f"[{sid}] nothing new")
        return

    item = fresh[0]
    seen.append(item["key"])            # mark first, so a failing story is not retried forever
    save_json(seen_path, seen[-MAX_SEEN:])

    headline, paragraphs = generate_article(site["angle"], item["title"], item["summary"])

    now = datetime.now(timezone.utc)
    article = {
        "slug": f"{now:%Y%m%d-%H%M}-{slugify(headline)[:60] or 'story'}",
        "headline": headline,
        "paragraphs": paragraphs,
        "date": now.strftime("%d %b %Y"),
        "iso": now.isoformat(),
        "source_name": item["source"],
        "source_url": item["link"],
    }

    folder = build_sites.OUT / sid
    folder.mkdir(parents=True, exist_ok=True)
    articles_path = folder / "articles.json"
    articles = load_json(articles_path, [])
    articles.insert(0, article)
    save_json(articles_path, articles)

    build_sites.build_site(site, articles)
    print(f"[{sid}] published: {headline}")

    try:
        send_telegram(site, article)
    except Exception as ex:
        print(f"[{sid}] Telegram failed (article is still saved): {ex}")


def main():
    if not (GEMINI_API_KEY or GROQ_API_KEY):
        raise SystemExit("ERROR: set GEMINI_API_KEY (or GROQ_API_KEY).")
    STATE_DIR.mkdir(exist_ok=True)

    sites = [s for s in load_json(build_sites.CONFIG, []) if s.get("enabled")]
    print(f"Enabled sites: {[s['id'] for s in sites]}")

    for site in sites:
        try:
            process_site(site)
        except Exception as ex:
            print(f"[{site['id']}] FAILED: {ex}")


if __name__ == "__main__":
    main()
