"""Read user-selected local Markdown preferences. No installation or script execution."""
from pathlib import Path

MAX_SKILL_BYTES = 6000


class PrivateSkills:
    def __init__(self, root, check_path):
        self.repository = Path(root).absolute()
        self.check_path = check_path
        self.check_path(self.repository)
        self.repository = self.repository.resolve()
        self.directory = self.repository / "skills" if (self.repository / "skills").is_dir() else self.repository
        self.check_path(self.directory)

    def list(self):
        files = []
        for path in self.directory.rglob("*.md"):
            self.check_path(path)
            files.append({"path": path.relative_to(self.directory).as_posix(), "bytes": path.stat().st_size})
            if len(files) == 50:
                break
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
