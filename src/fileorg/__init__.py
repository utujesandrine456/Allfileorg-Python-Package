"""
fileorg
-------
An intelligent, fast, and automated file organization package for Python.
Organizes documents (.docx, .doc, .txt, .odt), PDFs, images, spreadsheets,
code, audio, video, archives, and other files into structured directories.
"""

from typing import Dict, List, Optional, Union
from pathlib import Path

from .rules import DEFAULT_CATEGORIES, build_extension_map, load_rules_from_file
from .organizer import FileOrganizer, MoveRecord, OrganizationSummary

__version__ = "1.0.0"
__author__ = "UWASE UTUJE Sandrine"
__all__ = [
    "FileOrganizer",
    "MoveRecord",
    "OrganizationSummary",
    "DEFAULT_CATEGORIES",
    "build_extension_map",
    "load_rules_from_file",
    "organize_directory",
    "undo_organization",
    "__version__",
]


def organize_directory(
    source_dir: Union[str, Path] = ".",
    target_dir: Optional[Union[str, Path]] = None,
    categories: Optional[Dict[str, List[str]]] = None,
    conflict_strategy: str = "rename",
    dry_run: bool = False,
    recursive: bool = False,
    by_date: bool = False,
) -> OrganizationSummary:
    """
    Convenience function to organize files in a directory.

    :param source_dir: Directory containing files to organize (default: current directory).
    :param target_dir: Optional target directory. Defaults to source_dir.
    :param categories: Custom dictionary mapping folder names to extension lists.
    :param conflict_strategy: 'rename' (default), 'skip', or 'overwrite'.
    :param dry_run: If True, simulates moves without modifying disk.
    :param recursive: If True, recursively scans nested subdirectories.
    :param by_date: If True, creates subfolders by Year/Month inside categories.
    :return: OrganizationSummary object containing stats and move records.
    """
    organizer = FileOrganizer(
        source_dir=source_dir,
        target_dir=target_dir,
        categories=categories,
        conflict_strategy=conflict_strategy,
        dry_run=dry_run,
        recursive=recursive,
        by_date=by_date,
    )
    return organizer.organize()


def undo_organization(target_dir: Union[str, Path] = ".") -> tuple[int, int, list[str]]:
    """
    Convenience function to revert the last file organization in target_dir.

    :param target_dir: Directory to restore.
    :return: Tuple of (reverted_count, failed_count, error_messages).
    """
    return FileOrganizer.undo(target_dir)
