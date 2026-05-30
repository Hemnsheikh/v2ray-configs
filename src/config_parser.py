"""
config_parser.py – extract vless:// and https://t.me/proxy? links from text.
"""

import re
import base64
from urllib.parse import urlparse, parse_qs
from typing import List, Dict, Optional, Tuple

# ── Patterns ──────────────────────────────────────────────────────────────────

# vless://... — everything until whitespace or newline
_VLESS_RE = re.compile(r"vless://[^\s\r\n]+", re.IGNORECASE)

# https://t.me/proxy?... — Telegram MTProto proxy links
_PROXY_RE = re.compile(r"https://t\.me/proxy\?[^\s\r\n]+", re.IGNORECASE)

# Maximum number of vless configs kept in vless.txt at any time
VLESS_MAX = 200


def _normalize(uri: str) -> str:
    """Strip trailing punctuation that may have been captured."""
    return uri.rstrip(".,;\"')")


def _host_port(vless_uri: str) -> Optional[Tuple[str, str]]:
    """
    Extract (host, port) from a vless:// URI.

    vless://UUID@HOST:PORT?params#name
    Returns None if the URI cannot be parsed.
    """
    try:
        parsed = urlparse(vless_uri)
        host = parsed.hostname  # lowercased automatically
        port = str(parsed.port) if parsed.port else ""
        if host and port:
            return (host, port)
    except Exception:
        pass
    return None


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
    """
    Remove duplicates while preserving insertion order.

    For vless:// URIs two levels of deduplication are applied:
      1. Exact URI match (as before).
      2. host:port match — if a config with the same host AND port already
         exists in the list, the new one is skipped.

    Non-vless entries (proxy links, etc.) are still deduplicated by exact match.
    """
    seen_exact: set = set()
    seen_hostport: set = set()
    out: List[str] = []

    for c in configs:
        key = c.strip()
        if not key:
            continue

        # Exact duplicate — always skip
        if key in seen_exact:
            continue

        # For vless URIs also check host:port
        if key.lower().startswith("vless://"):
            hp = _host_port(key)
            if hp is not None:
                if hp in seen_hostport:
                    continue          # same host:port already present
                seen_hostport.add(hp)

        seen_exact.add(key)
        out.append(key)

    return out


def trim_to_limit(configs: List[str], limit: int = VLESS_MAX) -> List[str]:
    """
    Keep only the *last* `limit` configs (newest entries, assuming the list
    is ordered oldest-first, newest-last).  Logs how many were dropped.
    """
    if len(configs) <= limit:
        return configs
    dropped = len(configs) - limit
    # Keep the tail (most recently added)
    return configs[dropped:]


def build_subscription(vless_configs: List[str]) -> str:
    """
    Encode a list of vless:// configs as a base64 subscription string.
    v2rayN / v2rayNG expect each config on its own line, then base64-encoded.
    """
    joined  = "\n".join(vless_configs)
    encoded = base64.b64encode(joined.encode("utf-8")).decode("utf-8")
    return encoded
