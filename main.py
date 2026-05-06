#!/usr/bin/env python3
"""
CTFd Swiss Army Knife CLI v2.0
A definitive, high-performance CTF management CLI.

Commands:
  Workspace: init, add
  API:       list, pull, submit, bulk, track, config, categories
"""

import asyncio
import logging
import re
import sys
from pathlib import Path
from typing import Optional


# ── Helpers ───────────────────────────────────────────────────────────────────

def _slugify(text: str) -> str:
    """Convert text to a filesystem-safe, URL-friendly slug.

    Examples:
        "PicoCTF 2025"  → "picoctf-2025"
        "SQL Injection!" → "sql-injection"
        "Web/XSS"        → "web-xss"
    """
    text = str(text).lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)   # strip non-word chars
    text = re.sub(r"[\s_/\\]+", "-", text) # spaces / separators → hyphens
    text = re.sub(r"-+", "-", text)        # collapse consecutive hyphens
    text = text.strip("-")
    return text or "challenge"

import click

from src.api_client import CTFdAPIClient, APIError
from src.challenge_scraper import ChallengeScraper
from src.config_manager import resolve_config, load_from_env, ConfigManager
from src.flag_submitter import FlagSubmitter
from src.scoreboard_tracker import ScoreboardTracker, default_change_callback
from src.ui_renderer import (
    console,
    print_header,
    render_error,
    render_info,
    render_success,
    render_warning,
    render_workspace_init,
    render_challenge_added,
    render_challenges_by_category,
    render_config_panel,
    render_challenges_table,
)
from src.workspace_manager import (
    init_workspace,
    add_challenge,
    detect_challenge_context,
    find_workspace_root,
    update_workspace_config,
    CONFIG_KEY_ALIASES,
    WORKSPACE_CONFIG_FILENAME,
)

# ── Logging ───────────────────────────────────────────────────────────────────

def _setup_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[logging.FileHandler("ctf_client.log", encoding="utf-8")],
    )


# ── Banner ────────────────────────────────────────────────────────────────────

BANNER = """\
[bold cyan]
   ██████╗███████╗██╗      [bold white]CSL[/bold white][bold cyan]-CtfShitCli[/bold cyan]
  ██╔════╝██╔════╝██║      [dim]CTFd Swiss Army Knife  v2.0[/dim]
  ██║     ███████╗██║
  ██║     ╚════██║██║      [dim]dev by [link=https://github.com/MacallanTheRoot]macallantheroot[/link][/dim]
  ╚██████╗███████║███████╗
   ╚═════╝╚══════╝╚══════╝[/bold cyan]
"""

# ── CLI Group ─────────────────────────────────────────────────────────────────

@click.group(
    context_settings={"help_option_names": ["-h", "--help"], "max_content_width": 100},
    invoke_without_command=True,
)
@click.option("--env", "-e", type=click.Path(path_type=Path), default=None,
              help="Path to .env file (default: auto-detect .ctf_config.json or .env).")
@click.option("--log-level", "-l",
              type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR"], case_sensitive=False),
              default="INFO", show_default=True, help="Log verbosity (ctf_client.log).")
@click.pass_context
def cli(ctx: click.Context, env: Optional[Path], log_level: str) -> None:
    """CTFd Swiss Army Knife — workspace and API management CLI."""
    _setup_logging(log_level)
    ctx.ensure_object(dict)
    ctx.obj["env"] = env
    ctx.obj["log_level"] = log_level
    if ctx.invoked_subcommand is None:
        console.print(BANNER)
        console.print(ctx.get_help())


# ── Helpers ───────────────────────────────────────────────────────────────────

def _load_config(ctx_obj: dict) -> ConfigManager:
    env_path = ctx_obj.get("env")
    try:
        return load_from_env(env_path) if env_path else resolve_config()
    except FileNotFoundError as e:
        render_error("Configuration Not Found", str(e))
        sys.exit(1)
    except ValueError as e:
        render_error("Configuration Invalid", str(e))
        sys.exit(1)


def _make_client(config: ConfigManager) -> CTFdAPIClient:
    return CTFdAPIClient(
        base_url=config.ctf_url,
        api_token=config.api_token,
        timeout=config.api_timeout,
        max_retries=config.max_retries,
    )


