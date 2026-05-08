"""
Submission History Module (v3.0)
Logs and retrieves local flag submission attempts.

Design rationale:
  - CTFd /api/v1/submissions requires admin token → unusable for normal users.
  - Instead, every 'ctf submit' and 'ctf watch' call writes to a local
    attempts.json file inside the challenge directory.
  - 'ctf submissions --id <id>' reads this file and renders a history table.
  - File location: <challenge_dir>/attempts.json
  - Format: a JSON array of attempt objects (appended on each submission).

Schema per attempt:
  {
    "challenge_id":   42,
    "challenge_name": "Easy SQLi",
    "flag":           "flag{...}",
    "result":         "correct" | "incorrect" | "already_solved" | "error",
    "message":        "CTFd response message",
    "source":         "submit" | "watch",
    "submitted_at":   "2025-05-08T14:00:00+03:00"
  }
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from rich.table import Table

from src.ui_renderer import console, render_info

logger = logging.getLogger(__name__)

ATTEMPTS_FILENAME = "attempts.json"


# ── Write ─────────────────────────────────────────────────────────────────────

def log_attempt(
    challenge_dir: Path,
    challenge_id: int,
    challenge_name: str,
    flag: str,
    result: str,
    message: str,
    source: str = "submit",
) -> None:
    """
    Append a submission attempt to <challenge_dir>/attempts.json.

    Creates the file if it doesn't exist.

    Args:
        challenge_dir:   Challenge directory path (contains .challenge.json).
        challenge_id:    CTFd challenge ID.
        challenge_name:  Human-readable challenge name.
        flag:            Flag string that was submitted.
        result:          CTFd status string: "correct", "incorrect",
                         "already_solved", or "error".
        message:         Human-readable result message from CTFd.
        source:          "submit" (manual) or "watch" (auto-daemon).
    """
    attempts_path = Path(challenge_dir) / ATTEMPTS_FILENAME

    # Load existing attempts (or start fresh)
    attempts: List[Dict[str, Any]] = []
    if attempts_path.exists():
        try:
            with open(attempts_path, "r", encoding="utf-8") as f:
                attempts = json.load(f)
            if not isinstance(attempts, list):
                logger.warning(f"Unexpected format in {attempts_path}, resetting")
                attempts = []
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Could not read {attempts_path}: {e} — starting fresh")
            attempts = []

    # Build new entry
    entry: Dict[str, Any] = {
        "challenge_id":   challenge_id,
        "challenge_name": challenge_name,
        "flag":           flag,
        "result":         result,
        "message":        message,
        "source":         source,
        "submitted_at":   datetime.now(timezone.utc).astimezone().isoformat(),
    }
    attempts.append(entry)

    try:
        with open(attempts_path, "w", encoding="utf-8") as f:
            json.dump(attempts, f, indent=2, ensure_ascii=False)
        logger.debug(
            f"Logged attempt for #{challenge_id} ({result}) → {attempts_path}"
        )
    except OSError as e:
        logger.error(f"Could not write {attempts_path}: {e}")


# ── Read ──────────────────────────────────────────────────────────────────────

def load_attempts(challenge_dir: Path) -> List[Dict[str, Any]]:
    """
    Load all submission attempts from <challenge_dir>/attempts.json.

    Args:
        challenge_dir: Challenge directory path.

    Returns:
        List of attempt dicts (oldest first). Empty list if no history.
    """
    attempts_path = Path(challenge_dir) / ATTEMPTS_FILENAME
    if not attempts_path.exists():
        return []

    try:
        with open(attempts_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return data
        logger.warning(f"Unexpected format in {attempts_path}")
        return []
    except (json.JSONDecodeError, OSError) as e:
        logger.error(f"Could not read {attempts_path}: {e}")
        return []


def find_attempts_for_challenge(
    workspace_root: Path, challenge_id: int
) -> Optional[tuple[Path, List[Dict[str, Any]]]]:
    """
    Search the workspace tree for the attempts.json belonging to a challenge.

    Walks all subdirectories looking for .challenge.json files whose 'id'
    matches challenge_id, then reads the sibling attempts.json.

    Args:
        workspace_root: CTF workspace root path.
        challenge_id:   Challenge ID to look up.

    Returns:
        (challenge_dir, attempts_list) tuple, or None if not found.
    """
    workspace_root = Path(workspace_root)
    for meta_file in workspace_root.rglob(".challenge.json"):
        try:
            with open(meta_file, "r", encoding="utf-8") as f:
                meta = json.load(f)
            if int(meta.get("id", -1)) == challenge_id:
                challenge_dir = meta_file.parent
                attempts      = load_attempts(challenge_dir)
                return challenge_dir, attempts
        except (json.JSONDecodeError, OSError, ValueError):
            continue
    return None


# ── Render ────────────────────────────────────────────────────────────────────

_RESULT_STYLE = {
    "correct":       "[bold green]✔ Correct[/bold green]",
    "already_solved":"[bold yellow]★ Already Solved[/bold yellow]",
    "incorrect":     "[bold red]✗ Incorrect[/bold red]",
    "error":         "[dim red]⚠ Error[/dim red]",
}

_SOURCE_STYLE = {
    "submit": "[cyan]manual[/cyan]",
    "watch":  "[magenta]auto[/magenta]",
}


def render_submission_history(
    attempts: List[Dict[str, Any]],
    challenge_id: int,
    challenge_name: str = "",
) -> None:
    """
    Render a challenge's submission history as a Rich table.

    Args:
        attempts:       List of attempt dicts from load_attempts().
        challenge_id:   Challenge ID (for table title).
        challenge_name: Optional human-readable name for the title.
    """
    if not attempts:
        render_info(
            "No Submission History",
            f"No local attempts found for challenge #{challenge_id}.\n"
            "[dim]Submissions are logged automatically when you run "
            "'ctf submit' or 'ctf watch'.[/dim]",
        )
        return

    title_name = f" — {challenge_name}" if challenge_name else ""
    table = Table(
        title=f"[bold cyan]📋 Submission History  #{challenge_id}{title_name}[/bold cyan]",
        border_style="bright_black",
        header_style="bold cyan",
        show_lines=False,
        expand=False,
    )
    table.add_column("#",          style="dim",      width=4,  justify="right")
    table.add_column("Result",     width=18)
    table.add_column("Flag",       style="white",    width=35, no_wrap=True)
    table.add_column("Source",     width=10)
    table.add_column("Submitted",  style="dim",      width=22)
    table.add_column("Message",    style="dim white", width=30, no_wrap=False)

    for idx, attempt in enumerate(reversed(attempts), start=1):
        result     = attempt.get("result", "")
        flag_text  = attempt.get("flag", "")
        source     = attempt.get("source", "submit")
        submitted  = attempt.get("submitted_at", "")[:19].replace("T", " ")
        message    = attempt.get("message", "")

        # Truncate long flags for display
        flag_display = (
            flag_text[:32] + "…" if len(flag_text) > 32 else flag_text
        )

        table.add_row(
            str(idx),
            _RESULT_STYLE.get(result, f"[dim]{result}[/dim]"),
            flag_display,
            _SOURCE_STYLE.get(source, source),
            submitted,
            message[:60],
        )

    console.print(table)
    console.print(
        f"  [dim]Total attempts: {len(attempts)} · "
        f"Local log only (no admin API required)[/dim]\n"
    )
