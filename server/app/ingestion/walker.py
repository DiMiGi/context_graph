import os
from typing import List, Dict, Any, Generator
from app.config import EXCLUDE_DIRS, MAX_FILE_SIZE_KB

class DirectoryWalker:
    SUPPORTED_EXTENSIONS = {
        # Code
        ".py": "python",
        ".js": "javascript",
        ".jsx": "javascript",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".go": "go",
        ".rs": "rust",
        ".php": "php",
        ".java": "java",
        ".c": "c",
        ".cpp": "cpp",
        ".h": "c",
        ".hpp": "cpp",
        ".sql": "sql",
        ".prisma": "prisma",
        # Docs
        ".md": "markdown",
        ".mdx": "markdown",
        ".txt": "text",
        ".json": "json",
        ".yaml": "yaml",
        ".yml": "yaml",
    }

    @classmethod
    def walk(cls, root_path: str) -> Generator[Dict[str, Any], None, None]:
        if not os.path.exists(root_path):
            return

        max_size_bytes = MAX_FILE_SIZE_KB * 1024

        for root, dirs, files in os.walk(root_path, topdown=True):
            # Prune excluded dirs
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS and not d.startswith(".")]

            for file in files:
                ext = os.path.splitext(file)[1].lower()
                if ext in cls.SUPPORTED_EXTENSIONS:
                    file_path = os.path.join(root, file)
                    rel_path = os.path.relpath(file_path, root_path)
                    try:
                        size = os.path.getsize(file_path)
                        if size <= max_size_bytes:
                            yield {
                                "absolute_path": file_path,
                                "relative_path": rel_path,
                                "filename": file,
                                "extension": ext,
                                "file_type": cls.SUPPORTED_EXTENSIONS[ext],
                                "size": size
                            }
                    except Exception:
                        continue
