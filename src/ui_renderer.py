"""
UI Renderer Module
Terminal output formatting and rendering using the rich library.
Provides beautiful, dark-theme-friendly tables, alerts, panels, and progress indicators.

v2.0 Additions:
  - render_challenges_by_category() — category-grouped challenge tree table
  - render_config_panel()           — rich config display (replaces plain print)
  - render_workspace_init()         — workspace init success panel
  - render_challenge_added()        — challenge scaffolding success panel
  - render_download_summary()       — file download result panel
"""

from pathlib import Path
from typing import Any, Dict, List, Optional

from rich.columns import Columns
from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text
from rich.tree import Tree

# ─── Global Console ───────────────────────────────────────────────────────────
# force_terminal=True ensures colours render in all environments
console = Console(highlight=False)


# ─── Challenges ───────────────────────────────────────────────────────────────

def render_challenges_table(
    challenges: List[Dict[str, Any]],
    show_files: bool = True,
) -> None:
    """
    Render challenges as a flat formatted table.

    Args:
        challenges: List of challenge dicts from CTFd API.
        show_files: Whether to show file count column.
    """
    table = Table(
        title="[bold cyan]⚑ Available Challenges[/bold cyan]",
        border_style="bright_black",
        header_style="bold cyan",
        show_lines=False,
        expand=False,
    )

    table.add_column("#",         style="dim cyan",     width=5,  justify="right")
    table.add_column("Name",      style="bold white",   width=28, no_wrap=True)
    table.add_column("Category",  style="magenta",      width=14)
    table.add_column("Pts",       style="yellow",       width=6,  justify="right")
    table.add_column("Status",    style="white",        width=14)
    if show_files:
        table.add_column("Files", style="bright_black", width=6,  justify="center")

    for ch in challenges:
        ch_id    = str(ch.get("id", "?"))
        name     = ch.get("name", "Unknown")
        category = ch.get("category", "—")
        points   = str(ch.get("value", 0))
        solved   = ch.get("solved_by_me", False)

        team_solved = ch.get("solved_by_team", False)

        if solved:
            status = "[bold green]✔ Siz Çözdünüz[/bold green]"
        elif team_solved:
            status = "[bold blue]✔ Takım Çözdü[/bold blue]"
        else:
            status = "[red]○ Çözülmedi[/red]"

        if show_files:
            file_count = str(len(ch.get("files", []))) if ch.get("files") else "—"
            table.add_row(ch_id, name, category, points, status, file_count)
        else:
            table.add_row(ch_id, name, category, points, status)

    console.print(table)


