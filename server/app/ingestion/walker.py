import os
from typing import Dict, Any, Generator, Tuple, Set
from app.config import EXCLUDE_DIRS, MAX_FILE_SIZE_KB
from app.ingestion.parsers import PARSERS_MAP

class DirectoryWalker:
    SUPPORTED_EXTENSIONS = set(PARSERS_MAP.keys())

    # Static assets and lockfiles to categorize as Media/Asset without parsing
    MEDIA_EXTENSIONS = {".png", ".jpg", ".jpeg", ".svg", ".gif", ".webp", ".ico", ".woff", ".woff2", ".ttf", ".eot"}
    IGNORE_SYSTEM_EXTENSIONS = {".lock", ".example", ".tmp", ".log"}

    @classmethod
    def walk(cls, root_path: str) -> Tuple[Generator[Dict[str, Any], None, None], Dict[str, int]]:
        if not os.path.exists(root_path):
            return (x for x in []), {}

        max_size_bytes = MAX_FILE_SIZE_KB * 1024
        unregistered_files: Dict[str, int] = {}

        def file_generator():
            for root, dirs, files in os.walk(root_path, topdown=True):
                # Prune excluded dirs
                dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS and d != "data" and not d.startswith(".")]

                for file in files:
                    ext = os.path.splitext(file)[1].lower()
                    file_path = os.path.join(root, file)
                    rel_path = os.path.relpath(file_path, root_path)

                    if ext in cls.SUPPORTED_EXTENSIONS or ext in cls.MEDIA_EXTENSIONS:
                        try:
                            size = os.path.getsize(file_path)
                            if size <= max_size_bytes:
                                yield {
                                    "absolute_path": file_path,
                                    "relative_path": rel_path,
                                    "filename": file,
                                    "extension": ext,
                                    "is_media": ext in cls.MEDIA_EXTENSIONS,
                                    "size": size
                                }
                        except Exception:
                            continue
                    elif ext in cls.IGNORE_SYSTEM_EXTENSIONS:
                        # Skip system lockfiles / example templates quietly
                        continue
                    else:
                        # Track genuinely unregistered extensions
                        if ext and not ext.startswith(".git") and len(ext) <= 8:
                            unregistered_files[ext] = unregistered_files.get(ext, 0) + 1

        return file_generator(), unregistered_files
