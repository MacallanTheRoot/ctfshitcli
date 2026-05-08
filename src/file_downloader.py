"""
File Downloader Module
Handles downloading challenge attachments from CTFd via async streaming.

Design:
  - download_challenge_files() fetches challenge details, extracts file URLs,
    and downloads each to the destination directory.
  - Uses aiohttp streaming for memory-efficient large file handling.
  - Rich progress bar per file, with overall summary on completion.
  - Handles both relative CTFd paths (/files/...) and absolute URLs.
  - show_progress=False path downloads silently — used by 'pull --all' to
    avoid nested rich Live context conflicts with the outer Progress bar.

v3.0 additions:
  - extract (bool): unpack .zip / .tar.gz into dest_dir after download.
  - delete_archive (bool): remove the archive after extraction (default: keep).
"""

import logging
import re
import tarfile
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import aiohttp
from rich.console import Console
from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
    TransferSpeedColumn,
)

from src.api_client import CTFdAPIClient, APIError

logger = logging.getLogger(__name__)
console = Console()

# Default chunk size for streaming (64 KB)
CHUNK_SIZE = 65536


def _extract_archive(archive_path: Path, dest_dir: Path, delete_after: bool = False, password: Optional[str] = None) -> List[Path]:
    """
    Extract a .zip or .tar.gz archive into dest_dir.

    Performs a safety check to prevent path-traversal attacks (zip-slip):
    all extracted members must resolve inside dest_dir.

    Args:
        archive_path: Path to the downloaded archive file.
        dest_dir:     Destination directory for extracted files.
        delete_after: If True, delete the archive file after extraction.

    Returns:
        List of Paths for extracted files.

    Raises:
        ValueError: If the archive type is unsupported.
        Exception:  If extraction fails.
    """
    name   = archive_path.name.lower()
    is_zip = name.endswith(".zip")
    is_tar = name.endswith((".tar.gz", ".tgz", ".tar.bz2", ".tar.xz"))

    if not (is_zip or is_tar):
        raise ValueError(f"Unsupported archive format: {archive_path.name}")

    extracted: List[Path] = []
    dest_dir = dest_dir.resolve()

    try:
        if is_zip:
            with zipfile.ZipFile(archive_path, "r") as zf:
                if password:
                    zf.setpassword(password.encode("utf-8"))
                for member in zf.infolist():
                    target = (dest_dir / member.filename).resolve()
                    # zip-slip guard
                    if not str(target).startswith(str(dest_dir)):
                        logger.warning(f"Skipping unsafe zip member: {member.filename}")
                        continue
                    try:
                        zf.extract(member, dest_dir)
                    except RuntimeError as e:
                        if 'password' in str(e).lower() or 'bad password' in str(e).lower():
                            logger.error(f"Failed to extract {member.filename}: Incorrect or missing password.")
                            console.print(f"  [yellow]⚠ Archive might be password protected: {archive_path.name}[/yellow]")
                        raise e
                    extracted.append(target)
        else:  # tar.*
            with tarfile.open(archive_path, "r:*") as tf:
                for member in tf.getmembers():
                    target = (dest_dir / member.name).resolve()
                    # tar-slip guard
                    if not str(target).startswith(str(dest_dir)):
                        logger.warning(f"Skipping unsafe tar member: {member.name}")
                        continue
                    tf.extract(member, dest_dir)
                    extracted.append(target)

        logger.info(
            f"Extracted {len(extracted)} item(s) from {archive_path.name} → {dest_dir}"
        )

        if delete_after:
            archive_path.unlink()
            logger.info(f"Deleted archive: {archive_path.name}")

    except Exception as e:
        logger.error(f"Extraction failed for {archive_path.name}: {e}")
        raise

    return extracted


def _resolve_file_url(base_url: str, file_url: str) -> str:
    """
    Resolve a CTFd file URL to an absolute URL.

    CTFd returns file paths like:
        /files/<hash>/challenge.zip?token=...
    or full URLs like:
        https://cdn.ctf.example.com/files/...
    """
    if file_url.startswith(("http://", "https://")):
        return file_url
    base = base_url.rstrip("/")
    path = file_url if file_url.startswith("/") else f"/{file_url}"
    return f"{base}{path}"


def _extract_filename(file_url: str, fallback: str = "download") -> str:
    """Extract a safe filename from a URL, stripping query strings."""
    parsed   = urlparse(file_url)
    name     = Path(parsed.path).name
    if not name or not re.search(r"\.", name):
        return fallback
    return name


