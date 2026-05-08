"""
Writeup Exporter Module (v3.0)
Automates the generation of a comprehensive Markdown writeup for all solved
challenges in a CTF workspace.

Design:
  - Scans workspace for .challenge.json files.
  - Filters for challenges marked as "solved" (solved: true or flag is present).
  - Groups challenges by category.
  - Concatenates README.md and solve.py (or notes.txt) into a single Markdown file.
  - Gracefully handles missing files without crashing.
"""

import json
import logging
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

logger = logging.getLogger(__name__)

CHALLENGE_META_FILENAME = ".challenge.json"


def _read_file_safe(path: Path) -> str:
    """Read a file's content safely, returning an empty string if missing."""
    if not path.exists() or not path.is_file():
        return ""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except OSError as e:
        logger.warning(f"Failed to read {path}: {e}")
        return ""


def export_writeups(workspace_root: Path, output_file: Path) -> Tuple[bool, int, Dict[str, int]]:
    """
    Export solved challenges into a single Markdown writeup file.

    Args:
        workspace_root: Path to the CTF workspace directory.
        output_file:    Path to save the generated writeup markdown file.

    Returns:
        (success_bool, total_exported, category_stats_dict)
    """
    workspace_root = Path(workspace_root)
    output_file = Path(output_file)

    # 1. Scan and parse metadata
    solved_challenges: List[Dict[str, Any]] = []

    for meta_file in workspace_root.rglob(CHALLENGE_META_FILENAME):
        try:
            with open(meta_file, "r", encoding="utf-8") as f:
                meta = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Could not read metadata {meta_file}: {e}")
            continue

        # Check if solved
        is_solved = meta.get("solved") is True or bool(meta.get("flag"))
        if is_solved:
            meta["_dir"] = meta_file.parent
            solved_challenges.append(meta)

    if not solved_challenges:
        logger.info("No solved challenges found to export.")
        return False, 0, {}

    # 2. Group by category
    grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for ch in solved_challenges:
        cat = ch.get("category", "Uncategorized").title()
        grouped[cat].append(ch)

    # Sort categories alphabetically, and challenges by name inside each
    sorted_categories = sorted(grouped.keys())
    for cat in sorted_categories:
        grouped[cat].sort(key=lambda x: x.get("name", ""))

    # 3. Generate Markdown content
    lines = [
        "# CTF Writeups",
        f"\n*Generated automatically on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*",
        "\n---"
    ]

    total_exported = 0
    stats: Dict[str, int] = {}

    for cat in sorted_categories:
        challenges = grouped[cat]
        stats[cat] = len(challenges)
        
        lines.append(f"\n## {cat}\n")

        for ch in challenges:
            name = ch.get("name", "Unknown").replace("-", " ").replace("_", " ").title()
            ch_dir: Path = ch["_dir"]
            
            lines.append(f"### {name}\n")
            
            # Append README.md
            readme_path = ch_dir / "README.md"
            readme_content = _read_file_safe(readme_path)
            if readme_content:
                lines.append(readme_content)
                lines.append("\n")
            else:
                lines.append("*No README.md found.*\n")

            # Append solve.py or notes.txt
            solve_path = ch_dir / "solve.py"
            notes_path = ch_dir / "notes.txt"
            
            if solve_path.exists():
                code = _read_file_safe(solve_path)
                if code:
                    lines.append("#### Solution Script (`solve.py`)")
                    lines.append("```python")
                    lines.append(code)
                    lines.append("```\n")
            elif notes_path.exists():
                notes = _read_file_safe(notes_path)
                if notes:
                    lines.append("#### Notes (`notes.txt`)")
                    lines.append("```text")
                    lines.append(notes)
                    lines.append("```\n")

            lines.append("---\n")
            total_exported += 1

    # 4. Write to output file
    try:
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        logger.info(f"Successfully exported {total_exported} writeups to {output_file}")
        return True, total_exported, dict(stats)
    except OSError as e:
        logger.error(f"Failed to write export file to {output_file}: {e}")
        return False, total_exported, dict(stats)
