"""
rules.py
Default file category mappings and custom rule configuration for fileorg.
"""

from typing import Dict, List, Optional
import json
import os
from pathlib import Path

# Built-in extension-to-category mapping
DEFAULT_CATEGORIES: Dict[str, List[str]] = {
    "Documents": [
        ".docx", ".doc", ".txt", ".rtf", ".odt", ".tex", ".md", ".pages", ".wpd", ".dotx"
    ],
    "PDFs": [
        ".pdf"
    ],
    "Spreadsheets": [
        ".xlsx", ".xls", ".csv", ".tsv", ".ods", ".numbers", ".xlsm", ".xlsb"
    ],
    "Presentations": [
        ".pptx", ".ppt", ".odp", ".key", ".ppsx", ".pps"
    ],
    "Images": [
        ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".svg", ".webp", ".tiff", ".tif",
        ".ico", ".psd", ".ai", ".raw", ".heic", ".heif", ".eps", ".indd"
    ],
    "Videos": [
        ".mp4", ".mkv", ".mov", ".avi", ".wmv", ".flv", ".webm", ".m4v", ".3gp",
        ".mpeg", ".mpg", ".vob"
    ],
    "Audio": [
        ".mp3", ".wav", ".aac", ".flac", ".ogg", ".m4a", ".wma", ".aiff", ".alac",
        ".mid", ".midi"
    ],
    "Archives": [
        ".zip", ".tar", ".gz", ".7z", ".rar", ".bz2", ".xz", ".iso", ".tgz",
        ".tar.gz", ".tar.bz2", ".tar.xz", ".cab", ".dmg"
    ],
    "Code": [
        ".py", ".js", ".ts", ".jsx", ".tsx", ".html", ".htm", ".css", ".scss",
        ".sass", ".json", ".xml", ".yaml", ".yml", ".java", ".c", ".cpp", ".cc",
        ".h", ".hpp", ".cs", ".go", ".rs", ".php", ".rb", ".sh", ".bash", ".zsh",
        ".bat", ".cmd", ".ps1", ".sql", ".swift", ".kt", ".lua", ".r", ".dart"
    ],
    "Executables": [
        ".exe", ".msi", ".apk", ".bin", ".appimage", ".deb", ".rpm", ".jar", ".app"
    ],
    "Fonts": [
        ".ttf", ".otf", ".woff", ".woff2", ".eot"
    ],
    "Ebooks": [
        ".epub", ".mobi", ".azw", ".azw3", ".djvu"
    ],
    "Others": []
}


def build_extension_map(categories: Optional[Dict[str, List[str]]] = None) -> Dict[str, str]:
    """
    Builds a reverse lookup dictionary mapping normalized lowercase file extensions to category names.
    """
    cats = categories if categories is not None else DEFAULT_CATEGORIES
    ext_map: Dict[str, str] = {}
    for category, extensions in cats.items():
        for ext in extensions:
            clean_ext = ext.lower()
            if not clean_ext.startswith("."):
                clean_ext = f".{clean_ext}"
            ext_map[clean_ext] = category
    return ext_map


def load_rules_from_file(file_path: str | Path) -> Dict[str, List[str]]:
    """
    Loads custom category-extension rules from a JSON file.
    Merges with DEFAULT_CATEGORIES or overrides them.
    """
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"Rules configuration file not found: {file_path}")

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, dict):
        raise ValueError("Rules configuration must be a JSON object mapping categories to extension lists.")

    # Merge custom categories on top of default
    merged = {cat: list(exts) for cat, exts in DEFAULT_CATEGORIES.items()}
    for category, extensions in data.items():
        if isinstance(extensions, list):
            merged[category] = [str(ext).lower() for ext in extensions]
    return merged
