"""
Workspace Manager Module
Handles local CTF workspace scaffolding: init, add challenge directories,
README/solve.py templates, and challenge metadata (.challenge.json).

Design:
  - find_workspace_root() walks up the directory tree (like git) to locate
    the nearest .ctf_config.json file.
  - All paths are resolved relative to the workspace root or cwd as appropriate.
"""

import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ─── Constants ────────────────────────────────────────────────────────────────

WORKSPACE_CONFIG_FILENAME = ".ctf_config.json"
CHALLENGE_META_FILENAME = ".challenge.json"
DEFAULT_NOTES_DIR = "notes"
DEFAULT_FLAGS_CSV = "flags.csv"
FLAGS_CSV_HEADER = "challenge_id,flag,category,name\n"


# ─── Templates ────────────────────────────────────────────────────────────────

def _readme_template(category: str, name: str) -> str:
    """Generate a README.md template for a challenge directory."""
    title = name.replace("-", " ").replace("_", " ").title()
    return f"""# {title}

> **Category:** {category.upper()}
> **Status:** 🔴 Unsolved
> **Points:** TBD
> **Author:** TBD

---

## 📋 Challenge Description

<!-- Paste the challenge description here -->

---

## 🔍 Enumeration

<!-- Document your recon steps, tools used, findings -->

```
$ 
```

---

## 💥 Exploitation

<!-- Step-by-step exploitation notes -->

### Approach 1

### Approach 2

---

## 🏁 Flag

```
flag{{}}
```

---

## 📎 Files / Resources

<!-- List attached files, URLs, service addresses -->

---

## 🧠 Notes & Lessons Learned

<!-- What did you learn? Any rabbit holes? -->
"""


def _solve_py_template(category: str, name: str) -> str:
    """Generate a solve.py template for a challenge directory."""
    var_name = re.sub(r"[^a-zA-Z0-9_]", "_", name).lower()
    return f'''#!/usr/bin/env python3
"""
CTF Challenge: {name}
Category: {category}
Date: {datetime.now().strftime("%Y-%m-%d")}

Usage:
    python solve.py
    python solve.py --host <host> --port <port>
"""

import argparse
import sys
from pathlib import Path

# ─── Uncomment as needed ───────────────────────────────────────────────────
# from pwn import *
# import requests
# from Crypto.Util.number import *
# from z3 import *

# ─── Configuration ─────────────────────────────────────────────────────────

TARGET_HOST = "localhost"
TARGET_PORT = 1337


def solve(host: str = TARGET_HOST, port: int = TARGET_PORT) -> str:
    """
    Main solve function.
    Returns the flag string on success, or raises an exception.
    """
    flag = ""

    # ── Your exploit here ─────────────────────────────────────────────────

    # TODO: Implement solution

    # ─────────────────────────────────────────────────────────────────────

    return flag


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Solve: {name} [{category}]"
    )
    parser.add_argument("--host", default=TARGET_HOST)
    parser.add_argument("--port", type=int, default=TARGET_PORT)
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    try:
        flag = solve(host=args.host, port=args.port)
        if flag:
            print(f"[+] Flag: {{flag}}")
            return 0
        else:
            print("[-] No flag obtained.", file=sys.stderr)
            return 1
    except KeyboardInterrupt:
        print("\\n[!] Aborted by user", file=sys.stderr)
        return 130
    except Exception as e:
        print(f"[!] Error: {{e}}", file=sys.stderr)
        if args.debug:
            raise
        return 1


if __name__ == "__main__":
    sys.exit(main())
'''


def _notes_txt_template(category: str, name: str) -> str:
    """Generate a quick notes.txt for categories that don't suit Python."""
    return f"""# {name.upper()} [{category.upper()}]
# Created: {datetime.now().strftime("%Y-%m-%d %H:%M")}
# Status: Unsolved

## Quick Notes

## Commands Run

## Resources

"""


# ─── Workspace Root Detection ─────────────────────────────────────────────────

