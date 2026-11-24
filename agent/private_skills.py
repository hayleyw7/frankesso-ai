"""Read user-selected local Markdown preferences. No installation or script execution."""
import os
from pathlib import Path

MAX_SKILL_BYTES = 6000
MAX_SCAN_ENTRIES = 2000


class PrivateSkills:
    def __init__(self, root, check_path):
        self.repository = Path(root).absolute()
        self.check_path = check_path
        self.check_path(self.repository)
        self.repository = self.repository.resolve()
        conventional = self.repository / "skills"
        self.check_path(conventional)
        self.directory = conventional if conventional.is_dir() else self.repository

    def list(self):
        self.check_path(self.directory)
        files = []
        scanned = 0
        for root, dirs, names in os.walk(self.directory, followlinks=False):
            current = Path(root)
            allowed = []
            for name in sorted(dirs):
                scanned += 1
                if scanned > MAX_SCAN_ENTRIES:
                    return files
                try:
                    self.check_path(current / name)
                except (OSError, ValueError):
                    continue
                allowed.append(name)
            dirs[:] = allowed
            for name in sorted(names):
                scanned += 1
                if scanned > MAX_SCAN_ENTRIES:
                    return files
                path = current / name
                if path.suffix.lower() != ".md":
                    continue
                try:
                    self.check_path(path)
                    files.append({"path": path.relative_to(self.directory).as_posix(),
                                  "bytes": path.stat().st_size})
                except (OSError, ValueError):
                    continue
                if len(files) == 50:
                    return files
        return files

    def read(self, name):
        given = Path(name)
        if not name or given.is_absolute() or name.startswith(("/", "\\")) or ":" in name or ".." in given.parts or given.suffix.lower() != ".md":
            raise ValueError("Skill path must be a relative Markdown path from list_skills")
        path = self.directory / given
        self.check_path(path)
        if not path.is_file() or path.stat().st_size > MAX_SKILL_BYTES:
            raise ValueError("Skill file is missing or exceeds the 6,000-byte local context limit")
        content = path.read_text(encoding="utf-8-sig")
        return content
