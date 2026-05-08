"""
Watch Daemon Module (v3.0)
Monitors directory trees for 'flag.txt' changes and auto-submits found flags.

Design:
  - Uses watchdog for filesystem events (runs in its own thread).
  - Bridges the synchronous watchdog callbacks to the main asyncio event loop
    using asyncio.run_coroutine_threadsafe().
  - Reads flag.txt, extracts flags via regex, and calls CTFd API.
  - Logs attempts locally (submission_history) and sends Discord webhooks.
  - Can watch a single challenge directory or the entire workspace.
"""

import asyncio
import json
import logging
import re
import time
from pathlib import Path
from typing import Optional

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from src.api_client import APIError, CTFdAPIClient
from src.config_manager import ConfigManager
from src.discord_notifier import send_flag_notification
from src.submission_history import log_attempt
from src.ui_renderer import console

logger = logging.getLogger(__name__)

# Default regex to match flags (e.g. flag{...} or CTF{...})
DEFAULT_PATTERN = r"(?:flag|CTF)\{.*?\}"


class FlagFileHandler(FileSystemEventHandler):
    """
    Watchdog event handler for flag.txt modifications.
    
    When a change is detected, it parses the file, extracts the flag,
    and dispatches an asynchronous task to the main event loop to submit it.
    """

    def __init__(
        self,
        loop: asyncio.AbstractEventLoop,
        api_client: CTFdAPIClient,
        config: ConfigManager,
        pattern: str = DEFAULT_PATTERN,
    ):
        super().__init__()
        self.loop = loop
        self.api_client = api_client
        self.config = config
        self.pattern = re.compile(pattern, re.IGNORECASE)
        # Prevent rapid double-submissions for the same file modification
        self._processed_flags: set = set()

    def on_modified(self, event: FileSystemEvent) -> None:
        self._process_event(event)

    def on_created(self, event: FileSystemEvent) -> None:
        self._process_event(event)

    def _process_event(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return

        path = Path(event.src_path)
        if path.name.lower() != "flag.txt":
            return

        # Slight delay to ensure the writing process has flushed to disk
        time.sleep(0.1)

        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
        except OSError as e:
            logger.warning(f"WatchDaemon: Could not read {path}: {e}")
            return

        matches = self.pattern.findall(content)
        for flag in matches:
            if flag in self._processed_flags:
                continue  # Already submitted this exact flag recently

            self._processed_flags.add(flag)
            
            # Dispatch to async loop
            asyncio.run_coroutine_threadsafe(
                self._submit_async(path, flag), self.loop
            )

    async def _submit_async(self, flag_path: Path, flag: str) -> None:
        """Asynchronous worker that performs the actual API submission."""
        challenge_dir = flag_path.parent
        meta_path = challenge_dir / ".challenge.json"

        # 1. Read metadata to get challenge ID
        if not meta_path.exists():
            console.print(
                f"[yellow]⚠ Auto-Submit:[/yellow] Captured '{flag}' in {challenge_dir.name}, "
                f"but no .challenge.json found. Skipping."
            )
            return

        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            console.print(f"[red]✗ Auto-Submit:[/red] Failed to read metadata in {challenge_dir.name}: {e}")
            return

        challenge_id = meta.get("id")
        challenge_name = meta.get("name", challenge_dir.name)
        category = meta.get("category", "")
        points = meta.get("points", 0)

        if not challenge_id:
            console.print(f"[red]✗ Auto-Submit:[/red] No 'id' found in {meta_path.name}")
            return

        # If already marked solved locally, we might want to skip, but it's
        # safer to attempt anyway in case the local state is stale.
        console.print(f"\n[bold magenta]🤖 Auto-Submit triggered![/bold magenta] Extracted flag for '{challenge_name}'")

        # 2. Submit to CTFd
        try:
            status, message = await self.api_client.submit_flag(challenge_id, flag)
        except APIError as e:
            status, message = "error", str(e)
            console.print(f"  [red]✗ API Error:[/red] {e}")
        else:
            if status == "correct":
                console.print(f"  [bold green]✔ Correct![/bold green] {message}")
                
                # Update local metadata as solved
                meta["solved"] = True
                meta["flag"] = flag
                try:
                    with open(meta_path, "w", encoding="utf-8") as f:
                        json.dump(meta, f, indent=2)
                except OSError:
                    pass
                
                # Trigger Discord notification if configured
                webhook_url = self.config.discord_webhook_url
                if webhook_url:
                    await send_flag_notification(
                        webhook_url=webhook_url,
                        challenge_name=challenge_name,
                        challenge_id=challenge_id,
                        category=category,
                        points=points,
                        flag=flag,
                        source="watch"
                    )
            elif status == "already_solved":
                console.print(f"  [bold yellow]★ Already Solved![/bold yellow] {message}")
            else:
                console.print(f"  [bold red]✗ Incorrect.[/bold red] {message}")

        # 3. Log attempt locally
        log_attempt(
            challenge_dir=challenge_dir,
            challenge_id=challenge_id,
            challenge_name=challenge_name,
            flag=flag,
            result=status,
            message=message,
            source="watch",
        )


async def start_watch_daemon(
    target_dir: Path,
    api_client: CTFdAPIClient,
    config: ConfigManager,
    pattern: str = DEFAULT_PATTERN,
) -> None:
    """
    Start the watchdog observer and block until interrupted.

    Args:
        target_dir: Directory to watch (either workspace root or challenge dir).
        api_client: Initialized API client.
        config:     Loaded config manager (for Discord webhook URL).
        pattern:    Regex pattern to extract flags.
    """
    target_dir = Path(target_dir).resolve()
    if not target_dir.is_dir():
        console.print(f"[red]Error:[/red] '{target_dir}' is not a valid directory.")
        return

    # Use flag_format to build regex if available and no custom pattern was given
    if pattern == DEFAULT_PATTERN and config.flag_format and "{}" in config.flag_format:
        prefix = config.flag_format.split("{")[0]
        pattern = re.escape(prefix) + r"\{.*?\}"

    loop = asyncio.get_running_loop()
    event_handler = FlagFileHandler(
        loop=loop,
        api_client=api_client,
        config=config,
        pattern=pattern,
    )

    observer = Observer()
    # Recursive=True allows watching all subdirectories if target_dir is workspace root
    observer.schedule(event_handler, str(target_dir), recursive=True)
    observer.start()

    console.print(f"[bold magenta]👁 Watch Daemon started[/bold magenta]")
    console.print(f"  Directory: [cyan]{target_dir}[/cyan]")
    console.print(f"  Pattern:   [yellow]{pattern}[/yellow]")
    console.print(f"  [dim]Monitoring for 'flag.txt' changes... Press Ctrl+C to stop.[/dim]\n")

    try:
        # Keep the async task alive indefinitely
        while True:
            await asyncio.sleep(1)
    except asyncio.CancelledError:
        pass
    finally:
        observer.stop()
        observer.join()
        console.print("\n[dim]Watch Daemon stopped.[/dim]")