# ── WORKSPACE COMMANDS ────────────────────────────────────────────────────────

@cli.command("init")
@click.argument("ctf_url")
@click.option("--token", "-t", prompt="API Token", hide_input=True, help="CTFd API token.")
@click.option("--name",  "-n", default="", help="CTF event name (also used to name the workspace folder).")
@click.option("--force", "-f", is_flag=True, help="Overwrite existing config.")
@click.option("--path",  "-p", default=None, type=click.Path(file_okay=False, path_type=Path),
              help="Workspace directory. Auto-derived from --name when omitted (default: ./ctf-workspace).")
@click.pass_context
def cmd_init(ctx, ctf_url, token, name, force, path):
    """
    Initialize a CTF workspace directory.

    \b
    If --path is omitted, the folder name is derived from --name (slugified)
    or defaults to './ctf-workspace'. The directory is created automatically.

    \b
    Creates inside the workspace:
      .ctf_config.json  — URL, token, settings
      flags.csv         — flag log
      notes/            — notes directory

    \b
    Examples:
      ctf init https://ctf.example.com -t ctfd_...
      ctf init https://ctf.example.com -t ctfd_... --name "PicoCTF 2025"
      ctf init https://ctf.example.com -t ctfd_... --path ./my-workspace
    """
    # ── Resolve workspace path ──────────────────────────────────────────────
    if path is None:
        folder = _slugify(name) if name.strip() else "ctf-workspace"
        workspace = Path.cwd() / folder
    else:
        workspace = Path(path).resolve()

    workspace.mkdir(parents=True, exist_ok=True)
    ctf_name = name.strip() or "My CTF"

    try:
        init_workspace(workspace, ctf_url, token, ctf_name, force)
        render_workspace_init(workspace, ctf_name, ctf_url)

        # Tell the user the next step
        try:
            rel = workspace.relative_to(Path.cwd())
        except ValueError:
            rel = workspace
        console.print(
            f"\n[bold cyan]Next:[/bold cyan]  [bold]cd {rel}[/bold]\n"
        )

    except FileExistsError as e:
        render_warning("Already Initialized", str(e))
        sys.exit(1)
    except ValueError as e:
        render_error("Init Failed", str(e))
        sys.exit(1)




@cli.command("add")
@click.argument("challenge_path")
@click.option("--id",     "-i", "challenge_id", type=int, default=None, help="CTFd challenge ID.")
@click.option("--points", "-p", type=int,   default=None, help="Point value.")
@click.option("--desc",   "-d", default="",               help="Pre-fill README description.")
@click.pass_context
def cmd_add(ctx, challenge_path, challenge_id, points, desc):
    """
    Scaffold a challenge directory with templates.

    \b
    Format: <category>/<name>
    Examples:
      ctf add web/easy-sqli
      ctf add crypto/rsa-basics --id 12 --points 300

    \b
    Creates:
      <category>/<name>/README.md       — notes template
      <category>/<name>/solve.py        — exploit template
      <category>/<name>/.challenge.json — metadata
    """
    try:
        created = add_challenge(challenge_path, challenge_id, points, desc)
        render_challenge_added(created["root"], created)
    except FileNotFoundError as e:
        render_error("Workspace Not Found", str(e))
        sys.exit(1)
    except ValueError as e:
        render_error("Invalid Path", str(e))
        sys.exit(1)


# ── API COMMANDS ──────────────────────────────────────────────────────────────

@cli.command("list")
@click.option("--category", "-c", default=None, help="Filter by category.")
@click.option("--flat",     "-f", is_flag=True, help="Flat table (no category grouping).")
@click.option("--no-cache",       is_flag=True, help="Force fresh fetch.")
@click.pass_context
def cmd_list(ctx, category, flat, no_cache):
    """
    List challenges, grouped by category.

    \b
    Examples:
      ctf list                  # All challenges
      ctf list --category web   # Web only
      ctf list --flat           # Flat table
    """
    config = _load_config(ctx.obj)

    async def _run():
        from rich.status import Status
        async with _make_client(config) as api:
            scraper = ChallengeScraper(api)
            with Status("[cyan]Fetching challenges…[/cyan]", console=console):
                try:
                    challenges = (
                        await scraper.get_challenges_by_category(category, use_cache=not no_cache)
                        if category
                        else await scraper.fetch_challenges(use_cache=not no_cache)
                    )
                except APIError as e:
                    render_error("Fetch Failed", str(e))
                    return 1

        if not challenges:
            render_info("No Challenges Found",
                        f"No challenges{f' in [{category}]' if category else ''}.")
            return 0

        if flat:
            render_challenges_table(challenges)
        else:
            render_challenges_by_category(challenges)

        solved = sum(1 for c in challenges if c.get("solved_by_me"))
        pts_e  = sum(c.get("value", 0) for c in challenges if c.get("solved_by_me"))
        pts_t  = sum(c.get("value", 0) for c in challenges)
        console.print(f"[dim]  {solved}/{len(challenges)} solved · {pts_e}/{pts_t} pts[/dim]\n")
        return 0

    sys.exit(asyncio.run(_run()))


