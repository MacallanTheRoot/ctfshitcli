"""
Flag Submitter Module
Handles single and bulk flag submissions with rate-limit safeguards (jitter).
"""

import asyncio
import csv
import logging
import random
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from src.api_client import CTFdAPIClient, APIError
from src.ui_renderer import (
    render_flag_result,
    render_bulk_submission_summary,
    render_error,
    print_loading,
    clear_line,
)

logger = logging.getLogger(__name__)


class FlagSubmissionResult:
    """Represents the result of a flag submission."""

    def __init__(
        self,
        challenge_id: int,
        challenge_name: str,
        flag: str,
        success: bool,
        correct: Optional[bool] = None,
        message: str = "",
        error: Optional[str] = None,
        status: str = "",
    ):
        """
        Initialize submission result.

        Args:
            challenge_id:   Challenge ID.
            challenge_name: Challenge name.
            flag:           Flag that was submitted.
            success:        Whether the HTTP request succeeded.
            correct:        Whether the flag was correct.
            message:        Human-readable message from CTFd.
            error:          Error string if submission raised an exception.
            status:         Raw CTFd status string (correct|incorrect|already_solved|…).
        """
        self.challenge_id   = challenge_id
        self.challenge_name = challenge_name
        self.flag           = flag
        self.success        = success
        self.correct        = correct
        self.message        = message
        self.error          = error
        self.status         = status

    def __repr__(self) -> str:
        state = self.status or ("correct" if self.correct else "rejected")
        return f"<FlagResult #{self.challenge_id}: {state}>"


