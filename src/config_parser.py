"""
config_parser.py – extract vless:// and https://t.me/proxy? links from text.
"""

import re
import base64
from typing import List, Dict

# ── Patterns ──────────────────────────────────────────────────────────────────

# vless://... — everything until whitespace or newline
_VLESS_RE = re.compile(r"vless://[^\s\r\n]+", re.IGNORECASE)

# https://t.me/proxy?... — Telegram MTProto proxy links
_PROXY_RE = re.compile(r"https://t\.me/proxy\?[^\s\r\n]+", re.IGNORECASE)


def _normalize(uri: str) -> str:
    """Strip trailing punctuation that may have been captured."""
    return uri.rstrip(".,;\"')")


# ── Public API ────────────────────────────────────────────────────────────────

def extract_configs(text: str) -> Dict[str, List[str]]:
    """
    Parse *text* and return a dict with two keys:
        "vless"  → list of vless:// URIs
        "proxy"  → list of https://t.me/proxy? URIs
    """
    vless = [_normalize(m.group()) for m in _VLESS_RE.finditer(text)]
    proxy = [_normalize(m.group()) for m in _PROXY_RE.finditer(text)]
    return {"vless": vless, "proxy": proxy}


def deduplicate_configs(configs: List[str]) -> List[str]:
    """Remove duplicates while preserving insertion order."""
    seen: set = set()
    out: List[str] = []
    for c in configs:
        key = c.strip()
        if key and key not in seen:
            seen.add(key)
            out.append(key)
    return out


def build_subscription(vless_configs: List[str]) -> str:
    """
    Encode a list of vless:// configs as a base64 subscription string.
    v2rayN / v2rayNG expect each config on its own line, then base64-encoded.
    """
    joined  = "\n".join(vless_configs)
    encoded = base64.b64encode(joined.encode("utf-8")).decode("utf-8")
    return encoded
