#!/usr/bin/env python3
"""
V2Ray Config Collector Bot
Collects vless:// and https://t.me/proxy? links from a Telegram channel
and pushes them to GitHub as separate files.
The vless file is also saved as a base64 subscription link for v2rayN.
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
from src.config_parser import extract_configs, deduplicate_configs, build_subscription, trim_to_limit, VLESS_MAX

load_dotenv()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("bot.log"),
    ],
)
log = logging.getLogger(__name__)

# ── Credentials ───────────────────────────────────────────────────────────────
API_ID       = int(os.environ["TELEGRAM_API_ID"])
API_HASH     = os.environ["TELEGRAM_API_HASH"]
CHANNEL      = os.environ["TELEGRAM_CHANNEL"]
GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]
GITHUB_REPO  = os.environ["GITHUB_REPO"]

# ── Settings ──────────────────────────────────────────────────────────────────
FETCH_LIMIT   = int(os.getenv("FETCH_LIMIT", "200"))
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL_SEC", "600"))
CONFIGS_DIR   = Path("configs")
STATE_FILE    = Path(".last_message_id")

# Output files
VLESS_FILE = CONFIGS_DIR / "vless.txt"          # raw vless:// links, one per line
PROXY_FILE = CONFIGS_DIR / "telegram_proxy.txt" # https://t.me/proxy? links
SUB_FILE   = CONFIGS_DIR / "subscription.txt"   # base64-encoded subscription for v2rayN


def load_last_id() -> int:
    try:
        return int(STATE_FILE.read_text().strip()) if STATE_FILE.exists() else 0
    except ValueError:
        return 0


def save_last_id(msg_id: int):
    STATE_FILE.write_text(str(msg_id))


async def fetch_new_links(client: TelegramClient) -> dict:
    """Fetch messages and return new vless + proxy links."""
    last_id = load_last_id()
    log.info("Fetching messages from '%s' (after id=%d)", CHANNEL, last_id)

    raw_vless: list[str] = []
    raw_proxy: list[str] = []
    newest_id = last_id

    async for msg in client.iter_messages(CHANNEL, limit=FETCH_LIMIT, min_id=last_id):
        if not isinstance(msg, Message) or not msg.text:
            continue

        found = extract_configs(msg.text)
        raw_vless.extend(found["vless"])
        raw_proxy.extend(found["proxy"])

        if msg.id > newest_id:
            newest_id = msg.id

    if newest_id > last_id:
        save_last_id(newest_id)
        log.info("Last message id updated → %d", newest_id)

    return {
        "vless": deduplicate_configs(raw_vless),
        "proxy": deduplicate_configs(raw_proxy),
    }


def merge_with_existing(path: Path, new_items: list[str]) -> list[str]:
    """Load existing file, merge with new items, deduplicate."""
    existing = []
    if path.exists():
        existing = [l.strip() for l in path.read_text().splitlines() if l.strip()]
    return deduplicate_configs(existing + new_items)


def write_and_upload(
    uploader: GitHubUploader,
    path: Path,
    content: str,
    commit_msg: str,
    label: str,
):
    path.write_text(content)
    uploader.upload_file(path, str(path), commit_msg)
    log.info("Pushed %s → %s", label, path)


async def run_once(client: TelegramClient, uploader: GitHubUploader):
    new = await fetch_new_links(client)

    total = len(new["vless"]) + len(new["proxy"])
    if total == 0:
        log.info("No new links found.")
        return

    log.info("New links — vless: %d  |  proxy: %d", len(new["vless"]), len(new["proxy"]))

    CONFIGS_DIR.mkdir(exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    commit_msg = f"update configs [{ts}] (+{len(new['vless'])} vless, +{len(new['proxy'])} proxy)"

    # ── vless.txt ─────────────────────────────────────────────────────────────
    if new["vless"]:
        all_vless = merge_with_existing(VLESS_FILE, new["vless"])
        all_vless = trim_to_limit(all_vless)   # keep newest ≤ VLESS_MAX entries
        log.info("vless.txt will hold %d/%d configs (cap=%d)", len(all_vless), len(all_vless), VLESS_MAX)
        write_and_upload(uploader, VLESS_FILE, "\n".join(all_vless) + "\n", commit_msg, "vless")

        # ── subscription.txt (base64) ─────────────────────────────────────────
        # v2rayN reads this URL directly as a subscription — each line is a config,
        # the whole file is base64-encoded.
        sub_content = build_subscription(all_vless)
        write_and_upload(uploader, SUB_FILE, sub_content, commit_msg, "subscription")

        log.info(
            "Subscription file updated (%d configs). "
            "Use the raw GitHub URL in v2rayN → Servers → Add subscription.",
            len(all_vless),
        )

    # ── telegram_proxy.txt ────────────────────────────────────────────────────
    if new["proxy"]:
        all_proxy = merge_with_existing(PROXY_FILE, new["proxy"])
        write_and_upload(uploader, PROXY_FILE, "\n".join(all_proxy) + "\n", commit_msg, "proxy")

    # Save state file to repo so CI runs resume correctly
    uploader.upload_file(STATE_FILE, ".last_message_id", commit_msg)
    log.info("Done.")


async def main():
    log.info("Starting V2Ray Collector …")
    uploader = GitHubUploader(GITHUB_TOKEN, GITHUB_REPO)

    # Build proxy tuple from .env (PROXY_HOST / PROXY_PORT / PROXY_TYPE)
    proxy = None
    proxy_host = os.getenv("PROXY_HOST", "").strip()
    proxy_port = os.getenv("PROXY_PORT", "").strip()
    proxy_type = os.getenv("PROXY_TYPE", "socks5").strip().lower()

    if proxy_host and proxy_port:
        import socks
        _type = socks.HTTP if proxy_type == "http" else socks.SOCKS5
        proxy = (_type, proxy_host, int(proxy_port))
        log.info("Using proxy: %s %s:%s", proxy_type.upper(), proxy_host, proxy_port)
    else:
        log.warning("No proxy configured — set PROXY_HOST and PROXY_PORT in .env")

    async with TelegramClient("v2ray_session", API_ID, API_HASH, proxy=proxy) as client:
        while True:
            try:
                await run_once(client, uploader)
            except Exception as exc:
                log.exception("Run failed: %s", exc)
            log.info("Sleeping %d s …", POLL_INTERVAL)
            await asyncio.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    asyncio.run(main())