def render_challenges_by_category(
    challenges: List[Dict[str, Any]],
) -> None:
    """
    Render challenges grouped by category — one rich Table per category.

    Args:
        challenges: List of challenge dicts from CTFd API.
    """
    if not challenges:
        render_info("No challenges found", "The challenge list is empty.")
        return

    # Group by category
    from collections import defaultdict
    groups: Dict[str, list] = defaultdict(list)
    for ch in challenges:
        cat = ch.get("category", "Uncategorized")
        groups[cat].append(ch)

    # Category colour palette (cycles)
    COLOURS = [
        "cyan", "magenta", "yellow", "green", "blue",
        "bright_cyan", "bright_magenta", "bright_yellow",
    ]

    total   = len(challenges)
    solved  = sum(1 for c in challenges if c.get("solved_by_me"))

    # Header
    console.print()
    console.print(
        Panel(
            f"[bold white]{total}[/bold white] challenges across "
            f"[bold cyan]{len(groups)}[/bold cyan] categories  ·  "
            f"[bold green]{solved}[/bold green] solved  "
            f"[dim]({total - solved} remaining)[/dim]",
            title="[bold cyan]⚑  CTF Challenges[/bold cyan]",
            border_style="cyan",
            expand=False,
        )
    )
    console.print()

    for idx, (category, chs) in enumerate(sorted(groups.items())):
        colour = COLOURS[idx % len(COLOURS)]
        cat_solved   = sum(1 for c in chs if c.get("solved_by_me"))
        cat_total    = len(chs)
        cat_pts      = sum(c.get("value", 0) for c in chs)
        solved_pts   = sum(c.get("value", 0) for c in chs if c.get("solved_by_me"))

        table = Table(
            title=(
                f"[bold {colour}]{category.upper()}[/bold {colour}]  "
                f"[dim]{cat_solved}/{cat_total} solved · "
                f"{solved_pts}/{cat_pts} pts[/dim]"
            ),
            border_style="bright_black",
            header_style=f"bold {colour}",
            show_lines=False,
            expand=False,
            min_width=60,
        )
        table.add_column("ID",     style="dim",          width=5,  justify="right")
        table.add_column("Name",   style="bold white",   width=30, no_wrap=True)
        table.add_column("Pts",    style="yellow",       width=6,  justify="right")
        table.add_column("Status", width=14)
        table.add_column("Files",  style="bright_black", width=5,  justify="center")

        for ch in sorted(chs, key=lambda x: x.get("value", 0)):
            team_solved = ch.get("solved_by_team", False)
            file_cnt  = len(ch.get("files", []))
            
            if solved:
                status = "[bold green]✔ Siz Çözdünüz[/bold green]"
            elif team_solved:
                status = "[bold blue]✔ Takım Çözdü[/bold blue]"
            else:
                status = "[red]○ Çözülmedi[/red]"
            table.add_row(
                str(ch.get("id", "?")),
                ch.get("name", "Unknown"),
                str(ch.get("value", 0)),
                status,
                str(file_cnt) if file_cnt else "—",
            )

        console.print(table)
        console.print()


# ─── Flag Submission ──────────────────────────────────────────────────────────

def render_flag_result(
    challenge_id: int,
    challenge_name: str,
    success: bool,
    message: str,
    correct: Optional[bool] = None,
    status: Optional[str] = None,
) -> None:
    """
    Render flag submission result with a styled panel.

    Args:
        challenge_id:   Challenge ID.
        challenge_name: Challenge name.
        success:        Whether submission request succeeded.
        message:        Response message from CTFd.
        correct:        Whether flag was correct.
        status:         Raw status string from CTFd (e.g. 'already_solved').
    """
    if status == "already_solved":
        icon, title, style = "★", "[yellow]Already Solved[/yellow]", "yellow"
    elif success and correct:
        icon, title, style = "✔", "[bold green]Correct Flag![/bold green]", "green"
    elif success and not correct:
        icon, title, style = "✗", "[bold red]Wrong Flag[/bold red]", "red"
    else:
        icon, title, style = "⚠", "[yellow]Submission Error[/yellow]", "yellow"

    content = (
        f"[bold]Challenge:[/bold] [cyan]#{challenge_id}[/cyan] — {challenge_name}\n"
        f"[bold]Result:[/bold]    {message}"
    )
    if status:
        content += f"\n[bold]Status:[/bold]    [dim]{status}[/dim]"

    console.print(
        Panel(
            content,
            title=f"{icon}  {title}",
            style=style,
            expand=False,
            padding=(1, 2),
        )
    )


# ─── Generic Alerts ───────────────────────────────────────────────────────────

def render_error(message: str, details: Optional[str] = None) -> None:
    """Render an error panel."""
    content = f"[bold white]{message}[/bold white]"
    if details:
        content += f"\n[dim]{details}[/dim]"
    console.print(
        Panel(content, title="[bold red]✗  Error[/bold red]", style="red",
              expand=False, padding=(0, 2))
    )


def render_success(message: str, details: Optional[str] = None) -> None:
    """Render a success panel."""
    content = f"[bold white]{message}[/bold white]"
    if details:
        content += f"\n[dim]{details}[/dim]"
    console.print(
        Panel(content, title="[bold green]✔  Success[/bold green]", style="green",
              expand=False, padding=(0, 2))
    )


