"""
Discord Notifier Module (v3.0)
Sends flag-solved notifications to a Discord channel via webhook.

Design:
  - Completely independent of CTFdAPIClient (different base URL).
  - Uses a rich Discord embed for a polished look.
  - Fire-and-forget: errors are logged but never propagate to the caller,
    so a Discord outage never breaks the main CTF workflow.
  - send_flag_notification() is the single public entry point; called by
    both 'ctf submit' (on correct answer) and 'ctf watch' (on flag capture).
"""

import logging
from typing import Optional

import aiohttp

logger = logging.getLogger(__name__)

# Discord embed colour codes
_COLOUR_CORRECT = 0x57F287   # Green  — correct flag
_COLOUR_WATCH   = 0xFEE75C   # Yellow — auto-captured by watch daemon


async def send_flag_notification(
    webhook_url: str,
    challenge_name: str,
    challenge_id: int,
    category: str,
    points: int,
    flag: str,
    source: str = "submit",
) -> None:
    """
    Send a flag-solved notification to Discord via webhook embed.

    Args:
        webhook_url:     Discord incoming webhook URL.
        challenge_name:  Human-readable challenge name.
        challenge_id:    CTFd challenge ID.
        category:        Challenge category string.
        points:          Point value of the challenge.
        flag:            The correct flag that was submitted.
        source:          "submit" (manual) or "watch" (auto-captured daemon).
                         Controls the embed colour and footer text.
    """
    if not webhook_url:
        logger.debug("discord_webhook_url not configured — skipping notification")
        return

    colour  = _COLOUR_CORRECT if source == "submit" else _COLOUR_WATCH
    icon    = "🚩" if source == "submit" else "🤖"
    footer  = "CTFd CLI — ctf submit" if source == "submit" else "CTFd CLI — ctf watch daemon"

    embed = {
        "title": f"{icon} Challenge Solved!",
        "color": colour,
        "fields": [
            {"name": "Challenge",  "value": f"`{challenge_name}` (#{challenge_id})", "inline": True},
            {"name": "Category",   "value": category or "—",                          "inline": True},
            {"name": "Points",     "value": str(points),                              "inline": True},
            {"name": "Flag",       "value": f"||`{flag}`||",                          "inline": False},
        ],
        "footer": {"text": footer},
    }

    payload = {"embeds": [embed]}

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                webhook_url,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status == 204:
                    logger.info(
                        f"Discord notification sent for '{challenge_name}' "
                        f"(source: {source})"
                    )
                else:
                    body = await resp.text()
                    logger.warning(
                        f"Discord webhook returned HTTP {resp.status}: {body[:200]}"
                    )
    except aiohttp.ClientError as e:
        logger.warning(f"Discord notification failed (network): {e}")
    except Exception as e:
        logger.warning(f"Discord notification failed (unexpected): {e}")