def find_workspace_root(start: Optional[Path] = None) -> Optional[Path]:
    """
    Walk up the directory tree from `start` (default: cwd) to find the nearest
    .ctf_config.json file.

    Returns:
        Path to the directory containing .ctf_config.json, or None if not found.
    """
    current = Path(start or Path.cwd()).resolve()
    while True:
        candidate = current / WORKSPACE_CONFIG_FILENAME
        if candidate.is_file():
            logger.debug(f"Found workspace root: {current}")
            return current
        parent = current.parent
        if parent == current:
            # Reached filesystem root
            logger.debug("No workspace root found (no .ctf_config.json in tree)")
            return None
        current = parent


def load_workspace_config(workspace_root: Optional[Path] = None) -> dict:
    """
    Load .ctf_config.json from the workspace root.

    Args:
        workspace_root: Explicit path. If None, auto-detects via find_workspace_root().

    Returns:
        Parsed config dictionary.

    Raises:
        FileNotFoundError: If workspace root or config file not found.
        ValueError: If config JSON is malformed.
    """
    root = workspace_root or find_workspace_root()
    if root is None:
        raise FileNotFoundError(
            "No CTF workspace found. Run 'ctf init' first, or provide --env."
        )

    config_path = root / WORKSPACE_CONFIG_FILENAME
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        logger.debug(f"Loaded workspace config from {config_path}")
        return data
    except json.JSONDecodeError as e:
        raise ValueError(f"Malformed {WORKSPACE_CONFIG_FILENAME}: {e}")


