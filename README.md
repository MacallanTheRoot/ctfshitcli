<div align="center">

```
   ██████╗███████╗██╗       CSL-CtfShitCli
  ██╔════╝██╔════╝██║       CTFd Swiss Army Knife  v2.0
  ██║     ███████╗██║
  ██║     ╚════██║██║       dev by macallantheroot
  ╚██████╗███████║███████╗
   ╚═════╝╚══════╝╚══════╝
```

**CSL-CtfShitCli** — a definitive, high-performance CTF workspace and API management CLI.  
Built for speed. Built for the terminal. Built by **[macallantheroot](https://github.com/MacallanTheRoot)**.

[![Python](https://img.shields.io/badge/Python-3.9%2B-blue?logo=python&logoColor=white)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)
[![CTFd](https://img.shields.io/badge/CTFd-API%20v1-purple)](https://docs.ctfd.io)
[![rich](https://img.shields.io/badge/UI-rich-cyan)](https://github.com/Textualize/rich)
[![click](https://img.shields.io/badge/CLI-click-orange)](https://click.palletsprojects.com)

</div>

---

## ✨ Features

### 🗂️ Workspace Management

| Command | What it does |
|---|---|
| `ctf init <url>` | Auto-creates a workspace folder (derived from `--name`), writes config, flag log, notes dir |
| `ctf add <cat/name>` | Scaffold a challenge dir with `README.md`, `solve.py`, `.challenge.json` |

### 🌐 CTFd API Integration

| Command | What it does |
|---|---|
| `ctf list` | List all challenges grouped by category with solve status & points |
| `ctf pull` | Download file attachments for one challenge (auto-detects from cwd) |
| `ctf pull --all` | **Full workspace sync** — scaffold every challenge + download all files |
| `ctf submit <flag>` | Submit a flag — auto-detects challenge ID from cwd |
| `ctf bulk <csv>` | Bulk-submit flags from a CSV file with jitter rate-limiting |
| `ctf track` | Real-time scoreboard polling with change alerts |
| `ctf config` | Display and validate current configuration |
| `ctf categories` | List challenge categories with solve statistics |

---

## ⚡ Quick Start

### 1. Install

```bash
git clone https://github.com/MacallanTheRoot/CSL-CtfShitCli
cd CSL-CtfShitCli/ctfshit
pip install -r requirements.txt
```

### 2. Initialize a workspace

```bash
# Folder name is auto-derived from --name: "picoctf-2025/"
ctf init https://ctf.example.com \
  --token ctfd_your_token_here \
  --name "PicoCTF 2025"

# The CLI tells you what to do next:
#   Next: cd picoctf-2025

cd picoctf-2025
```

> **No `--name`?** Defaults to `ctf-workspace/`.  
> **Want a custom path?** Use `--path ./mydir`.

### 3. One-shot full sync

```bash
# Inside the workspace — scaffolds every challenge + downloads all files
ctf pull --all
```

This single command:
1. Fetches the full challenge list from CTFd (cache bypassed)
2. Creates `<category>/<challenge>/` directories with `README.md` + `solve.py`
3. Downloads every file attachment into the matching directory
4. Shows a live progress bar and a summary panel at the end
5. Logs any per-challenge errors in red and keeps going — **never crashes the whole loop**

### 4. Work a challenge manually

```bash
# Browse what's available
ctf list
ctf list --category web

# Add and enter a specific challenge
ctf add web/easy-sqli --id 12 --points 300
cd web/easy-sqli

# Download its files
ctf pull

# Solve it, then submit
ctf submit 'flag{blind_sqli_union_ftw}'
```

### 5. Track the scoreboard

```bash
# In a separate terminal
ctf track
ctf track --teams "MyTeam" "Rivals" --limit 20
```

---

## 🔧 Command Reference

### `ctf init <CTF_URL>`

Initialize a CTF workspace directory.

```
Options:
  -t, --token TEXT      CTFd API token (prompted if omitted)
  -n, --name  TEXT      CTF event name — also used to name the workspace folder
  -f, --force           Overwrite an existing workspace config
  -p, --path  DIR       Custom directory (default: auto-derived from --name)
```

**Folder name logic:**

| Scenario | Resulting folder |
|---|---|
| `--name "PicoCTF 2025"` | `./picoctf-2025/` |
| `--name "HackTheBox CTF!"` | `./hackthebox-ctf/` |
| *(no `--name`)* | `./ctf-workspace/` |
| `--path ./custom` | `./custom/` |

**Created files:**

```
<workspace>/
├── .ctf_config.json   ← stores URL, token, all settings
├── flags.csv          ← flag log (challenge_id, flag, category, name)
└── notes/             ← free-form notes directory
```

---

### `ctf add <category>/<name>`

Scaffold a challenge directory with templates.

```bash
ctf add web/easy-sqli
ctf add crypto/rsa-basics --id 12 --points 300 --desc "Break the RSA"
```

Creates inside the workspace:

```
web/easy-sqli/
├── README.md         ← Description / Enumeration / Exploitation / Flag sections
├── solve.py          ← Exploit script skeleton with argparse + solve() function
└── .challenge.json   ← {"id": 12, "category": "web", "points": 300, "solved": false}
```

OSINT/stego categories generate `notes.txt` instead of `solve.py`.

---

### `ctf pull [--all]`

Download challenge file attachments.

```
Options:
  -i, --id INTEGER    Challenge ID (auto-detected from .challenge.json if omitted)
  -o, --out DIR       Output directory (default: cwd — ignored with --all)
  -f, --overwrite     Re-download files that already exist
  -a, --all           Full workspace sync: scaffold + download every challenge
```

**Single mode** — run inside a challenge directory:

```bash
cd web/easy-sqli
ctf pull            # auto-detects #12 from .challenge.json
ctf pull --id 42    # explicit ID
```

**Bulk sync mode** — run from workspace root:

```bash
ctf pull --all                  # scaffold + download everything
ctf pull --all --overwrite      # force re-download of existing files
```

`--all` progress output:

```
⚡ Syncing 47 challenges → /home/user/picoctf-2025

⠋ web/easy-sqli  ████████████░░░░░░░░  12/47
  ⚠ #31 file download: has no attached files.   ← non-fatal, continues

╭──────────── ⚡  Pull All — Complete ─────────────╮
│  Challenges total:    47                         │
│  ✔ Scaffolded:        47                         │
│  📥 Files downloaded: 23 challenge(s) had files  │
│  ✗ Errors:            0                          │
╰──────────────────────────────────────────────────╯
```

---

### `ctf submit <flag>`

Submit a flag for a challenge.

```bash
cd web/easy-sqli
ctf submit 'flag{xss_pwned}'        # auto-detects ID from .challenge.json
ctf submit 'flag{...}' --id 42      # explicit ID from anywhere
```

On correct submission, `.challenge.json` is automatically updated:  
`"solved": true, "flag": "flag{xss_pwned}"`

---

### `ctf list`

Browse all challenges grouped by category.

```bash
ctf list                  # grouped by category (default)
ctf list --flat           # flat table
ctf list --category web   # filter by category
ctf list --no-cache       # bypass 5-minute cache
```

---

### `ctf bulk <csv>`

Bulk-submit flags from a CSV file with jitter delays.

```csv
challenge_id,flag
1,flag{first_challenge}
5,flag{websecurity_100}
```

```bash
ctf bulk flags.csv --details
```

---

### `ctf track`

Real-time scoreboard polling. Press **Ctrl+C** to stop.

```bash
ctf track
ctf track --teams "MyTeam" "Rivals" --limit 20
```

---

### `ctf config`

Display and validate the current configuration (token masked).

```bash
ctf config
```

---

## ⚙️ Configuration

CSL-CtfShitCli uses a **priority cascade** — walks up the directory tree (like git) to find the nearest `.ctf_config.json`, then falls back to `.env`.

### `.ctf_config.json` (workspace config — created by `ctf init`)

```json
{
  "ctf_name": "PicoCTF 2025",
  "ctf_url": "https://ctf.example.com",
  "ctf_token": "ctfd_your_token_here",
  "api_timeout": 15,
  "max_retries": 3,
  "poll_interval": 30,
  "log_level": "INFO"
}
```

> ⚠️ **Never commit this file** — it contains your API token. It's in `.gitignore` by default.

### `.env` (legacy fallback)

```bash
cp .env.example .env
```

```env
CTF_URL=https://ctf.example.com
CTF_TOKEN=ctfd_your_api_token
POLL_INTERVAL=30
API_TIMEOUT=15
MAX_RETRIES=3
LOG_LEVEL=INFO
```

Get your token: `CTFd → Settings → API Token`

---

## 🏗️ Project Structure

```
ctfshit/
├── main.py                     ← CLI entry point (click + all commands)
├── requirements.txt
├── .env.example                ← Legacy config template
├── .ctf_config.json.example    ← Workspace config template
├── .gitignore
├── .gitattributes
├── LICENSE
├── README.md
└── src/
    ├── __init__.py             ← v2.0.0
    ├── api_client.py           ← Async HTTP client (aiohttp, retry, backoff)
    ├── challenge_scraper.py    ← Challenge fetch + 5-min cache
    ├── config_manager.py       ← JSON + .env config with auto-detection
    ├── file_downloader.py      ← Streaming downloader (progress / silent modes)
    ├── flag_submitter.py       ← Single + bulk flag submission
    ├── scoreboard_tracker.py   ← Async background scoreboard polling
    ├── ui_renderer.py          ← All rich terminal output
    └── workspace_manager.py    ← Workspace init + challenge scaffolding
```

---

## 🔌 Resilience & Rate-Limit Handling

| Feature | Detail |
|---|---|
| **Exponential backoff** | `base × 2^attempt` ± 20% jitter, capped at 60s |
| **HTTP 429 handling** | Auto-detects rate limiting, backs off and retries |
| **5xx retry** | Server errors retry with backoff (401/404 are not retried) |
| **Timeout protection** | Configurable per-request timeout (default 15s) |
| **Connection pooling** | aiohttp TCPConnector, 20 max connections |
| **Jitter on bulk submit** | 0.5–3s random delay between flag submissions |
| **`pull --all` resilience** | Per-challenge try/except — one bad challenge never kills the loop |

---

## 📦 Dependencies

```
aiohttp>=3.9.0        # Async HTTP client
python-dotenv>=1.0.0  # .env loading
rich>=13.7.0          # Terminal UI
pydantic>=2.0.0       # Config validation
click>=8.1.0          # CLI framework
requests>=2.31.0      # HTTP utility
pytest>=7.4.0
pytest-asyncio>=0.21.0
```

---

## 🛠️ Troubleshooting

| Problem | Fix |
|---|---|
| `No CTF workspace found` | Run `ctf init <url>` first, or `cd` into your workspace |
| `Challenge ID Required` | Run `ctf add` first, or provide `--id N` |
| `AuthenticationError` | Check your token in `.ctf_config.json` or `.env` |
| `HTTP 429 / rate limited` | Built-in backoff handles this automatically |
| `Network timeout` | Increase `api_timeout` in config; check CTFd status |
| `Already solved` panel | Yellow — CTFd confirms it's already done |
| `pull --all` stops on one challenge | It doesn't — errors are logged and the loop continues |

---

## 🔐 Security Notes

- API token stored in `.ctf_config.json` or `.env` — **both are git-ignored by default**
- Token is masked in all console output: `ctfd_xxxxx...xxxx`
- `ctf_client.log` never writes tokens in plain text
- Recommended permissions: `chmod 600 .ctf_config.json`

---

## 📚 CTFd API Reference

| Endpoint | Used for |
|---|---|
| `GET /api/v1/challenges` | List all challenges |
| `GET /api/v1/challenges/{id}` | Challenge detail + file list |
| `POST /api/v1/challenges/attempt` | Submit flag |
| `GET /api/v1/scoreboard` | Leaderboard |
| `GET /api/v1/users/me` | Token validation |

---

## 🚀 Programmatic API

```python
import asyncio
from src.config_manager import resolve_config
from src.api_client import CTFdAPIClient
from src.challenge_scraper import ChallengeScraper
from src.flag_submitter import FlagSubmitter

async def example():
    config = resolve_config()
    async with CTFdAPIClient(config.ctf_url, config.api_token) as api:
        challenges = await ChallengeScraper(api).fetch_challenges()
        result = await FlagSubmitter(api).submit_single_flag(42, "flag{test}")
        print(result)

asyncio.run(example())
```

---

## 📄 License

MIT — see [LICENSE](LICENSE).

---

<div align="center">

**Built with ❤️ for the CTF community**  
by **[macallantheroot](https://github.com/MacallanTheRoot)**

*Go hack something.*

</div>