async def download_file(
    session: aiohttp.ClientSession,
    url: str,
    dest_path: Path,
    headers: Optional[Dict[str, str]] = None,
    progress: Optional[Progress] = None,
    task_id: Optional[Any] = None,
    chunk_size: int = CHUNK_SIZE,
) -> Path:
    """
    Stream-download a single file from `url` to `dest_path`.

    Args:
        session:    Active aiohttp session.
        url:        File URL to download.
        dest_path:  Local path to write to.
        headers:    Optional additional request headers.
        progress:   Optional rich Progress instance for live updates.
        task_id:    Task ID in the Progress instance.
        chunk_size: Streaming chunk size in bytes.

    Returns:
        Path to the downloaded file.

    Raises:
        APIError: If the download fails (HTTP error or network issue).
    """
    req_headers = headers or {}
    try:
        async with session.get(url, headers=req_headers, allow_redirects=True) as resp:
            if resp.status >= 400:
                raise APIError(f"Download failed for {url}: HTTP {resp.status}")

            total = int(resp.headers.get("Content-Length", 0)) or None
            if progress and task_id is not None and total:
                progress.update(task_id, total=total)

            dest_path.parent.mkdir(parents=True, exist_ok=True)
            with open(dest_path, "wb") as f:
                async for chunk in resp.content.iter_chunked(chunk_size):
                    f.write(chunk)
                    if progress and task_id is not None:
                        progress.update(task_id, advance=len(chunk))

        logger.info(f"Downloaded: {dest_path.name} ({dest_path.stat().st_size} bytes)")
        return dest_path

    except aiohttp.ClientError as e:
        raise APIError(f"Network error downloading {url}: {e}") from e