def render_info(message: str, details: Optional[str] = None) -> None:
    """Render an info panel."""
    content = f"[bold white]{message}[/bold white]"
    if details:
        content += f"\n[dim]{details}[/dim]"
    console.print(
        Panel(content, title="[bold blue]ℹ  Info[/bold blue]", style="blue",
              expand=False, padding=(0, 2))
    )


def render_warning(message: str, details: Optional[str] = None) -> None:
    """Render a warning panel."""
    content = f"[bold white]{message}[/bold white]"
    if details:
        content += f"\n[dim]{details}[/dim]"
    console.print(
        Panel(content, title="[bold yellow]⚠  Warning[/bold yellow]", style="yellow",
              expand=False, padding=(0, 2))
    )


def render_alert(
    title: str,
    message: str,
    alert_type: str = "info",
) -> None:
    """
    Render a generic alert panel (backward-compatible).

    Args:
        title:      Alert title.
        message:    Alert message content.
        alert_type: One of: info, warning, error, success.
    """
    handlers = {
        "info":    render_info,
        "success": render_success,
        "warning": render_warning,
        "error":   render_error,
    }
    handler = handlers.get(alert_type, render_info)
    handler(title, message)


# ─── Scoreboard ───────────────────────────────────────────────────────────────

def render_scoreboard_table(
    scoreboard: List[Dict[str, Any]],
    limit: Optional[int] = None,
) -> None:
    """Render scoreboard as a formatted table."""
    table = Table(
        title="[bold cyan]🏆 Scoreboard[/bold cyan]",
        border_style="bright_black",
        header_style="bold cyan",
        show_lines=False,
        expand=False,
    )
    table.add_column("Rank",       style="dim yellow",  width=6,  justify="right")
    table.add_column("Team",       style="bold white",  width=28, no_wrap=True)
    table.add_column("Score",      style="yellow",      width=10, justify="right")
    table.add_column("Challenges", style="magenta",     width=12, justify="center")

    data = scoreboard[:limit] if limit else scoreboard

    MEDAL = {1: "🥇", 2: "🥈", 3: "🥉"}
    for idx, team in enumerate(data, start=1):
        rank_str      = MEDAL.get(idx, str(idx))
        name          = team.get("name", "Unknown")
        score         = str(team.get("score", 0))
        challenge_cnt = str(len(team.get("solves", [])))
        table.add_row(rank_str, name, score, challenge_cnt)

    console.print(table)


# ─── Bulk Submission ──────────────────────────────────────────────────────────

def render_bulk_submission_summary(
    total: int,
    successful: int,
    failed: int,
    skipped: int,
) -> None:
    """Render summary of bulk flag submissions."""
    attempted     = total - skipped
    success_rate  = (successful / attempted * 100) if attempted > 0 else 0.0

    content = (
        f"[bold]Total Submissions:[/bold] {total}\n"
        f"[bold green]✔ Correct:[/bold green]   {successful}\n"
        f"[bold red]✗ Incorrect:[/bold red] {failed}\n"
        f"[bold yellow]⊘ Skipped:[/bold yellow]  {skipped}\n"
        f"[bold]Success Rate:[/bold]  {success_rate:.1f}%"
    )
    console.print(
        Panel(
            content,
            title="[bold cyan]Bulk Submission Summary[/bold cyan]",
            style="cyan",
            expand=False,
            padding=(1, 2),
        )
    )


# ─── Workspace ────────────────────────────────────────────────────────────────

