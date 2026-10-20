"""
cli.py
Command-Line Interface for fileorg.
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Optional

from . import __version__
from .organizer import FileOrganizer, MoveRecord
from .rules import DEFAULT_CATEGORIES, load_rules_from_file


def format_size(bytes_num: int) -> str:
    """Formats bytes into human readable format."""
    for unit in ["B", "KB", "MB", "GB"]:
        if abs(bytes_num) < 1024.0:
            return f"{bytes_num:3.1f} {unit}"
        bytes_num /= 1024.0
    return f"{bytes_num:.1f} TB"


def print_progress(record: MoveRecord) -> None:
    """Prints single move action."""
    status_symbols = {
        "moved": "[OK]",
        "dry_run": "[PREVIEW]",
        "skipped": "[SKIP]",
        "error": "[ERROR]",
    }
    symbol = status_symbols.get(record.status, "[INFO]")
    src_name = Path(record.source).name
    dest_dir = Path(record.destination).parent.name
    print(f"  {symbol} {src_name} -> {dest_dir}/ ({record.category})")
    if record.error_message:
        print(f"         Error: {record.error_message}")


def main(argv: Optional[list] = None) -> int:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="fileorg",
        description="fileorg: Automatic, intelligent file organizer for desktops and folders.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  fileorg                           # Organize current folder
  fileorg ~/Downloads               # Organize Downloads folder
  fileorg . --dry-run               # Preview changes without moving
  fileorg . --recursive             # Include files in subfolders
  fileorg . --by-date               # Group files inside category by Year/Month
  fileorg . --strategy skip         # Skip existing file names instead of renaming
  fileorg . --undo                  # Revert last organization
  fileorg . --config my_rules.json  # Use custom category rules
        """,
    )

    parser.add_argument(
        "path",
        nargs="?",
        default=".",
        help="Path to folder to organize (default: current directory)",
    )
    parser.add_argument(
        "-t", "--target",
        dest="target",
        default=None,
        help="Target folder to move organized files into (default: same as source)",
    )
    parser.add_argument(
        "-d", "--dry-run",
        action="store_true",
        help="Simulate and print actions without moving any files",
    )
    parser.add_argument(
        "-r", "--recursive",
        action="store_true",
        help="Recursively scan all subdirectories",
    )
    parser.add_argument(
        "--by-date",
        action="store_true",
        help="Group files by creation/modification date within category folders",
    )
    parser.add_argument(
        "-s", "--strategy",
        choices=["rename", "skip", "overwrite"],
        default="rename",
        help="Conflict resolution strategy when destination file exists (default: rename)",
    )
    parser.add_argument(
        "-u", "--undo",
        action="store_true",
        help="Undo the last organization run in the target directory",
    )
    parser.add_argument(
        "-c", "--config",
        dest="config",
        default=None,
        help="Path to custom JSON configuration for extension-to-category rules",
    )
    parser.add_argument(
        "-q", "--quiet",
        action="store_true",
        help="Suppress itemized move output",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output summary results in JSON format",
    )
    parser.add_argument(
        "-v", "--version",
        action="version",
        version=f"fileorg {__version__}",
    )

    args = parser.parse_args(argv)

    target_path = Path(args.target or args.path).resolve()

    # Handle Undo
    if args.undo:
        try:
            reverted, failed, errors = FileOrganizer.undo(target_path)
            if args.json:
                print(json.dumps({"status": "undo", "reverted": reverted, "failed": failed, "errors": errors}, indent=2))
            else:
                print(f"\n[fileorg Undo] Reverted {reverted} file(s) in: {target_path}")
                if failed > 0:
                    print(f"Warning: Failed to revert {failed} file(s).")
                    for err in errors:
                        print(f"  - {err}")
            return 0 if failed == 0 else 1
        except Exception as e:
            if args.json:
                print(json.dumps({"status": "error", "message": str(e)}))
            else:
                print(f"Error executing undo: {e}", file=sys.stderr)
            return 1

    # Load custom rules if specified
    custom_rules = None
    if args.config:
        try:
            custom_rules = load_rules_from_file(args.config)
        except Exception as e:
            print(f"Error loading config file '{args.config}': {e}", file=sys.stderr)
            return 1

    source_path = Path(args.path).resolve()
    if not source_path.exists():
        print(f"Error: Source directory does not exist: {source_path}", file=sys.stderr)
        return 1

    if not source_path.is_dir():
        print(f"Error: Specified path is not a directory: {source_path}", file=sys.stderr)
        return 1

    if not args.json and not args.quiet:
        mode_str = " (DRY-RUN PREVIEW)" if args.dry_run else ""
        print(f"\n=======================================================")
        print(f"  fileorg v{__version__} - Organizing Files{mode_str}")
        print(f"  Source: {source_path}")
        if args.target:
            print(f"  Target: {target_path}")
        print(f"=======================================================\n")

    progress_cb = None if (args.quiet or args.json) else print_progress

    organizer = FileOrganizer(
        source_dir=source_path,
        target_dir=target_path,
        categories=custom_rules,
        conflict_strategy=args.strategy,
        dry_run=args.dry_run,
        recursive=args.recursive,
        by_date=args.by_date,
        on_progress=progress_cb,
    )

    try:
        summary = organizer.organize()
    except Exception as e:
        if args.json:
            print(json.dumps({"status": "error", "message": str(e)}))
        else:
            print(f"Error during organization: {e}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(summary.to_dict(), indent=2))
        return 0

    # Print Summary Report
    print("\n-------------------------------------------------------")
    print("  Organization Summary:")
    print(f"  Scanned Files: {summary.total_files_scanned}")
    action_label = "Would Move" if args.dry_run else "Moved"
    print(f"  {action_label}:        {summary.total_moved}")
    if summary.total_skipped > 0:
        print(f"  Skipped:       {summary.total_skipped}")
    if summary.total_errors > 0:
        print(f"  Errors:        {summary.total_errors}")

    if summary.category_counts:
        print("\n  Categorized Breakdown:")
        for cat, count in sorted(summary.category_counts.items(), key=lambda x: x[0]):
            print(f"    - {cat:15}: {count} file(s)")

    print("-------------------------------------------------------\n")
    if args.dry_run:
        print("Note: This was a dry run. No files were moved. Run without --dry-run to organize.\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