async def download_challenge_files(
    api_client: CTFdAPIClient,
    challenge_id: int,
    dest_dir: Path,
    overwrite: bool = False,
    show_progress: bool = True,
    extract: bool = False,
    delete_archive: bool = False,
) -> List[Path]:
    """
    Fetch challenge details from CTFd and download all attached files.

    Args:
        api_client:     Initialized CTFdAPIClient (session must be open).
        challenge_id:   CTFd challenge ID.
        dest_dir:       Local directory to save files into.
        overwrite:      If False, skip files that already exist.
        show_progress:  If True (default), display per-file progress bars and
                        header output. Set to False when called from 'pull --all'
                        to avoid nested rich Live context conflicts.
        extract:        If True, unpack .zip / .tar.gz files after download.
        delete_archive: If True (and extract=True), remove archive after extraction.

    Returns:
        List of Paths for successfully downloaded files.

    Raises:
        APIError:   If challenge fetch fails or the session is not open.
        ValueError: If challenge has no attached files.
    """
    dest_dir = Path(dest_dir).resolve()
    dest_dir.mkdir(parents=True, exist_ok=True)

    logger.info(f"Fetching challenge #{challenge_id} details for file download")
    challenge = await api_client.get_challenge(challenge_id)

    files: List[str] = challenge.get("files", [])
    if not files:
        raise ValueError(
            f"Challenge #{challenge_id} ({challenge.get('name', '?')}) "
            f"has no attached files."
        )

    if show_progress:
        console.print(
            f"\n[bold cyan]📥 Downloading {len(files)} file(s) "
            f"for challenge #{challenge_id}: "
            f"[green]{challenge.get('name')}[/green][/bold cyan]"
        )

    session = api_client.session
    if session is None:
        raise APIError(
            "API client session is not open. "
            "Call download_challenge_files within 'async with api_client'."
        )

    base_url         = api_client.base_url
    auth_headers     = api_client._get_headers()
    download_headers = {k: v for k, v in auth_headers.items() if k != "Content-Type"}

    downloaded: List[Path] = []
    failed:     List[str]  = []

    # ── WITH progress bars (single-challenge mode) ────────────────────────────
    if show_progress:
        with Progress(
            SpinnerColumn(style="cyan"),
            TextColumn("[bold blue]{task.fields[filename]}", justify="right"),
            BarColumn(bar_width=30, style="cyan", complete_style="green"),
            DownloadColumn(),
            TransferSpeedColumn(),
            TimeElapsedColumn(),
            console=console,
            transient=False,
        ) as progress:
            for raw_url in files:
                abs_url   = _resolve_file_url(base_url, raw_url)
                filename  = _extract_filename(abs_url, fallback=f"challenge_{challenge_id}_file")
                dest_path = dest_dir / filename

                if dest_path.exists() and not overwrite:
                    console.print(
                        f"  [yellow]⊘ Skipped[/yellow] {filename} "
                        f"[dim](already exists)[/dim]"
                    )
                    downloaded.append(dest_path)
                    continue

                task_id = progress.add_task("download", filename=filename, total=None)
                try:
                    path = await download_file(
                        session=session, url=abs_url, dest_path=dest_path,
                        headers=download_headers, progress=progress, task_id=task_id,
                    )
                    downloaded.append(path)
                    progress.update(task_id, description=f"[green]✓[/green] {filename}")
                except APIError as e:
                    logger.error(f"Failed to download {filename}: {e}")
                    failed.append(filename)
                    progress.update(task_id, description=f"[red]✗[/red] {filename}")
                    console.print(f"  [red]✗ Failed:[/red] {filename} — {e}")

        if downloaded:
            console.print(
                f"\n[green]✓ Downloaded {len(downloaded)} file(s) → {dest_dir}[/green]"
            )
        if failed:
            console.print(
                f"[red]✗ {len(failed)} file(s) failed: {', '.join(failed)}[/red]"
            )

    # ── WITHOUT progress bars (pull --all bulk mode) ──────────────────────────
    else:
        for raw_url in files:
            abs_url   = _resolve_file_url(base_url, raw_url)
            filename  = _extract_filename(abs_url, fallback=f"challenge_{challenge_id}_file")
            dest_path = dest_dir / filename

            if dest_path.exists() and not overwrite:
                downloaded.append(dest_path)
                continue

            try:
                path = await download_file(
                    session=session, url=abs_url, dest_path=dest_path,
                    headers=download_headers,
                )
                downloaded.append(path)
                logger.info(f"[pull-all] Downloaded: {filename}")
            except APIError as e:
                logger.error(f"[pull-all] Failed to download {filename}: {e}")
                failed.append(filename)

    # ── Extraction ────────────────────────────────────────────────────────────
    if extract and downloaded:
        # Search for password in description
        archive_password = None
        description = challenge.get("description")
        if description:
            pwd_match = re.search(r"(?:parola|şifre|password|zip şifresi)\s*[:=]\s*([A-Za-z0-9!@#$%^&*()_+={}\[\]|\\:;\"'<>,.?/-]+)", description, re.IGNORECASE)
            if pwd_match:
                archive_password = pwd_match.group(1).strip()
                console.print(f"  [bold magenta]🔑 Soru açıklamasında arşiv şifresi bulundu: '{archive_password}'[/bold magenta]")

        final_downloaded: List[Path] = []
        for dl_path in downloaded:
            name = dl_path.name.lower()
            if name.endswith((".zip", ".tar.gz", ".tgz", ".tar.bz2", ".tar.xz")):
                try:
                    extracted_files = _extract_archive(dl_path, dest_dir, delete_after=delete_archive, password=archive_password)
                    final_downloaded.extend(extracted_files)
                    if show_progress:
                        console.print(f"  [green]✓ Extracted[/green] {dl_path.name}")
                    # If not deleted, we might still want to keep the archive in the list
                    if not delete_archive:
                        final_downloaded.append(dl_path)
                except Exception as e:
                    final_downloaded.append(dl_path)
                    if show_progress:
                        console.print(f"  [red]✗ Extraction failed[/red] {dl_path.name} — {e}")
            else:
                final_downloaded.append(dl_path)
        downloaded = final_downloaded

    # ── Description Update ────────────────────────────────────────────────────
    description = challenge.get("description")
    if description:
        readme_path = dest_dir / "README.md"
        if readme_path.exists():
            try:
                content = readme_path.read_text(encoding="utf-8")
                placeholder = "<!-- Paste the challenge description here -->"
                if placeholder in content:
                    content = content.replace(placeholder, description)
                    readme_path.write_text(content, encoding="utf-8")
                    logger.info(f"Updated README.md with description for challenge #{challenge_id}")
            except Exception as e:
                logger.error(f"Failed to update README.md description: {e}")
        else:
            desc_path = dest_dir / "challenge_description.md"
            try:
                desc_path.write_text(description, encoding="utf-8")
                logger.info(f"Created challenge_description.md for challenge #{challenge_id}")
            except Exception as e:
                logger.error(f"Failed to create challenge_description.md: {e}")

    return downloaded
