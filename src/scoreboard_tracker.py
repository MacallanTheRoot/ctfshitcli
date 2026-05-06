"""
Scoreboard Tracker Module
Asynchronously polls CTFd scoreboard and detects ranking changes.
"""

import asyncio
import logging
from typing import Any, Callable, Dict, List, Optional, Set

from src.api_client import CTFdAPIClient, APIError
from src.ui_renderer import render_alert, render_scoreboard_table

logger = logging.getLogger(__name__)


class RankingChange:
    """Represents a detected ranking change."""

    def __init__(
        self,
        team_name: str,
        previous_rank: Optional[int],
        current_rank: Optional[int],
        previous_score: int,
        current_score: int,
    ):
        """
        Initialize RankingChange.

        Args:
            team_name: Team name.
            previous_rank: Previous ranking position (None if new entry).
            current_rank: Current ranking position.
            previous_score: Previous score.
            current_score: Current score.
        """
        self.team_name = team_name
        self.previous_rank = previous_rank
        self.current_rank = current_rank
        self.previous_score = previous_score
        self.current_score = current_score

    def get_change_summary(self) -> str:
        """
        Get human-readable summary of the change.

        Returns:
            Change summary string.
        """
        if self.previous_rank is None:
            return f"New team: {self.team_name} entered scoreboard at rank #{self.current_rank}"

        if self.current_rank is None:
            return f"Team eliminated: {self.team_name} left the scoreboard"

        if self.current_rank < self.previous_rank:
            improvement = self.previous_rank - self.current_rank
            return (
                f"{self.team_name} moved up {improvement} positions "
                f"(#{self.previous_rank} → #{self.current_rank})"
            )
        elif self.current_rank > self.previous_rank:
            decline = self.current_rank - self.previous_rank
            return (
                f"{self.team_name} moved down {decline} positions "
                f"(#{self.previous_rank} → #{self.current_rank})"
            )
        else:
            score_change = self.current_score - self.previous_score
            return (
                f"{self.team_name} score changed: "
                f"{self.previous_score} → {self.current_score} (+{score_change})"
            )

    def __repr__(self) -> str:
        return f"<RankingChange {self.team_name}>"