@cli.command("scrape", hidden=True)
@click.option("--category", default=None)
@click.option("--no-files", is_flag=True)
@click.pass_context
def cmd_scrape(ctx, category, no_files):
    """[Deprecated] Use 'list' instead."""
    render_warning("Deprecated", "'scrape' has been renamed to 'list'.")
    ctx.invoke(cmd_list, category=category, flat=no_files, no_cache=False)


@cli.command("pull")
@click.option("--id",        "-i", "challenge_id", type=int, default=None,
              help="Challenge ID (auto-detected from .challenge.json if omitted).")
@click.option("--out",       "-o", type=click.Path(file_okay=False, path_type=Path), default=None,
              help="Output directory (default: cwd). Ignored when --all is used.")
@click.option("--overwrite", "-f", is_flag=True, help="Re-download already-existing files.")
@click.option("--all",       "-a", "pull_all",   is_flag=True,
              help="Sync ALL challenges: scaffold directories and download every attachment.")
@click.pass_context
def cmd_pull(ctx, challenge_id, out, overwrite, pull_all):
    """
    Download challenge file attachments.

    \b
    Single-challenge mode (default):
      Auto-detects challenge ID from .challenge.json in cwd.
      Pass --id to override.

    \b
    Bulk sync mode (--all):
      Fetches every visible challenge from CTFd, creates the category/name
      directory structure, generates README + solve.py templates, and
      downloads all attached files — all in one shot.

    \b
    Examples:
      ctf pull                        # Auto-detect from .challenge.json
      ctf pull --id 42                # Explicit single challenge
      ctf pull --all                  # Full workspace sync
      ctf pull --all --overwrite      # Force re-download of existing files
    """
    config = _load_config(ctx.obj)

    # ── BULK SYNC MODE ────────────────────────────────────────────────────────
    if pull_all:
        async def _run_all():
            from src.file_downloader import download_challenge_files
            from rich.panel import Panel
            from rich.progress import (
                Progress, SpinnerColumn, TextColumn,
                BarColumn, MofNCompleteColumn,
            )

            # Workspace root is required for add_challenge to know where to write
            workspace_root = find_workspace_root()
            if workspace_root is None:
                render_error(
                    "No Workspace Found",
                    "Run 'ctf init <url>' first, then re-run 'ctf pull --all'.",
                )
                return 1

            async with _make_client(config) as api:
                # ── Fetch challenge list ──────────────────────────────────────
                from rich.status import Status
                with Status("[cyan]Fetching challenge list…[/cyan]", console=console):
                    try:
                        scraper = ChallengeScraper(api)
                        challenges = await scraper.fetch_challenges(use_cache=False)
                    except APIError as e:
                        render_error("Fetch Failed", str(e))
                        return 1

                if not challenges:
                    render_info("No Challenges", "The server returned no visible challenges.")
                    return 0

                total     = len(challenges)
                scaffolded = 0
                files_dl  = 0
                failed    = []  # list of (id, name, reason)

                console.print(
                    f"\n[bold cyan]⚡ Syncing [white]{total}[/white] challenges "
                    f"→ [white]{workspace_root}[/white][/bold cyan]\n"
                )

                # ── Per-challenge progress bar ────────────────────────────────
                with Progress(
                    SpinnerColumn(style="cyan"),
                    TextColumn("[bold cyan]{task.description}", justify="left"),
                    BarColumn(bar_width=28, style="cyan", complete_style="green"),
                    MofNCompleteColumn(),
                    console=console,
                    transient=False,
                ) as progress:
                    task = progress.add_task(
                        "Starting…", total=total
                    )

                    for ch in challenges:
                        ch_id   = ch.get("id")
                        ch_name = ch.get("name", f"challenge-{ch_id}")
                        ch_cat  = ch.get("category", "misc")
                        ch_slug = _slugify(ch_name)
                        ch_path = f"{_slugify(ch_cat)}/{ch_slug}"

                        progress.update(
                            task,
                            description=(
                                f"[magenta]{_slugify(ch_cat)}[/magenta]"
                                f"[dim]/[/dim][white]{ch_slug}[/white]"
                            ),
                        )

                        try:
                            # 1. Scaffold directory + templates
                            created = add_challenge(
                                challenge_path=ch_path,
                                challenge_id=ch_id,
                                points=ch.get("value"),
                                workspace_root=workspace_root,
                            )
                            scaffolded += 1

                            # 2. Always attempt file download.
                            #    The challenge LIST endpoint does NOT include the
                            #    `files` field — only the detail endpoint does.
                            #    We can't pre-check; just try and handle gracefully.
                            try:
                                dl = await download_challenge_files(
                                    api_client=api,
                                    challenge_id=ch_id,
                                    dest_dir=created["root"],
                                    overwrite=overwrite,
                                    show_progress=False,
                                )
                                if dl:
                                    files_dl += 1
                            except ValueError:
                                # Challenge has no attached files — not an error
                                pass
                            except APIError as dl_err:
                                console.print(
                                    f"  [yellow]⚠ #{ch_id} file download: {dl_err}[/yellow]"
                                )

                        except Exception as err:
                            failed.append((ch_id, ch_name, str(err)))
                            console.print(
                                f"  [red]✗ #{ch_id} {ch_name!r}: {err}[/red]"
                            )

                        progress.advance(task)

                    progress.update(task, description="[green]Done[/green]")

                # ── Summary panel ─────────────────────────────────────────────
                console.print()
                console.print(
                    Panel(
                        f"[bold]Challenges total:[/bold]    {total}\n"
                        f"[green]✔ Scaffolded:[/green]        {scaffolded}\n"
                        f"[cyan]📥 Files downloaded:[/cyan]  {files_dl} challenge(s) had files\n"
                        f"[red]✗ Errors:[/red]            {len(failed)}",
                        title="[bold cyan]⚡  Pull All — Complete[/bold cyan]",
                        border_style="cyan",
                        expand=False,
                        padding=(1, 2),
                    )
                )

                if failed:
                    console.print("\n[dim red]Failed challenges:[/dim red]")
                    for fid, fname, ferr in failed:
                        console.print(
                            f"  [red]#{fid}[/red] [white]{fname}[/white] "
                            f"[dim]— {ferr}[/dim]"
                        )

            return 1 if failed else 0

        sys.exit(asyncio.run(_run_all()))

    # ── SINGLE CHALLENGE MODE ─────────────────────────────────────────────────
    cid = challenge_id
    if cid is None:
        meta = detect_challenge_context()
        if meta and meta.get("id"):
            cid = int(meta["id"])
            console.print(
                f"[dim]Auto-detected challenge [cyan]#{cid}[/cyan] "
                f"({meta.get('name', '?')}) from .challenge.json[/dim]"
            )
        else:
            render_error(
                "Challenge ID Required",
                "Provide --id, run inside a challenge directory, or use --all.",
            )
            sys.exit(1)

    dest = (out or Path.cwd()).resolve()

    async def _run():
        from src.file_downloader import download_challenge_files
        from src.ui_renderer import render_download_summary
        async with _make_client(config) as api:
            try:
                downloaded = await download_challenge_files(
                    api, cid, dest, overwrite, show_progress=True
                )
                render_download_summary(downloaded, [], dest)
                return 0
            except ValueError as e:
                render_info("No Files", str(e))
                return 0
            except APIError as e:
                render_error("Download Failed", str(e))
                return 1

    sys.exit(asyncio.run(_run()))




