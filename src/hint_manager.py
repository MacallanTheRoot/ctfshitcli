"""
Hint Manager Module (v3.0)
Manages CTFd challenge hints: listing and unlocking with cost-aware confirmation.

Design:
  - HintManager wraps api_client hint calls.
  - list_hints()   — fetches all hints for a challenge (shows cost + lock status)
  - unlock_hint()  — confirms cost → POST /api/v1/unlocks → GET to reveal content
  - All UI output delegated to ui_renderer (render_hints_table, etc.).
  - render_* functions for hints are defined here as thin wrappers until
    ui_renderer.py is updated in Group 6.
"""

import logging
from typing import Any, Dict, List, Optional

from rich.panel import Panel
from rich.table import Table

from src.api_client import CTFdAPIClient, APIError, NotFoundError
from src.ui_renderer import console, render_error, render_success, render_warning

logger = logging.getLogger(__name__)


# ── Hint Renderers (will be moved to ui_renderer.py in Group 6) ──────────────

def render_hints_table(hints: List[Dict[str, Any]], challenge_name: str) -> None:
    """
    Render hint list as a formatted Rich table.

    Args:
        hints:          List of hint dicts from CTFd API.
        challenge_name: Name of the challenge (for table title).
    """
    if not hints:
        from src.ui_renderer import render_info
        render_info("No Hints", f"Challenge '{challenge_name}' has no hints.")
        return

    table = Table(
        title=f"[bold cyan]💡 Hints — {challenge_name}[/bold cyan]",
        border_style="bright_black",
        header_style="bold cyan",
        show_lines=False,
        expand=False,
    )
    table.add_column("Hint ID",  style="dim cyan",   width=8,  justify="right")
    table.add_column("Cost",     style="yellow",      width=8,  justify="right")
    table.add_column("Status",   width=14)
    table.add_column("Content",  style="white",       width=50, no_wrap=False)

    for hint in hints:
        hint_id  = str(hint.get("id", "?"))
        cost     = str(hint.get("cost", 0))
        content  = hint.get("content")

        if content:
            status  = "[bold green]🔓 Unlocked[/bold green]"
            preview = content[:120] + ("…" if len(content) > 120 else "")
        else:
            status  = "[dim red]🔒 Locked[/dim red]"
            preview = "[dim]—[/dim]"

        table.add_row(hint_id, cost, status, preview)

    console.print(table)


def render_hint_unlocked(hint: Dict[str, Any]) -> None:
    """Render a single unlocked hint's content in a panel."""
    content_text = hint.get("content") or "[dim]No content returned.[/dim]"
    cost         = hint.get("cost", 0)
    hint_id      = hint.get("id", "?")

    body = (
        f"[bold]Hint #{hint_id}[/bold]  "
        f"[dim](Cost: [yellow]{cost}[/yellow] pts)[/dim]\n\n"
        f"{content_text}"
    )
    console.print(
        Panel(
            body,
            title="[bold green]🔓  Hint Unlocked[/bold green]",
            style="green",
            expand=False,
            padding=(1, 2),
        )
    )


# ── HintManager ───────────────────────────────────────────────────────────────

class HintManager:
    """
    Manages hint listing and unlocking for CTFd challenges.

    Example:
        async with _make_client(config) as api:
            hm = HintManager(api)
            await hm.list_hints(challenge_id=42)
    """

    def __init__(self, api_client: CTFdAPIClient):
        self.api_client = api_client

    async def list_hints(self, challenge_id: int) -> List[Dict[str, Any]]:
        """
        Fetch and display all hints for a challenge.

        Args:
            challenge_id: CTFd challenge ID.

        Returns:
            List of hint dicts (raw API response).
        """
        # Fetch challenge name for display
        try:
            ch = await self.api_client.get_challenge(challenge_id)
            challenge_name = ch.get("name", f"Challenge #{challenge_id}")
        except (APIError, NotFoundError):
            challenge_name = f"Challenge #{challenge_id}"

        logger.info(f"Listing hints for challenge #{challenge_id}")
        try:
            hints = await self.api_client.get_hints(challenge_id)
        except APIError as e:
            render_error("Hint Fetch Failed", str(e))
            return []

        render_hints_table(hints, challenge_name)
        return hints

    async def unlock_hint(
        self,
        hint_id: int,
        confirmed: bool = False,
    ) -> Optional[Dict[str, Any]]:
        """
        Unlock a hint, optionally after user confirmation.

        Fetches the hint metadata first to show the cost, then (if not
        already confirmed via --yes) prompts the user before deducting
        points.

        Args:
            hint_id:   CTFd hint ID to unlock.
            confirmed: If True, skip the interactive [y/N] prompt
                       (equivalent to --yes / -y CLI flag).

        Returns:
            The hint dict with content populated, or None on failure.
        """
        logger.info(f"Attempting to unlock hint #{hint_id}")

        # 1. Fetch current hint metadata (cost, locked status)
        try:
            hint = await self.api_client.get_hint(hint_id)
        except NotFoundError:
            render_error("Hint Not Found", f"Hint #{hint_id} does not exist.")
            return None
        except APIError as e:
            render_error("Hint Fetch Failed", str(e))
            return None

        # 2. If already unlocked, just render and return
        if hint.get("content") is not None:
            render_warning(
                "Already Unlocked",
                f"Hint #{hint_id} is already unlocked — no points deducted.",
            )
            render_hint_unlocked(hint)
            return hint

        # 3. Show cost and request confirmation (unless --yes was passed)
        cost = hint.get("cost", 0)
        if not confirmed:
            console.print(
                f"\n[bold yellow]⚠  This hint costs [white]{cost}[/white] points.[/bold yellow]"
                f"\n   Hint ID: [cyan]#{hint_id}[/cyan]\n"
            )
            answer = console.input(
                "[bold]Unlock this hint? [[green]y[/green]/[red]N[/red]][/bold] "
            ).strip().lower()
            if answer not in ("y", "yes"):
                console.print("[dim]Cancelled.[/dim]\n")
                return None

        # 4. POST /api/v1/unlocks
        try:
            await self.api_client.unlock_hint(hint_id)
        except APIError as e:
            render_error("Unlock Failed", str(e))
            return None

        # 5. Re-fetch hint to get the now-visible content
        try:
            unlocked_hint = await self.api_client.get_hint(hint_id)
        except APIError as e:
            render_error(
                "Could Not Retrieve Hint",
                f"Unlock succeeded but re-fetch failed: {e}",
            )
            return None

        render_hint_unlocked(unlocked_hint)
        return unlocked_hint
