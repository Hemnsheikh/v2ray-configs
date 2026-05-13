# V2Ray Config Collector Bot

Automatically scrapes v2ray/xray proxy configs from a **public or private Telegram channel** (no admin rights needed) and pushes them to a GitHub repository — every hour, hands-free.

## Supported protocols

`vmess` · `vless` · `trojan` · `ss` · `ssr` · `hysteria` · `hysteria2` · `tuic` · `wireguard` · `naive`

---

## Quick Start (local machine)

### 1. Clone / copy this project

```bash
git clone https://github.com/YOU/v2ray-configs
cd v2ray-configs
pip install -r requirements.txt
```

### 2. Get Telegram API credentials

1. Go to <https://my.telegram.org/apps>
2. Log in with your phone number
3. Create a new application → copy **App api_id** and **App api_hash**

### 3. Create a GitHub Personal Access Token

1. Go to <https://github.com/settings/tokens> → **Generate new token (classic)**
2. Enable the **`repo`** scope
3. Copy the token

### 4. Configure environment

```bash
cp .env.example .env
# Edit .env and fill in all values
```

| Variable | Description |
|---|---|
| `TELEGRAM_API_ID` | From my.telegram.org |
| `TELEGRAM_API_HASH` | From my.telegram.org |
| `TELEGRAM_CHANNEL` | `@channelname` or numeric ID |
| `GITHUB_TOKEN` | Your PAT |
| `GITHUB_REPO` | `owner/repo` |
| `FETCH_LIMIT` | Messages per run (default 200) |
| `POLL_INTERVAL_SEC` | Seconds between runs (default 3600) |

### 5. First-time login (creates session file)

```bash
python bot.py
# Telegram will ask for your phone number + OTP the FIRST time only.
# A `v2ray_session.session` file is saved – keep it safe.
```

After login the bot runs in an infinite loop, polling the channel every hour.

---

## Automated via GitHub Actions (recommended)

Run the collector for free on GitHub's servers — no local machine needed.

### 1. Create the target repository on GitHub

Create a new **public or private** repo (e.g. `yourusername/v2ray-configs`).

### 2. Copy project files into the repo

Push all files from this folder into that repo.

### 3. First-time Telegram login

Run locally once to generate `v2ray_session.session`:

```bash
python bot_ci.py   # logs in, runs one cycle, exits
```

Then encode the session file:

```bash
base64 v2ray_session.session   # copy the output
```

### 4. Add GitHub Secrets

In your repo → **Settings → Secrets and variables → Actions → New repository secret**:

| Secret name | Value |
|---|---|
| `TELEGRAM_API_ID` | Your api_id |
| `TELEGRAM_API_HASH` | Your api_hash |
| `TELEGRAM_CHANNEL` | `@channelname` |
| `GH_PAT` | GitHub PAT with repo scope |
| `TELEGRAM_SESSION_B64` | base64 output from step 3 |

### 5. Enable the workflow

The workflow file is at `.github/workflows/collect.yml`.  
Push it to GitHub — the action will run every hour automatically.  
You can also trigger it manually from the **Actions** tab.

---

## Output files

| File | Contents |
|---|---|
| `configs/vmess.txt` | All vmess:// configs |
| `configs/vless.txt` | All vless:// configs |
| `configs/trojan.txt` | All trojan:// configs |
| `configs/ss.txt` | Shadowsocks configs |
| `configs/all_configs.txt` | Every config merged & deduplicated |
| `.last_message_id` | Tracks last processed message (auto-managed) |

---

## Notes

- The bot **never duplicates** configs — each URI is stored exactly once.
- Only messages **newer** than the last run are processed.
- `bot.py` runs forever (local/server use). `bot_ci.py` runs once and exits (CI use).
- You do **not** need to be an admin of the channel.
