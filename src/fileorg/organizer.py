"""
organizer.py
Core file organization engine for fileorg.
"""

from dataclasses import dataclass, field
from datetime import datetime
import json
import os
from pathlib import Path
import shutil
from typing import Callable, Dict, List, Optional, Tuple, Union

from .rules import DEFAULT_CATEGORIES, build_extension_map


HISTORY_FILENAME = ".fileorg_history.json"
IGNORED_SYSTEM_FILES = {
    ".ds_store",
    "thumbs.db",
    "desktop.ini",
    HISTORY_FILENAME.lower(),
}


@dataclass
class MoveRecord:
    """Represents a single file move action."""
    source: str
    destination: str
    category: str
    file_size: int = 0
    timestamp: str = ""
    status: str = "moved"  # moved, skipped, dry_run, error
    error_message: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "destination": self.destination,
            "category": self.category,
            "file_size": self.file_size,
            "timestamp": self.timestamp or datetime.now().isoformat(),
            "status": self.status,
            "error_message": self.error_message,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "MoveRecord":
        return cls(
            source=data["source"],
            destination=data["destination"],
            category=data.get("category", "Unknown"),
            file_size=data.get("file_size", 0),
            timestamp=data.get("timestamp", ""),
            status=data.get("status", "moved"),
            error_message=data.get("error_message"),
        )


@dataclass
class OrganizationSummary:
    """Summary of an organization run."""
    source_dir: str
    target_dir: str
    dry_run: bool
    total_files_scanned: int = 0
    total_moved: int = 0
    total_skipped: int = 0
    total_errors: int = 0
    category_counts: Dict[str, int] = field(default_factory=dict)
    records: List[MoveRecord] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "source_dir": self.source_dir,
            "target_dir": self.target_dir,
            "dry_run": self.dry_run,
            "total_files_scanned": self.total_files_scanned,
            "total_moved": self.total_moved,
            "total_skipped": self.total_skipped,
            "total_errors": self.total_errors,
            "category_counts": self.category_counts,
            "records": [r.to_dict() for r in self.records],
        }