@cli.command("submit")
@click.argument("flag")
@click.option("--id", "-i", "challenge_id", type=int, default=None,
              help="Challenge ID (auto-detected from .challenge.json if omitted).")
@click.pass_context
def cmd_submit(ctx, flag, challenge_id):
    """
    Submit a flag for a challenge.

    Auto-detects challenge ID from .challenge.json when run inside a
    directory created with 'ctf add'.

    \b
    Examples:
      ctf submit 'flag{xss_pwned}'       # Auto-detect ID
      ctf submit 'flag{...}' --id 42     # Explicit ID
    """
    config = _load_config(ctx.obj)

    cid = challenge_id
    if cid is None:
        meta = detect_challenge_context()
        if meta and meta.get("id"):
            cid = int(meta["id"])
            console.print(f"[dim]Auto-detected [cyan]#{cid}[/cyan] "
                          f"({meta.get('name', '?')}) from .challenge.json[/dim]")
        else:
            render_error("Challenge ID Required",
                         "Provide --id or run inside a challenge directory.")
            sys.exit(1)

    async def _run():
        from rich.status import Status
        async with _make_client(config) as api:
            submitter = FlagSubmitter(api)
            with Status(f"[cyan]Submitting flag for #{cid}…[/cyan]", console=console):
                result = await submitter.submit_single_flag(cid, flag)
        submitter.display_single_result(result)

        if result.correct and challenge_id is None:
            from src.workspace_manager import update_challenge_meta
            update_challenge_meta(solved=True, flag=flag)
            console.print("[dim green]  ↳ .challenge.json marked solved[/dim green]")

        return 0 if result.correct else 1

    sys.exit(asyncio.run(_run()))


