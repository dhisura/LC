"""Workspace file utilities and diff tools."""
import difflib
from pathlib import Path
from typing import List, Optional, Tuple


class FileManager:
    """Manages workspace file reads, writes, and diff calculations."""

    def __init__(self, workspace: str = "."):
        self.workspace = Path(workspace).resolve()

    def resolve(self, path: str) -> Path:
        """Resolve a path and refuse anything that escapes the workspace.

        The workspace is the trust boundary: `dev.write_solution` passes the
        `[FILE: ...]` headers straight out of the LLM response to `write_file`,
        so an emitted path of `../../.ssh/authorized_keys` or an absolute
        `C:/...` would otherwise let the model write anywhere the process can.
        Resolving first also collapses `..` and follows symlinks, so a link
        planted inside the workspace cannot point out of it.
        """
        p = Path(path)
        # An absolute path is not "already inside" -- it is simply a different
        # root, so it goes through the same containment check as a relative one.
        candidate = (p if p.is_absolute() else self.workspace / p).resolve()

        if not candidate.is_relative_to(self.workspace):
            raise ValueError(
                f"Path escapes the workspace: {path!r} resolves to {candidate}, "
                f"which is outside {self.workspace}."
            )
        return candidate

    def read_file(self, path: str) -> str:
        """Reads a file content as text."""
        target = self.resolve(path)
        if not target.exists():
            raise FileNotFoundError(f"File not found: {target}")
        return target.read_text(encoding="utf-8", errors="replace")

    def write_file(self, path: str, content: str) -> Tuple[int, str]:
        """Writes content to a file, returning (bytes_written, diff_or_status)."""
        target = self.resolve(path)
        target.parent.mkdir(parents=True, exist_ok=True)

        old_content = ""
        is_new = not target.exists()
        if not is_new:
            old_content = target.read_text(encoding="utf-8", errors="replace")

        target.write_text(content, encoding="utf-8")
        bytes_written = len(content.encode("utf-8"))

        if is_new:
            line_count = len(content.splitlines())
            diff = f"+++ [NEW FILE] {path} ({bytes_written} bytes, {line_count} lines)\n"
            diff += "".join(f"+{line}\n" for line in content.splitlines())
        else:
            diff = self.compute_diff(old_content, content, filename=path)

        return bytes_written, diff

    def list_files(self, max_depth: int = 3) -> List[str]:
        """Lists files in the workspace up to max_depth."""
        results: List[str] = []
        ignore_dirs = {".git", ".lc", "__pycache__", "node_modules", ".venv", "venv", ".idea"}

        def _scan(curr: Path, depth: int):
            if depth > max_depth:
                return
            try:
                for item in curr.iterdir():
                    if item.name in ignore_dirs:
                        continue
                    rel = item.relative_to(self.workspace)
                    if item.is_file():
                        results.append(str(rel).replace("\\", "/"))
                    elif item.is_dir():
                        _scan(item, depth + 1)
            except PermissionError:
                pass

        _scan(self.workspace, 1)
        return sorted(results)

    @staticmethod
    def compute_diff(old: str, new: str, filename: str = "file") -> str:
        """Generate unified diff text."""
        old_lines = old.splitlines(keepends=True)
        new_lines = new.splitlines(keepends=True)
        diff = difflib.unified_diff(
            old_lines,
            new_lines,
            fromfile=f"a/{filename}",
            tofile=f"b/{filename}",
            lineterm=""
        )
        return "".join(diff)

    @staticmethod
    def count_diff_lines(diff: str) -> int:
        """Count added or modified lines in a diff for the Diff Budget."""
        count = 0
        for line in diff.splitlines():
            if line.startswith("+") and not line.startswith("+++"):
                count += 1
        return count