def render_workspace_init(
    workspace_path: Path,
    ctf_name: str,
    ctf_url: str,
) -> None:
    """
    Render workspace initialization success panel with a directory tree.

    Args:
        workspace_path: Path to the workspace root.
        ctf_name:       CTF event name.
        ctf_url:        CTFd platform URL.
    """
    tree = Tree(
        f"[bold cyan]{workspace_path.name}/[/bold cyan]",
        guide_style="bright_black",
    )
    tree.add("[green].ctf_config.json[/green]  [dim]← workspace config[/dim]")
    tree.add("[yellow]flags.csv[/yellow]         [dim]← flag log[/dim]")
    tree.add("[blue]notes/[/blue]            [dim]← free-form notes[/dim]")
    ch = tree.add("[bright_black]<category>/[/bright_black]")
    ch.add("[bright_black]<challenge>/[/bright_black]")

    # Capture the Tree as a string so it renders inside the Panel
    _cap_console = Console(highlight=False, width=60)
    with _cap_console.capture() as cap:
        _cap_console.print(tree)
    tree_str = cap.get().rstrip()

    content = (
        f"[bold]CTF:[/bold]      [cyan]{ctf_name}[/cyan]\n"
        f"[bold]Platform:[/bold] [link={ctf_url}]{ctf_url}[/link]\n"
        f"[bold]Path:[/bold]     {workspace_path}\n\n"
        f"{tree_str}"
    )

    console.print(
        Panel(
            content,
            title="[bold green]✔  Workspace Initialized[/bold green]",
            style="green",
            expand=False,
            padding=(1, 2),
        )
    )


def render_challenge_added(
    challenge_dir: Path,
    created_files: dict,
) -> None:
    """
    Render challenge scaffolding success panel.

    Args:
        challenge_dir: Path to the created challenge directory.
        created_files: Dict mapping file type → Path.
    """
    tree = Tree(
        f"[bold cyan]{challenge_dir.parent.name}/[/bold cyan]",
        guide_style="bright_black",
    )
    branch = tree.add(f"[bold magenta]{challenge_dir.name}/[/bold magenta]")

    labels = {
        "readme":    ("[green]README.md[/green]",   "challenge notes template"),
        "solve_py":  ("[yellow]solve.py[/yellow]",  "exploit script template"),
        "notes_txt": ("[yellow]notes.txt[/yellow]", "recon notes template"),
        "meta":      ("[dim].challenge.json[/dim]", "metadata"),
    }
    for key, (styled, desc) in labels.items():
        if key in created_files:
            branch.add(f"{styled}  [dim]← {desc}[/dim]")

    # Capture the Tree as a string so it renders inside the Panel
    _cap_console = Console(highlight=False, width=60)
    with _cap_console.capture() as cap:
        _cap_console.print(tree)
    tree_str = cap.get().rstrip()

    console.print(
        Panel(
            tree_str,
            title="[bold green]✔  Challenge Directory Created[/bold green]",
            style="green",
            expand=False,
            padding=(1, 2),
        )
    )
    console.print(
        f"  [dim]cd[/dim] [bold]{challenge_dir}[/bold]"
    )


# ─── Config Display ───────────────────────────────────────────────────────────

def render_config_panel(config) -> None:
    """
    Display current configuration in a styled panel (token masked).

    Args:
        config: ConfigManager instance.
    """
    token = config.api_token
    token_display = (
        token[:12] + "..." + token[-4:] if len(token) > 16 else "***"
    )

    content = (
        f"[bold]CTF Name:[/bold]      [cyan]{config.ctf_name or '—'}[/cyan]\n"
        f"[bold]Platform URL:[/bold]  [link={config.ctf_url}]{config.ctf_url}[/link]\n"
        f"[bold]API Token:[/bold]     [dim]{token_display}[/dim]\n"
        f"[bold]Poll Interval:[/bold] {config.poll_interval}s\n"
        f"[bold]API Timeout:[/bold]   {config.api_timeout}s\n"
        f"[bold]Max Retries:[/bold]   {config.max_retries}\n"
        f"[bold]Log Level:[/bold]     {config.log_level}"
    )
    console.print(
        Panel(
            content,
            title="[bold cyan]⚙  Configuration[/bold cyan]",
            border_style="cyan",
            expand=False,
            padding=(1, 2),
        )
    )


# ─── Download Summary ─────────────────────────────────────────────────────────

