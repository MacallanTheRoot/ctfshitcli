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

</div>

---

## ✨ Features

### 🗂️ Workspace Management
| Command | What it does |
|---|---|
| `ctf init <url>` | Initialize a CTF workspace — creates config, flag log, notes dir |
| `ctf add <cat/name>` | Scaffold a challenge dir with `README.md`, `solve.py`, `.challenge.json` |

### 🌐 CTFd API Integration
| Command | What it does |
|---|---|
| `ctf list` | List all challenges, grouped by category with solve status |
| `ctf pull` | Download all challenge file attachments (streaming, progress bar) |
| `ctf submit <flag>` | Submit a flag — auto-detects challenge ID from cwd |
| `ctf bulk <csv>` | Bulk-submit flags from a CSV file with jitter rate-limiting |
| `ctf track` | Real-time scoreboard polling with change alerts |
| `ctf config` | Display and validate current configuration |
| `ctf categories` | List challenge categories with solve statistics |

---

## ⚡ Quick Start

### 1. Install dependencies

```bash
git clone https://github.com/MacallanTheRoot/CSL-CtfShitCli
cd CSL-CtfShitCli/ctfshit

pip install -r requirements.txt
```

### 2. Initialize a workspace

```bash
mkdir hackthebox-2025 && cd hackthebox-2025

python main.py init https://ctf.example.com \
  --token ctfd_your_api_token_here \
  --name "HackTheBox CTF 2025"
```

This creates:
```
hackthebox-2025/
├── .ctf_config.json   ← stores URL, token, settings
├── flags.csv          ← flag log
└── notes/             ← free-form notes
```

### 3. Browse challenges

```bash
python main.py list                  # All challenges, grouped by category
python main.py list --category web   # Web challenges only
python main.py list --flat           # Flat table view
python main.py categories            # Category overview with stats
```

### 4. Add and work a challenge

```bash
# Scaffold a challenge directory
python main.py add web/easy-sqli --id 12 --points 300

# Navigate into it
cd web/easy-sqli

# Download attached files (auto-detects challenge from .challenge.json)
python main.py pull

# Solve it, then submit
python main.py submit 'flag{blind_sqli_union_ftw}'
```

### 5. Track the scoreboard

```bash
# In a separate terminal
python main.py track
python main.py track --teams "MyTeam" "Rivals" --limit 20
```

---

## 🏗️ Project Structure

```
ctfshit/
├── main.py                     ← CLI entry point (click)
├── requirements.txt            ← Python dependencies
├── .env.example                ← Configuration template
├── .env                        ← Your credentials (git-ignored)
├── .gitignore
├── .gitattributes
├── README.md
└── src/
    ├── __init__.py             ← Package init (v2.0.0)
    ├── api_client.py           ← Async HTTP client (aiohttp + retry logic)
    ├── challenge_scraper.py    ← Challenge fetching with 5-min cache
    ├── config_manager.py       ← JSON + .env config with auto-detection
    ├── file_downloader.py      ← Streaming file downloader
    ├── flag_submitter.py       ← Single + bulk flag submission
    ├── scoreboard_tracker.py   ← Async background scoreboard polling
    ├── ui_renderer.py          ← Rich terminal UI (all output)
    └── workspace_manager.py    ← Workspace init + challenge scaffolding
```

---

## ⚙️ Configuration

### Option A — Workspace Config (recommended)

Created automatically by `ctf init`. Located at `.ctf_config.json` in your workspace root:

```json
{
  "ctf_name": "HackTheBox CTF 2025",
  "ctf_url": "https://ctf.example.com",
  "ctf_token": "ctfd_your_token_here",
  "api_timeout": 15,
  "max_retries": 3,
  "poll_interval": 30,
  "log_level": "INFO"
}
```

**CSL-CtfShitCli walks up the directory tree** (like git) to find this file, so `ctf list`, `ctf submit`, etc. work from any subdirectory of your workspace.

### Option B — `.env` file (legacy / backward compatible)

```bash
cp .env.example .env
# edit .env with your credentials
```

```env
CTF_URL=https://ctf.example.com
CTF_TOKEN=ctfd_your_api_token
POLL_INTERVAL=30
API_TIMEOUT=15
MAX_RETRIES=3
LOG_LEVEL=INFO
```

Get your API token: `CTFd Platform → Settings → API Token`

---

## 📋 CSV Format for Bulk Submissions

```csv
challenge_id,flag
1,flag{first_challenge}
5,flag{websecurity_100}
12,flag{crypto_advanced}
```

```bash
python main.py bulk flags.csv --details
```

---

## 🔌 Resilience & Rate-Limit Handling

The `api_client.py` implements production-grade resilience out of the box:

| Feature | Detail |
|---|---|
| **Exponential backoff** | `base × 2^attempt` with ±20% jitter, capped at 60s |
| **HTTP 429 handling** | Auto-detects rate limiting, backs off and retries |
| **5xx retry** | Server errors retry with backoff (not 401/404) |
| **Timeout protection** | Configurable per-request timeout (default 15s) |
| **Connection pooling** | aiohttp TCP connector with 20 max connections |
| **Jitter on bulk submit** | 0.5–3s random delay between submissions |

---

## 🎨 Terminal UI

All output uses **[rich](https://github.com/Textualize/rich)** for a premium dark-theme terminal experience:

- **Category-grouped tables** — one table per category with solve progress
- **Streaming download progress** — per-file progress bar with speed + ETA
- **Submission panels** — green ✔ / red ✗ / yellow ★ (already solved)
- **Config panel** — token masked, clickable URL
- **Workspace tree** — visual directory tree on init

---

## 📦 Dependencies

```
aiohttp>=3.9.0        # Async HTTP client
python-dotenv>=1.0.0  # .env file loading
rich>=13.7.0          # Terminal UI
pydantic>=2.0.0       # Config validation
requests>=2.31.0      # HTTP (fallback/utility)
click>=8.1.0          # CLI framework
pytest>=7.4.0         # Testing
pytest-asyncio>=0.21.0
```

---

## 🛠️ Troubleshooting

| Problem | Fix |
|---|---|
| `No CTF workspace found` | Run `ctf init <url>` first, or `cd` to your workspace |
| `AuthenticationError` | Check your token in `.ctf_config.json` or `.env` |
| `Challenge ID Required` | Run `ctf add` first, or provide `--id N` |
| `HTTP 429 / rate limited` | Built-in backoff handles this automatically |
| `Network timeout` | Increase `api_timeout` in config, check CTFd status |
| `Already solved` displayed | Yellow panel indicates CTFd knows it's already done |

---

## 🔐 Security

- API token stored in `.ctf_config.json` or `.env` — **never commit these files**
- Both files are `.gitignore`d by default
- Token is masked in all console output (`ctfd_xxxxx...xxxx`)
- Logging to `ctf_client.log` never writes tokens in plain text
- Set `.ctf_config.json` permissions: `chmod 600 .ctf_config.json`

---

## 📚 CTFd API Reference

| Endpoint | Usage |
|---|---|
| `GET /api/v1/challenges` | List challenges |
| `GET /api/v1/challenges/{id}` | Challenge detail + files |
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
        scraper   = ChallengeScraper(api)
        challenges = await scraper.fetch_challenges()

        submitter = FlagSubmitter(api)
        result    = await submitter.submit_single_flag(42, "flag{test}")
        print(result)

asyncio.run(example())
```

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

---

<div align="center">

**Built with ❤️ for the CTF community**  
by **[macallantheroot](https://github.com/MacallanTheRoot)**

*Go hack something.*

</div>