@cli.command("bulk")
@click.argument("csv_file", type=click.Path(exists=True, path_type=Path))
@click.option("--details",   "-d", is_flag=True, help="Show per-flag results.")
@click.option("--no-jitter",       is_flag=True, help="Disable random delays between submissions.")
@click.pass_context
def cmd_bulk(ctx, csv_file, details, no_jitter):
    """
    Bulk-submit flags from a CSV file.

    \b
    CSV format:
      challenge_id,flag
      1,flag{first_challenge}
      5,flag{web_100}

    \b
    Example:
      ctf bulk flags.csv --details
    """
    config = _load_config(ctx.obj)

    async def _run():
        async with _make_client(config) as api:
            submitter = FlagSubmitter(api)
            try:
                results, summary = await submitter.submit_bulk_flags(
                    csv_file_path=csv_file, jitter=not no_jitter
                )
                submitter.display_bulk_results(results, summary, show_details=details)
                return 0
            except (FileNotFoundError, ValueError) as e:
                render_error("Setup Failed", str(e))
                return 1
            except APIError as e:
                render_error("Bulk Submission Failed", str(e))
                return 1

    sys.exit(asyncio.run(_run()))


@cli.command("track")
@click.option("--teams", "-t", multiple=True, help="Team name(s) to focus on.")
@click.option("--limit", "-n", type=int, default=10, show_default=True,
              help="Number of teams to display.")
@click.pass_context
def cmd_track(ctx, teams, limit):
    """
    Real-time scoreboard tracking. Press Ctrl+C to stop.

    \b
    Examples:
      ctf track
      ctf track --teams "MyTeam" "Rivals" --limit 20
    """
    config = _load_config(ctx.obj)

    async def _run():
        from rich.status import Status
        async with _make_client(config) as api:
            tracker = ScoreboardTracker(
                api, poll_interval=config.poll_interval,
                target_teams=list(teams) or None
            )
            tracker.add_callback(default_change_callback)
            print_header("Live Scoreboard Tracker")
            with Status("[cyan]Fetching scoreboard…[/cyan]", console=console):
                await tracker.fetch_and_display_scoreboard(limit=limit)
            render_success("Tracking Active",
                           f"Polling every {config.poll_interval}s. Ctrl+C to stop.")
            await tracker.start_polling()
            try:
                while True:
                    await asyncio.sleep(1)
            except KeyboardInterrupt:
                console.print("\n[yellow]Stopping…[/yellow]")
                await tracker.stop_polling()
                render_info("Tracking Stopped", "Session ended.")
                return 0

    try:
        sys.exit(asyncio.run(_run()))
    except APIError as e:
        render_error("Tracking Failed", str(e))
        sys.exit(1)