class ScoreboardTracker:
    """
    Async scoreboard tracker for CTFd.
    Periodically polls scoreboard and detects ranking changes.
    """

    def __init__(
        self,
        api_client: CTFdAPIClient,
        poll_interval: int = 30,
        target_teams: Optional[List[str]] = None,
    ):
        """
        Initialize ScoreboardTracker.

        Args:
            api_client: Initialized CTFdAPIClient instance.
            poll_interval: Polling interval in seconds.
            target_teams: List of team names to track specifically.
        """
        self.api_client = api_client
        self.poll_interval = poll_interval
        self.target_teams = set(target_teams or [])

        # State tracking
        self._state: Dict[str, Dict[str, Any]] = {}  # team_name -> {rank, score, ...}
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._callbacks: List[Callable[[List[RankingChange]], None]] = []

    def add_callback(self, callback: Callable[[List[RankingChange]], None]) -> None:
        """
        Register a callback for ranking changes.

        Args:
            callback: Function to call with list of RankingChange objects.
        """
        self._callbacks.append(callback)
        logger.debug(f"Added callback: {callback.__name__}")

    def remove_callback(self, callback: Callable) -> None:
        """
        Unregister a callback.

        Args:
            callback: Callback function to remove.
        """
        if callback in self._callbacks:
            self._callbacks.remove(callback)
            logger.debug(f"Removed callback: {callback.__name__}")

    async def _poll_scoreboard(self) -> List[Dict[str, Any]]:
        """
        Fetch scoreboard from API.

        Returns:
            List of team scores.

        Raises:
            APIError: If API request fails.
        """
        return await self.api_client.get_scoreboard()

    async def _detect_changes(
        self, new_scoreboard: List[Dict[str, Any]]
    ) -> List[RankingChange]:
        """
        Detect ranking changes by comparing with previous state.

        Args:
            new_scoreboard: Current scoreboard from API.

        Returns:
            List of RankingChange objects.
        """
        changes: List[RankingChange] = []

        # Create new state dict
        new_state: Dict[str, Dict[str, Any]] = {}
        for rank, team in enumerate(new_scoreboard, start=1):
            team_name = team.get("name", f"Team #{team.get('id')}")
            new_state[team_name] = {
                "rank": rank,
                "score": team.get("score", 0),
                "data": team,
            }

        # Check for rank changes, eliminations, and new entries
        all_teams = set(self._state.keys()) | set(new_state.keys())

        for team_name in all_teams:
            old_info = self._state.get(team_name)
            new_info = new_state.get(team_name)

            # New team entered scoreboard
            if old_info is None and new_info is not None:
                if not self.target_teams or team_name in self.target_teams:
                    change = RankingChange(
                        team_name=team_name,
                        previous_rank=None,
                        current_rank=new_info["rank"],
                        previous_score=0,
                        current_score=new_info["score"],
                    )
                    changes.append(change)
                    logger.info(f"Change detected: {change.get_change_summary()}")

            # Team left scoreboard
            elif old_info is not None and new_info is None:
                if not self.target_teams or team_name in self.target_teams:
                    change = RankingChange(
                        team_name=team_name,
                        previous_rank=old_info["rank"],
                        current_rank=None,
                        previous_score=old_info["score"],
                        current_score=0,
                    )
                    changes.append(change)
                    logger.info(f"Change detected: {change.get_change_summary()}")

            # Team's rank or score changed
            elif old_info is not None and new_info is not None:
                rank_changed = old_info["rank"] != new_info["rank"]
                score_changed = old_info["score"] != new_info["score"]

                if rank_changed or score_changed:
                    if not self.target_teams or team_name in self.target_teams:
                        change = RankingChange(
                            team_name=team_name,
                            previous_rank=old_info["rank"],
                            current_rank=new_info["rank"],
                            previous_score=old_info["score"],
                            current_score=new_info["score"],
                        )
                        changes.append(change)
                        logger.info(f"Change detected: {change.get_change_summary()}")

        # Update state
        self._state = new_state

        return changes

    async def _polling_loop(self) -> None:
        """
        Main polling loop. Runs in background until stopped.
        """
        logger.info(f"Scoreboard polling started (interval: {self.poll_interval}s)")

        while self._running:
            try:
                # Poll scoreboard
                scoreboard = await self._poll_scoreboard()

                # Detect changes
                changes = await self._detect_changes(scoreboard)

                # Trigger callbacks if changes detected
                if changes:
                    logger.info(f"Detected {len(changes)} ranking change(s)")
                    for callback in self._callbacks:
                        try:
                            callback(changes)
                        except Exception as e:
                            logger.error(f"Error in callback {callback.__name__}: {e}")

                # Wait before next poll
                await asyncio.sleep(self.poll_interval)

            except APIError as e:
                logger.error(f"Failed to poll scoreboard: {e}")
                # Wait before retrying
                await asyncio.sleep(self.poll_interval)

            except asyncio.CancelledError:
                logger.info("Scoreboard polling cancelled")
                break

            except Exception as e:
                logger.exception(f"Unexpected error in polling loop: {e}")
                await asyncio.sleep(self.poll_interval)

        logger.info("Scoreboard polling stopped")

    async def start_polling(self) -> None:
        """
        Start background scoreboard polling.
        """
        if self._running:
            logger.warning("Scoreboard polling already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._polling_loop())
        logger.info("Scoreboard polling task created")

    async def stop_polling(self) -> None:
        """
        Stop background scoreboard polling gracefully.
        """
        if not self._running:
            logger.warning("Scoreboard polling not running")
            return

        self._running = False

        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        logger.info("Scoreboard polling stopped")

    def get_current_state(self) -> Dict[str, Dict[str, Any]]:
        """
        Get current cached scoreboard state.

        Returns:
            Dictionary mapping team names to their rank/score info.
        """
        return dict(self._state)

    async def fetch_and_display_scoreboard(self, limit: Optional[int] = None) -> None:
        """
        Fetch and display current scoreboard.

        Args:
            limit: Maximum number of teams to display.
        """
        try:
            logger.info("Fetching scoreboard for display")
            scoreboard = await self._poll_scoreboard()
            render_scoreboard_table(scoreboard, limit=limit)
        except APIError as e:
            logger.error(f"Failed to fetch scoreboard: {e}")
            render_alert(
                "Scoreboard Fetch Error",
                f"Failed to fetch scoreboard: {e}",
                "error",
            )

    def get_team_position(self, team_name: str) -> Optional[Dict[str, Any]]:
        """
        Get a team's current position.

        Args:
            team_name: Team name to lookup.

        Returns:
            Dictionary with rank and score, or None if not on scoreboard.
        """
        return self._state.get(team_name)

    async def is_polling(self) -> bool:
        """
        Check if polling is currently active.

        Returns:
            True if polling is running, False otherwise.
        """
        return self._running


# Default callback implementation for alerts
def default_change_callback(changes: List[RankingChange]) -> None:
    """
    Default callback for ranking changes - displays alerts.

    Args:
        changes: List of RankingChange objects.
    """
    for change in changes:
        summary = change.get_change_summary()

        # Determine alert type based on change
        if change.current_rank is None:
            alert_type = "warning"
            title = "Team Eliminated"
        elif change.previous_rank is None:
            alert_type = "info"
            title = "New Team Entry"
        elif change.current_rank < change.previous_rank:
            alert_type = "warning"
            title = "Team Ranked Up"
        else:
            alert_type = "info"
            title = "Ranking Changed"

        render_alert(title, summary, alert_type)