def render_download_summary(
    downloaded: List[str],
    failed: List[str],
    dest_dir: Path,
) -> None:
    """Render summary of downloaded files."""
    lines = []
    if downloaded:
        lines.append(f"[bold green]✔ Downloaded {len(downloaded)} files[/bold green]")
        for f in downloaded:
            lines.append(f"  [dim]↳ {f}[/dim]")
    if failed:
        lines.append(f"[bold red]✗ Failed to download {len(failed)} files[/bold red]")
        for f in failed:
            lines.append(f"  [dim]↳ {f}[/dim]")

    content = "\n".join(lines) + f"\n\n[dim]→ {dest_dir}[/dim]"
    style   = "green" if not failed else "yellow"
    title   = (
        "[bold green]✔  Download Complete[/bold green]"
        if not failed
        else "[bold yellow]⚠  Download Partial[/bold yellow]"
    )
    console.print(
        Panel(content, title=title, style=style, expand=False, padding=(1, 2))
    )

def render_hints_table(hints: List[Dict[str, Any]]) -> None:
    """Render hints table (ID, Cost, Status)."""
    if not hints:
        render_info("No hints available for this challenge.")
        return

    table = Table(
        title="[bold cyan]💡 Challenge Hints[/bold cyan]",
        border_style="bright_black",
        header_style="bold cyan",
        show_lines=False,
        expand=False,
    )
    table.add_column("ID", style="dim", width=5, justify="right")
    table.add_column("Cost", style="yellow", width=6, justify="right")
    table.add_column("Status", style="white", width=12)

    for hint in hints:
        h_id = str(hint.get("id", "?"))
        cost = str(hint.get("cost", 0))
        # Depending on CTFd data, it might have 'content' if unlocked or just a boolean
        unlocked = hint.get("content") is not None or hint.get("unlocked", False)
        status = "[bold green]Unlocked[/bold green]" if unlocked else "[dim]Locked[/dim]"
        table.add_row(h_id, cost, status)

    console.print(table)


def render_submission_history(attempts: List[Dict[str, Any]], challenge_id: Optional[int] = None) -> None:
    """Render submission history table (Time, Flag, Status)."""
    title = "[bold cyan]📜 Submission History[/bold cyan]"
    if challenge_id is not None:
        title = f"[bold cyan]📜 Submission History (Challenge #{challenge_id})[/bold cyan]"

    if not attempts:
        render_info("No local submissions found.")
        return

    table = Table(
        title=title,
        border_style="bright_black",
        header_style="bold cyan",
        show_lines=False,
        expand=False,
    )
    table.add_column("Time", style="dim", width=22)
    table.add_column("Flag", style="white", width=35)
    table.add_column("Status", style="white", width=15)

    for att in attempts:
        time_str = att.get("time", att.get("timestamp", "Unknown"))
        flag = att.get("flag", "Unknown")
        status_val = att.get("status", "")
        correct = att.get("correct", False)
        
        if correct or status_val == "correct":
            status = "[bold green]✔ Correct[/bold green]"
        elif status_val == "already_solved":
            status = "[yellow]★ Already Solved[/yellow]"
        else:
            status = "[bold red]✗ Incorrect[/bold red]"

        table.add_row(time_str, flag, status)

    console.print(table)



def _fmt_size(n: int) -> str:
    """Format byte count into human-readable string."""
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


# ─── Header / Misc ────────────────────────────────────────────────────────────

def print_header(text: str) -> None:
    """Print a bold cyan rule header."""
    console.print()
    console.print(Rule(f"[bold cyan]{text}[/bold cyan]", style="cyan"))
    console.print()


def print_loading(message: str) -> None:
    """Print a simple loading indicator (no spinner — use rich.status for live)."""
    console.print(f"[dim cyan]⠋[/dim cyan] {message}", end="\r")


def clear_line() -> None:
    """Clear the current terminal line."""
    console.print(" " * 100, end="\r")