@cli.command("config")
@click.pass_context
def cmd_config(ctx):
    """Display and validate current configuration."""
    config = _load_config(ctx.obj)
    print_header("Configuration")
    render_config_panel(config)

    async def _run():
        from rich.status import Status
        async with _make_client(config) as api:
            with Status("[cyan]Validating token…[/cyan]", console=console):
                valid = await api.check_token_validity()
        if valid:
            render_success("Token Valid", "API token is active.")
            return 0
        render_error(
            "Invalid Token",
            "Token is invalid or expired.\n"
            "[dim]Update it with:[/dim] [bold cyan]ctf set token <new_token>[/bold cyan]"
        )
        return 1

    sys.exit(asyncio.run(_run()))


@cli.command("set")
@click.argument("key")
@click.argument("value")
@click.pass_context
def cmd_set(ctx, key, value):
    """
    Update a single config value in the workspace .ctf_config.json.

    \b
    Keys (aliases accepted):
      token / ctf_token      — API token
      url   / ctf_url        — CTFd platform URL
      name  / ctf_name       — CTF event name
      timeout / api_timeout  — Request timeout in seconds
      retries / max_retries  — Max retry attempts
      poll  / poll_interval  — Scoreboard poll interval in seconds
      log   / log_level      — Log level (DEBUG/INFO/WARNING/ERROR)

    \b
    Examples:
      ctf set token ctfd_abc123...        # replace expired token
      ctf set url https://ctf.example.com # fix the base URL
      ctf set timeout 30                  # increase request timeout
      ctf set name "My CTF 2025"          # rename the event
    """
    try:
        canonical, written = update_workspace_config(key, value)
    except FileNotFoundError as e:
        render_error("Workspace Not Found", str(e))
        sys.exit(1)
    except ValueError as e:
        render_error("Invalid Key or Value", str(e))
        # Print the valid keys hint
        from rich.table import Table as RTable
        t = RTable(border_style="bright_black", header_style="bold cyan", show_header=True)
        t.add_column("Alias",     style="cyan",   width=16)
        t.add_column("Config Key", style="white",  width=16)
        for alias, canon in sorted(CONFIG_KEY_ALIASES.items()):
            if alias != canon:
                t.add_row(alias, canon)
        console.print(t)
        sys.exit(1)

    # Mask token in output
    display = (
        written[:12] + "..." + written[-4:]
        if canonical == "ctf_token" and len(str(written)) > 16
        else str(written)
    )

    console.print(
        f"\n[bold green]✔[/bold green]  [bold]{canonical}[/bold] "
        f"updated → [cyan]{display}[/cyan]\n"
    )
    console.print(
        "[dim]Run [bold]ctf config[/bold] to verify, "
        "or [bold]ctf list[/bold] to test the connection.[/dim]\n"
    )



@cli.command("categories")
@click.pass_context
def cmd_categories(ctx):
    """List all challenge categories with solve statistics."""
    config = _load_config(ctx.obj)

    async def _run():
        from rich.status import Status
        from rich.table import Table as RTable
        from collections import defaultdict

        async with _make_client(config) as api:
            scraper = ChallengeScraper(api)
            with Status("[cyan]Fetching…[/cyan]", console=console):
                try:
                    challenges = await scraper.fetch_challenges()
                except APIError as e:
                    render_error("Fetch Failed", str(e))
                    return 1

        groups = defaultdict(list)
        for ch in challenges:
            groups[ch.get("category", "Uncategorized")].append(ch)

        table = RTable(
            title="[bold cyan]📂 Categories[/bold cyan]",
            border_style="bright_black", header_style="bold cyan",
        )
        table.add_column("Category",  style="bold magenta", width=20)
        table.add_column("Total",     width=7,  justify="right")
        table.add_column("Solved",    style="green", width=7, justify="right")
        table.add_column("Remaining", style="red",   width=10, justify="right")
        table.add_column("Points",    style="yellow", width=10, justify="right")

        for cat in sorted(groups):
            chs    = groups[cat]
            solved = sum(1 for c in chs if c.get("solved_by_me"))
            pts    = sum(c.get("value", 0) for c in chs)
            table.add_row(cat, str(len(chs)), str(solved),
                          str(len(chs) - solved), str(pts))
        console.print(table)
        return 0

    sys.exit(asyncio.run(_run()))


if __name__ == "__main__":
    cli(prog_name="ctf")
