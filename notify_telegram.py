#!/usr/bin/env python3
"""
Sends each queued article to Telegram with its LIVE site link.
Run this only AFTER the site branches are pushed and Pages has had time to deploy.
Clears the queue when done.
"""

import os
import json
import html
from pathlib import Path

import requests

PENDING = Path("state/pending.json")
CONFIG = Path("sites_config.json")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")


def load_json(path, default):
    if Path(path).exists():
        return json.loads(Path(path).read_text(encoding="utf-8"))
    return default


def send(payload):
    r = requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
        json=payload,
        timeout=30,
    )
    r.raise_for_status()


def main():
    if not (TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID):
        print("Telegram not configured, skipping.")
        return

    pending = load_json(PENDING, [])
    if not pending:
        print("No pending articles to send.")
        return

    sites = {s["id"]: s for s in load_json(CONFIG, [])}

    for item in pending:
        site = sites.get(item["site_id"])
        if not site:
            print(f"Unknown site in queue: {item['site_id']}")
            continue

        our_url = site["url"].rstrip("/") + "/" + item["slug"] + ".html"
        paras = "\n\n".join(html.escape(p) for p in item["paragraphs"])
        text = (
            f"<b>[{html.escape(site['name'])}] {html.escape(item['headline'])}</b>\n\n"
            f"{paras}\n\n"
            f"Source: {html.escape(item['source_name'])}\n"
            f"Our link: {html.escape(our_url)}"
        )

        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": text[:4096],
            "parse_mode": "HTML",
            "disable_web_page_preview": False,
            "reply_markup": {"inline_keyboard": [
                [{"text": "Read on our site", "url": our_url}],
                [{"text": "Original source", "url": item["source_url"]}],
            ]},
        }
        try:
            send(payload)
            print(f"sent: {our_url}")
        except Exception as ex:
            print(f"failed to send {our_url}: {ex}")

    PENDING.write_text("[]", encoding="utf-8")


if __name__ == "__main__":
    main()