class FlagSubmitter:
    """
    Handles single and bulk flag submissions to CTFd.
    Implements jitter-based rate limiting to avoid bans.
    """

    # Jitter parameters (seconds)
    MIN_JITTER = 0.5
    MAX_JITTER = 3.0

    def __init__(self, api_client: CTFdAPIClient):
        """
        Initialize FlagSubmitter.

        Args:
            api_client: Initialized CTFdAPIClient instance.
        """
        self.api_client = api_client

    async def submit_single_flag(
        self, challenge_id: int, flag: str
    ) -> FlagSubmissionResult:
        """
        Submit a single flag for a challenge.

        Args:
            challenge_id: Target challenge ID.
            flag: Flag string to submit.

        Returns:
            FlagSubmissionResult with submission details.
        """
        logger.info(f"Submitting flag for challenge {challenge_id}")

        try:
            # Fetch challenge name (best-effort — don't fail submission if it errors)
            try:
                challenge_info = await self.api_client.get_challenge(challenge_id)
                challenge_name = challenge_info.get("name", f"Challenge #{challenge_id}")
            except APIError:
                challenge_name = f"Challenge #{challenge_id}"

            # Submit the flag via the correct CTFd endpoint
            response = await self.api_client.submit_flag(challenge_id, flag)

            # Parse response from POST /api/v1/challenges/attempt
            # Response shape: {success: bool, data: {status: str, message: str}}
            success = response.get("success", False)
            data    = response.get("data", {})

            # 'status' can be: 'correct', 'incorrect', 'already_solved', 'paused', 'ratelimited'
            status  = data.get("status", "")
            message = data.get("message", response.get("message", "No response message"))
            correct = status == "correct"

            logger.info(
                f"Flag submission for #{challenge_id}: status={status!r}"
            )

            return FlagSubmissionResult(
                challenge_id=challenge_id,
                challenge_name=challenge_name,
                flag=flag,
                success=success,
                correct=correct,
                message=message,
                status=status,
            )

        except APIError as e:
            logger.error(f"Error submitting flag for challenge {challenge_id}: {e}")
            return FlagSubmissionResult(
                challenge_id=challenge_id,
                challenge_name=f"Challenge #{challenge_id}",
                flag=flag,
                success=False,
                correct=False,
                message="",
                error=str(e),
            )

    async def submit_bulk_flags(
        self,
        csv_file_path: Path,
        jitter: bool = True,
    ) -> Tuple[List[FlagSubmissionResult], Dict[str, int]]:
        """
        Submit multiple flags from a CSV file.
        CSV format: challenge_id, flag (with header row)

        Args:
            csv_file_path: Path to CSV file.
            jitter: Whether to add random delays between submissions.

        Returns:
            Tuple of (list of results, summary dict with counts).

        Raises:
            FileNotFoundError: If CSV file doesn't exist.
            ValueError: If CSV format is invalid.
        """
        csv_file_path = Path(csv_file_path)

        if not csv_file_path.exists():
            raise FileNotFoundError(f"CSV file not found: {csv_file_path}")

        logger.info(f"Reading flags from CSV: {csv_file_path}")

        # Parse CSV file
        flaglist: List[Tuple[int, str]] = []
        try:
            with open(csv_file_path, "r", encoding="utf-8") as f:
                reader = csv.reader(f)
                # Skip header row if it exists
                header = next(reader, None)
                if header and header[0].lower() in ("challenge_id", "id", "challenge"):
                    # It's a header row, proceed normally
                    pass
                elif header:
                    # It's not a header row, process it as data
                    try:
                        challenge_id = int(header[0])
                        flag = header[1]
                        flaglist.append((challenge_id, flag))
                    except (ValueError, IndexError):
                        logger.warning(f"Skipping malformed row: {header}")

                # Process remaining rows
                for row_num, row in enumerate(reader, start=2):
                    if not row or not row[0].strip():
                        continue

                    try:
                        challenge_id = int(row[0].strip())
                        flag = row[1].strip() if len(row) > 1 else ""

                        if not flag:
                            logger.warning(f"Row {row_num}: Empty flag, skipping")
                            continue

                        flaglist.append((challenge_id, flag))

                    except (ValueError, IndexError) as e:
                        logger.warning(f"Row {row_num}: Malformed data, skipping: {e}")
                        continue

        except Exception as e:
            raise ValueError(f"Error reading CSV file: {e}")

        if not flaglist:
            raise ValueError("No valid flags found in CSV file")

        logger.info(f"Parsed {len(flaglist)} flags from CSV")

        # Submit flags with jitter
        results: List[FlagSubmissionResult] = []
        summary = {
            "total": len(flaglist),
            "successful": 0,
            "failed": 0,
            "skipped": 0,
        }

        print_loading(f"Submitting {len(flaglist)} flags with jitter...")

        for idx, (challenge_id, flag) in enumerate(flaglist, start=1):
            # Add jitter delay before submission (except for first one)
            if idx > 1 and jitter:
                delay = random.uniform(self.MIN_JITTER, self.MAX_JITTER)
                logger.debug(f"Jitter delay: {delay:.2f}s before submission {idx}")
                await asyncio.sleep(delay)

            # Submit flag
            result = await self.submit_single_flag(challenge_id, flag)
            results.append(result)

            # Track statistics
            if result.error:
                summary["skipped"] += 1
            elif result.correct:
                summary["successful"] += 1
            else:
                summary["failed"] += 1

            # Progress update
            print_loading(
                f"Submitting flags... ({idx}/{len(flaglist)}) "
                f"[✓{summary['successful']} ✗{summary['failed']} ⊘{summary['skipped']}]"
            )

        clear_line()
        logger.info(
            f"Bulk submission completed: "
            f"{summary['successful']} correct, {summary['failed']} incorrect, "
            f"{summary['skipped']} errors"
        )

        return results, summary

    def display_single_result(self, result: FlagSubmissionResult) -> None:
        """
        Display result of a single flag submission.

        Args:
            result: FlagSubmissionResult instance.
        """
        if result.error:
            render_error(
                f"Failed to submit flag for {result.challenge_name}",
                result.error,
            )
        else:
            render_flag_result(
                result.challenge_id,
                result.challenge_name,
                result.success,
                result.message,
                result.correct,
                result.status,
            )

    def display_bulk_results(
        self,
        results: List[FlagSubmissionResult],
        summary: Dict[str, int],
        show_details: bool = False,
    ) -> None:
        """
        Display bulk submission results.

        Args:
            results: List of FlagSubmissionResult.
            summary: Summary dict with counts.
            show_details: Whether to show detailed results for each flag.
        """
        render_bulk_submission_summary(
            summary["total"],
            summary["successful"],
            summary["failed"],
            summary["skipped"],
        )

        if show_details:
            print("\n[bold cyan]Detailed Results:[/bold cyan]")
            for result in results:
                status_emoji = (
                    "✓" if result.correct else "✗" if not result.error else "⚠"
                )
                status_text = (
                    "CORRECT" if result.correct else "REJECTED" if not result.error else "ERROR"
                )
                print(
                    f"  {status_emoji} #{result.challenge_id:3d}: {status_text:8s} | {result.message}"
                )
