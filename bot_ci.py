#!/usr/bin/env python3
"""
bot_ci.py – single-shot version for GitHub Actions / cron.
Collects vless:// and https://t.me/proxy? links, saves them separately,
and generates a base64 subscription file for v2rayN.
"""

import os
import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path

from telethon import TelegramClient
from telethon.tl.types import Message
from dotenv import load_dotenv

from src.github_uploader import GitHubUploader
from src.config_parser import extract_configs, deduplicate_configs, build_subscription

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

API_ID       = int(os.environ["TELEGRAM_API_ID"])
API_HASH     = os.environ["TELEGRAM_API_HASH"]
CHANNEL      = os.environ["TELEGRAM_CHANNEL"]
GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]
GITHUB_REPO  = os.environ["GITHUB_REPO"]
FETCH_LIMIT  = int(os.getenv("FETCH_LIMIT", "200"))

CONFIGS_DIR = Path("configs")
STATE_FILE  = Path(".last_message_id")
VLESS_FILE  = CONFIGS_DIR / "vless.txt"
PROXY_FILE  = CONFIGS_DIR / "telegram_proxy.txt"
SUB_FILE    = CONFIGS_DIR / "subscription.txt"


def load_last_id() -> int:
    try:
        return int(STATE_FILE.read_text().strip()) if STATE_FILE.exists() else 0
    except ValueError:
        return 0


def merge(path: Path, new_items: list) -> list:
    existing = [l.strip() for l in path.read_text().splitlines() if l.strip()] if path.exists() else []
    return deduplicate_configs(existing + new_items)


async def main():
    uploader = GitHubUploader(GITHUB_TOKEN, GITHUB_REPO)
    last_id  = load_last_id()
    newest   = last_id
    raw_vless, raw_proxy = [], []

    proxy = None
    if os.getenv("PROXY_TYPE"):
        import socks
        proxy = (socks.SOCKS5, os.getenv("PROXY_HOST", "127.0.0.1"), int(os.getenv("PROXY_PORT", "10808")))

    async with TelegramClient("v2ray_session", API_ID, API_HASH, proxy=proxy) as client:
        async for msg in client.iter_messages(CHANNEL, limit=FETCH_LIMIT, min_id=last_id):
            if isinstance(msg, Message) and msg.text:
                found = extract_configs(msg.text)
                raw_vless.extend(found["vless"])
                raw_proxy.extend(found["proxy"])
            if msg.id > newest:
                newest = msg.id

    if newest > last_id:
        STATE_FILE.write_text(str(newest))

    new_vless = deduplicate_configs(raw_vless)
    new_proxy = deduplicate_configs(raw_proxy)
    log.info("New links — vless: %d  proxy: %d", len(new_vless), len(new_proxy))

    if not new_vless and not new_proxy:
        log.info("Nothing new, exiting.")
        return

    CONFIGS_DIR.mkdir(exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    commit_msg = f"update configs [{ts}] (+{len(new_vless)} vless, +{len(new_proxy)} proxy)"

    if new_vless:
        all_vless = merge(VLESS_FILE, new_vless)
        VLESS_FILE.write_text("\n".join(all_vless) + "\n")
        uploader.upload_file(VLESS_FILE, str(VLESS_FILE), commit_msg)

        # Subscription file (base64) — used directly in v2rayN as a sub URL
        sub = build_subscription(all_vless)
        SUB_FILE.write_text(sub)
        uploader.upload_file(SUB_FILE, str(SUB_FILE), commit_msg)
        log.info("Subscription updated: %d total vless configs", len(all_vless))

    if new_proxy:
        all_proxy = merge(PROXY_FILE, new_proxy)
        PROXY_FILE.write_text("\n".join(all_proxy) + "\n")
        uploader.upload_file(PROXY_FILE, str(PROXY_FILE), commit_msg)

    uploader.upload_file(STATE_FILE, ".last_message_id", commit_msg)
    log.info("Done.")


asyncio.run(main())