class FileOrganizer:
    """
    High-performance, safe file organizer.
    Categorizes files by extension and moves them into appropriate folders.
    """

    def __init__(
        self,
        source_dir: Union[str, Path] = ".",
        target_dir: Optional[Union[str, Path]] = None,
        categories: Optional[Dict[str, List[str]]] = None,
        conflict_strategy: str = "rename",  # "rename", "skip", "overwrite"
        dry_run: bool = False,
        recursive: bool = False,
        ignore_hidden: bool = True,
        by_date: bool = False,
        save_history: bool = True,
        on_progress: Optional[Callable[[MoveRecord], None]] = None,
    ):
        self.source_dir = Path(source_dir).resolve()
        self.target_dir = Path(target_dir).resolve() if target_dir else self.source_dir
        self.categories = categories if categories is not None else DEFAULT_CATEGORIES
        self.extension_map = build_extension_map(self.categories)
        self.conflict_strategy = conflict_strategy.lower()
        self.dry_run = dry_run
        self.recursive = recursive
        self.ignore_hidden = ignore_hidden
        self.by_date = by_date
        self.save_history = save_history
        self.on_progress = on_progress

        if self.conflict_strategy not in {"rename", "skip", "overwrite"}:
            raise ValueError(f"Invalid conflict_strategy '{conflict_strategy}'. Must be 'rename', 'skip', or 'overwrite'.")

    def get_category_for_file(self, file_path: Path) -> str:
        """Determines category name based on file extension."""
        suffix = file_path.suffix.lower()
        return self.extension_map.get(suffix, "Others")

    def _resolve_target_name(self, dest_folder: Path, filename: str) -> Tuple[Path, bool]:
        """
        Determines the final destination path based on conflict resolution strategy.
        Returns (destination_path, should_proceed).
        """
        target_path = dest_folder / filename
        if not target_path.exists():
            return target_path, True

        if self.conflict_strategy == "skip":
            return target_path, False

        if self.conflict_strategy == "overwrite":
            return target_path, True

        # "rename" strategy: append counter (1), (2), etc.
        stem = Path(filename).stem
        suffix = Path(filename).suffix
        counter = 1
        while True:
            candidate = dest_folder / f"{stem} ({counter}){suffix}"
            if not candidate.exists():
                return candidate, True
            counter += 1

    def _collect_files(self) -> List[Path]:
        """Scans the source directory and returns files to be processed."""
        if not self.source_dir.exists():
            raise FileNotFoundError(f"Source directory does not exist: {self.source_dir}")

        if not self.source_dir.is_dir():
            raise NotADirectoryError(f"Source path is not a directory: {self.source_dir}")

        # Category folder names to avoid re-organizing already organized directories
        known_category_names = set(self.categories.keys())

        files_to_process: List[Path] = []

        if self.recursive:
            for root, dirs, files in os.walk(self.source_dir):
                root_path = Path(root)
                # Filter hidden directories if required
                if self.ignore_hidden:
                    dirs[:] = [
                        d for d in dirs
                        if not d.startswith(".") and d.lower() != "__pycache__"
                    ]

                # Don't scan inside destination category folders if organizing in-place
                if root_path == self.source_dir:
                    dirs[:] = [d for d in dirs if d not in known_category_names]

                for file in files:
                    if self._should_skip_file(file, root_path):
                        continue
                    files_to_process.append(root_path / file)
        else:
            for item in self.source_dir.iterdir():
                if item.is_file():
                    if self._should_skip_file(item.name, self.source_dir):
                        continue
                    files_to_process.append(item)

        return sorted(files_to_process)

    def _should_skip_file(self, filename: str, folder: Path) -> bool:
        """Determines if a file should be ignored from organization."""
        lower_name = filename.lower()
        if lower_name in IGNORED_SYSTEM_FILES:
            return True
        if self.ignore_hidden and filename.startswith("."):
            return True
        return False

    def organize(self) -> OrganizationSummary:
        """
        Executes file organization based on configured rules and options.
        """
        summary = OrganizationSummary(
            source_dir=str(self.source_dir),
            target_dir=str(self.target_dir),
            dry_run=self.dry_run,
        )

        files = self._collect_files()
        summary.total_files_scanned = len(files)

        history_records: List[MoveRecord] = []

        for file_path in files:
            category = self.get_category_for_file(file_path)

            # Determine destination subfolder
            dest_dir = self.target_dir / category
            if self.by_date:
                try:
                    stat_info = file_path.stat()
                    mod_time = datetime.fromtimestamp(stat_info.st_mtime)
                    dest_dir = dest_dir / f"{mod_time.year}" / f"{mod_time.strftime('%m-%B')}"
                except Exception:
                    pass

            target_file, should_move = self._resolve_target_name(dest_dir, file_path.name)

            record = MoveRecord(
                source=str(file_path),
                destination=str(target_file),
                category=category,
                timestamp=datetime.now().isoformat(),
            )

            try:
                record.file_size = file_path.stat().st_size
            except Exception:
                record.file_size = 0

            if not should_move:
                record.status = "skipped"
                summary.total_skipped += 1
            elif self.dry_run:
                record.status = "dry_run"
                summary.total_moved += 1
                summary.category_counts[category] = summary.category_counts.get(category, 0) + 1
            else:
                try:
                    dest_dir.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(file_path), str(target_file))
                    record.status = "moved"
                    summary.total_moved += 1
                    summary.category_counts[category] = summary.category_counts.get(category, 0) + 1
                    history_records.append(record)
                except Exception as ex:
                    record.status = "error"
                    record.error_message = str(ex)
                    summary.total_errors += 1

            summary.records.append(record)
            if self.on_progress:
                self.on_progress(record)

        if not self.dry_run and self.save_history and history_records:
            self._write_history(history_records)

        return summary

    def _get_history_file_path(self) -> Path:
        return self.target_dir / HISTORY_FILENAME

    def _write_history(self, new_records: List[MoveRecord]) -> None:
        """Appends new move actions to the history file for undo support."""
        history_file = self._get_history_file_path()
        existing = []
        if history_file.exists():
            try:
                with open(history_file, "r", encoding="utf-8") as f:
                    existing = json.load(f)
            except Exception:
                existing = []

        existing.extend([r.to_dict() for r in new_records])
        try:
            with open(history_file, "w", encoding="utf-8") as f:
                json.dump(existing, f, indent=2)
        except Exception:
            pass

    @classmethod
    def undo(cls, target_dir: Union[str, Path]) -> Tuple[int, int, List[str]]:
        """
        Reverts the last organization operations recorded in the target directory's history.
        Returns (reverted_count, failed_count, error_messages).
        """
        target_path = Path(target_dir).resolve()
        history_file = target_path / HISTORY_FILENAME
        if not history_file.exists():
            raise FileNotFoundError(f"No history file found at: {history_file}")

        with open(history_file, "r", encoding="utf-8") as f:
            records_data = json.load(f)

        if not records_data:
            return 0, 0, ["History log is empty."]

        reverted_count = 0
        failed_count = 0
        errors = []
        remaining_records = []

        # Revert in reverse order
        for item in reversed(records_data):
            curr_dest = Path(item["destination"])
            orig_src = Path(item["source"])

            if not curr_dest.exists():
                failed_count += 1
                errors.append(f"Cannot restore {curr_dest.name}: file does not exist at destination.")
                remaining_records.append(item)
                continue

            try:
                orig_src.parent.mkdir(parents=True, exist_ok=True)
                # If original location already has a file with the same name, don't overwrite blindly
                final_restore_target = orig_src
                if final_restore_target.exists() and final_restore_target != curr_dest:
                    stem = orig_src.stem
                    suffix = orig_src.suffix
                    counter = 1
                    while final_restore_target.exists():
                        final_restore_target = orig_src.parent / f"{stem}_restored_{counter}{suffix}"
                        counter += 1

                shutil.move(str(curr_dest), str(final_restore_target))
                reverted_count += 1
            except Exception as e:
                failed_count += 1
                errors.append(f"Failed to move {curr_dest} back to {orig_src}: {str(e)}")
                remaining_records.append(item)

        # Update history file
        if remaining_records:
            with open(history_file, "w", encoding="utf-8") as f:
                json.dump(list(reversed(remaining_records)), f, indent=2)
        else:
            try:
                history_file.unlink(missing_ok=True)
            except Exception:
                pass

        # Cleanup empty category folders
        for cat in DEFAULT_CATEGORIES.keys():
            cat_dir = target_path / cat
            if cat_dir.exists() and cat_dir.is_dir():
                try:
                    # remove if empty
                    if not any(cat_dir.iterdir()):
                        cat_dir.rmdir()
                except Exception:
                    pass

        return reverted_count, failed_count, errors
