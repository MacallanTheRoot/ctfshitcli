"""
Challenge Scraper Module
Fetches and caches challenges from CTFd, with filtering and display capabilities.
"""

import logging
import time
from typing import Any, Dict, List, Optional

from src.api_client import CTFdAPIClient, APIError
from src.ui_renderer import (
    render_challenges_table,
    render_error,
    render_info,
    print_loading,
    clear_line,
)

logger = logging.getLogger(__name__)


class ChallengeScraper:
    """
    Challenge Scraper for CTFd.
    Fetches challenges, manages caching, filtering, and rendering.
    """

    # Cache expiration time (5 minutes)
    CACHE_EXPIRY = 300

    def __init__(self, api_client: CTFdAPIClient):
        """
        Initialize ChallengeScraper.

        Args:
            api_client: Initialized CTFdAPIClient instance.
        """
        self.api_client = api_client
        self._cache: Optional[List[Dict[str, Any]]] = None
        self._cache_timestamp: float = 0

    async def fetch_challenges(self, use_cache: bool = True) -> List[Dict[str, Any]]:
        """
        Fetch all challenges from CTFd.

        Args:
            use_cache: Whether to use cached results if available.

        Returns:
            List of challenge dictionaries.

        Raises:
            APIError: If API request fails.
        """
        # Return cached data if available and fresh
        if use_cache and self._is_cache_valid():
            logger.debug("Returning cached challenges")
            return self._cache

        try:
            logger.info("Fetching challenges from CTFd API")
            challenges = await self.api_client.get_challenges()
            
            # Cache the results
            self._cache = challenges
            self._cache_timestamp = time.time()
            
            logger.info(f"Successfully fetched {len(challenges)} challenges")
            return challenges

        except APIError as e:
            logger.error(f"Failed to fetch challenges: {e}")
            raise

    async def get_challenges_by_category(
        self, category: str, use_cache: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Fetch challenges filtered by category.

        Args:
            category: Category name to filter by.
            use_cache: Whether to use cached results.

        Returns:
            List of challenges in the specified category.

        Raises:
            APIError: If API request fails.
        """
        all_challenges = await self.fetch_challenges(use_cache=use_cache)
        filtered = [
            c for c in all_challenges
            if c.get("category", "").lower() == category.lower()
        ]
        logger.info(f"Found {len(filtered)} challenges in category '{category}'")
        return filtered

    async def get_challenge_by_id(self, challenge_id: int) -> Optional[Dict[str, Any]]:
        """
        Get a specific challenge by ID.

        Args:
            challenge_id: Challenge ID.

        Returns:
            Challenge dictionary or None if not found.

        Raises:
            APIError: If API request fails.
        """
        try:
            return await self.api_client.get_challenge(challenge_id)
        except APIError as e:
            logger.error(f"Failed to fetch challenge {challenge_id}: {e}")
            raise

    def _is_cache_valid(self) -> bool:
        """
        Check if cached data is still valid.

        Returns:
            True if cache exists and hasn't expired.
        """
        if self._cache is None:
            return False

        age = time.time() - self._cache_timestamp
        is_valid = age < self.CACHE_EXPIRY

        if not is_valid:
            logger.debug(f"Cache expired (age: {age:.1f}s > {self.CACHE_EXPIRY}s)")

        return is_valid

    def invalidate_cache(self) -> None:
        """Manually invalidate the challenge cache."""
        self._cache = None
        self._cache_timestamp = 0
        logger.debug("Challenge cache invalidated")

    async def display_challenges(
        self,
        category: Optional[str] = None,
        show_files: bool = True,
        use_cache: bool = True,
    ) -> None:
        """
        Fetch and display challenges in a formatted table.

        Args:
            category: Optional category filter.
            show_files: Whether to include file information.
            use_cache: Whether to use cached results.
        """
        try:
            print_loading("Fetching challenges...")

            # Fetch challenges
            if category:
                challenges = await self.get_challenges_by_category(
                    category, use_cache=use_cache
                )
            else:
                challenges = await self.fetch_challenges(use_cache=use_cache)

            clear_line()

            if not challenges:
                render_info("No challenges found")
                return

            # Render the table
            render_challenges_table(challenges, show_files=show_files)

            # Display summary
            solved = sum(1 for c in challenges if c.get("solved_by_me"))
            total = len(challenges)
            print(f"\n[cyan]Summary:[/cyan] {solved}/{total} challenges solved")

        except APIError as e:
            render_error("Failed to fetch challenges", str(e))

    async def get_categories(self) -> List[str]:
        """
        Get unique challenge categories.

        Returns:
            List of unique category names.

        Raises:
            APIError: If API request fails.
        """
        challenges = await self.fetch_challenges()
        categories = sorted(
            set(c.get("category", "Other") for c in challenges if c.get("category"))
        )
        return categories

    async def display_categories(self) -> None:
        """Fetch and display available challenge categories."""
        try:
            categories = await self.get_categories()

            if not categories:
                render_info("No categories available")
                return

            print("\n[bold cyan]Available Challenge Categories:[/bold cyan]")
            for idx, category in enumerate(categories, start=1):
                print(f"  {idx}. {category}")
            print()

        except APIError as e:
            render_error("Failed to fetch categories", str(e))

    async def get_statistics(self) -> Dict[str, Any]:
        """
        Get challenge statistics.

        Returns:
            Dictionary with stats: total_challenges, total_points, solved, etc.

        Raises:
            APIError: If API request fails.
        """
        challenges = await self.fetch_challenges()

        solved = [c for c in challenges if c.get("solved_by_me")]
        unsolved = [c for c in challenges if not c.get("solved_by_me")]

        total_points = sum(c.get("value", 0) for c in challenges)
        earned_points = sum(c.get("value", 0) for c in solved)
        possible_points = sum(c.get("value", 0) for c in unsolved)

        categories = set(c.get("category") for c in challenges if c.get("category"))

        return {
            "total_challenges": len(challenges),
            "solved_challenges": len(solved),
            "unsolved_challenges": len(unsolved),
            "categories": len(categories),
            "total_points": total_points,
            "earned_points": earned_points,
            "possible_points": possible_points,
            "completion_percent": (
                (len(solved) / len(challenges) * 100) if challenges else 0
            ),
        }

    async def display_statistics(self) -> None:
        """Display challenge statistics."""
        try:
            stats = await self.get_statistics()

            print("\n[bold cyan]Challenge Statistics:[/bold cyan]")
            print(f"  [green]✓ Solved:[/green] {stats['solved_challenges']}/{stats['total_challenges']}")
            print(f"  [cyan]Categories:[/cyan] {stats['categories']}")
            print(f"  [yellow]Points:[/yellow] {stats['earned_points']}/{stats['total_points']}")
            print(f"  [magenta]Completion:[/magenta] {stats['completion_percent']:.1f}%\n")

        except APIError as e:
            render_error("Failed to fetch statistics", str(e))