def detect_challenge_context(start: Optional[Path] = None) -> Optional[dict]:
    """
    Check whether the current directory (or `start`) is a challenge directory
    by looking for .challenge.json.

    Returns:
        Parsed .challenge.json dict, or None if not a challenge directory.
    """
    current = Path(start or Path.cwd()).resolve()
    meta_file = current / CHALLENGE_META_FILENAME
    if meta_file.is_file():
        try:
            with open(meta_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            logger.debug(f"Detected challenge context: {data}")
            return data
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Could not read {CHALLENGE_META_FILENAME}: {e}")
    return None


# ─── Workspace Init ──────────────────────────────────────────────────────────

def init_workspace(
    path: Path,
    ctf_url: str,
    ctf_token: str,
    ctf_name: str = "",
    force: bool = False,
) -> Path:
    """
    Initialize a new CTF workspace at `path`.

    Creates:
        .ctf_config.json   — workspace config with URL and token
        flags.csv          — CSV log for discovered flags
        notes/             — directory for free-form notes

    Args:
        path:       Directory to initialize (must exist).
        ctf_url:    CTFd base URL.
        ctf_token:  API token.
        ctf_name:   Human-readable CTF event name (optional).
        force:      Overwrite existing config if present.

    Returns:
        Path to the created .ctf_config.json.

    Raises:
        FileExistsError:  If workspace already initialized and force=False.
        ValueError:       If URL is missing.
    """
    path = Path(path).resolve()
    config_file = path / WORKSPACE_CONFIG_FILENAME

    if config_file.exists() and not force:
        raise FileExistsError(
            f"Workspace already initialized at {path}.\n"
            f"Use --force to reinitialize."
        )

    if not ctf_url:
        raise ValueError("CTF URL must not be empty.")

    # Normalize URL
    ctf_url = ctf_url.rstrip("/")

    # Write config
    config_data = {
        "ctf_name": ctf_name or "My CTF",
        "ctf_url": ctf_url,
        "ctf_token": ctf_token,
        "api_timeout": 15,
        "max_retries": 3,
        "poll_interval": 30,
        "log_level": "INFO",
        "created_at": datetime.now().isoformat(),
        "version": "2.0",
    }
    with open(config_file, "w", encoding="utf-8") as f:
        json.dump(config_data, f, indent=2)
    logger.info(f"Created workspace config: {config_file}")

    # Create flags CSV
    flags_csv = path / DEFAULT_FLAGS_CSV
    if not flags_csv.exists():
        with open(flags_csv, "w", encoding="utf-8") as f:
            f.write(FLAGS_CSV_HEADER)
        logger.info(f"Created flags.csv: {flags_csv}")

    # Create notes directory
    notes_dir = path / DEFAULT_NOTES_DIR
    notes_dir.mkdir(exist_ok=True)
    gitkeep = notes_dir / ".gitkeep"
    if not gitkeep.exists():
        gitkeep.touch()
    logger.info(f"Created notes directory: {notes_dir}")

    return config_file


# ─── Challenge Scaffolding ───────────────────────────────────────────────────

def add_challenge(
    challenge_path: str,
    challenge_id: Optional[int] = None,
    points: Optional[int] = None,
    description: str = "",
    workspace_root: Optional[Path] = None,
) -> dict:
    """
    Scaffold a challenge directory structure.

    Args:
        challenge_path: Slash-separated category/name (e.g. 'web/easy-sqli').
        challenge_id:   Optional CTFd challenge ID for metadata.
        points:         Optional point value.
        description:    Optional challenge description to pre-fill README.
        workspace_root: Workspace root. If None, auto-detected.

    Returns:
        Dict with created paths: {root, readme, solve_py, notes_txt, meta}.

    Raises:
        ValueError: If challenge_path format is invalid.
        FileNotFoundError: If workspace root not found.
    """
    # Parse and validate path
    parts = [p.strip() for p in challenge_path.strip("/").split("/") if p.strip()]
    if len(parts) < 2:
        raise ValueError(
            f"Challenge path must be 'category/name', got: '{challenge_path}'"
        )

    category = parts[0].lower()
    name = "/".join(parts[1:])  # Support nested like 'web/easy/sqli'
    name_slug = name.lower().replace(" ", "-")

    # Resolve workspace root
    root = workspace_root or find_workspace_root()
    if root is None:
        raise FileNotFoundError(
            "No CTF workspace found. Run 'ctf init' first."
        )

    # Build challenge directory path
    challenge_dir = root / category / name_slug
    challenge_dir.mkdir(parents=True, exist_ok=True)

    created = {"root": challenge_dir}

    # README.md
    readme_path = challenge_dir / "README.md"
    if not readme_path.exists():
        content = _readme_template(category, name_slug)
        if description:
            content = content.replace(
                "<!-- Paste the challenge description here -->",
                description,
            )
        with open(readme_path, "w", encoding="utf-8") as f:
            f.write(content)
        created["readme"] = readme_path
        logger.info(f"Created README.md: {readme_path}")

    # solve.py (for most categories) or notes.txt for misc/forensics
    SCRIPT_CATEGORIES = {"web", "pwn", "rev", "crypto", "misc", "blockchain"}
    NOTES_CATEGORIES = {"osint", "trivia", "stego", "steganography"}

    if category.lower() in NOTES_CATEGORIES:
        notes_path = challenge_dir / "notes.txt"
        if not notes_path.exists():
            with open(notes_path, "w", encoding="utf-8") as f:
                f.write(_notes_txt_template(category, name_slug))
            created["notes_txt"] = notes_path
            logger.info(f"Created notes.txt: {notes_path}")
    else:
        solve_path = challenge_dir / "solve.py"
        if not solve_path.exists():
            with open(solve_path, "w", encoding="utf-8") as f:
                f.write(_solve_py_template(category, name_slug))
            created["solve_py"] = solve_path
            logger.info(f"Created solve.py: {solve_path}")

    # .challenge.json metadata
    meta_path = challenge_dir / CHALLENGE_META_FILENAME
    meta_data = {
        "id": challenge_id,
        "name": name_slug,
        "category": category,
        "points": points,
        "solved": False,
        "flag": None,
        "created_at": datetime.now().isoformat(),
    }
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta_data, f, indent=2)
    created["meta"] = meta_path
    logger.info(f"Created .challenge.json: {meta_path}")

    return created


def update_challenge_meta(
    challenge_dir: Optional[Path] = None,
    **kwargs,
) -> None:
    """
    Update fields in a challenge's .challenge.json.

    Args:
        challenge_dir: Path to challenge directory. Defaults to cwd.
        **kwargs:      Fields to update (e.g. solved=True, flag='flag{...}').
    """
    cdir = Path(challenge_dir or Path.cwd()).resolve()
    meta_path = cdir / CHALLENGE_META_FILENAME
    if not meta_path.exists():
        logger.warning(f"No .challenge.json found at {cdir}")
        return

    with open(meta_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    data.update(kwargs)

    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    logger.debug(f"Updated .challenge.json: {kwargs}")
