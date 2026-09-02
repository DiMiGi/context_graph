import os
from typing import Optional, Dict
from app.graph.storage import GraphStorage
from app.services.project_service import ProjectService

class CodeService:
    LANG_MAP: Dict[str, str] = {
        "py": "python",
        "js": "javascript",
        "ts": "typescript",
        "jsx": "javascript",
        "tsx": "typescript",
        "php": "php",
        "cs": "csharp",
        "sql": "sql",
        "json": "json",
        "yml": "yaml",
        "yaml": "yaml",
        "html": "html",
        "css": "css",
        "md": "markdown",
        "sh": "bash",
        "ps1": "powershell"
    }

    @classmethod
    def get_code_slice(cls, project_id: str, node_id: str, context_lines: int = 0) -> str:
        """
        Extrae el fragmento exacto de código fuente correspondiente al nodo
        usando los metadatos de AST (start_line, end_line) directamente desde disco.
        """
        if not ProjectService.is_configured(project_id):
            return f"Error: Project '{project_id}' is not configured or enabled in projects_config.json."

        graph = GraphStorage.load_graph(project_id)
        if not graph:
            return f"Project '{project_id}' not found."

        node = next((n for n in graph.nodes if n.id == node_id), None)
        if not node:
            return f"Error: Node '{node_id}' not found in project '{project_id}'."

        if not node.path:
            return f"Error: Node '{node_id}' does not have an associated file path."

        meta = node.metadata or {}
        start_line = meta.get("start_line")
        end_line = meta.get("end_line", start_line)

        source_path = ProjectService.get_source_path(project_id)
        if not source_path:
            return f"Error: Source directory for project '{project_id}' could not be resolved."

        rel_path_clean = node.path.replace("\\", "/").lstrip("/")
        full_file_path = os.path.join(source_path, rel_path_clean)

        if not os.path.exists(full_file_path):
            # Fallback en rutas relativas locales
            fallbacks = [
                node.path,
                os.path.join(os.path.dirname(__file__), "..", "..", node.path)
            ]
            for fb in fallbacks:
                if os.path.exists(fb):
                    full_file_path = fb
                    break

        if not os.path.exists(full_file_path):
            return f"Error: File '{node.path}' could not be located on disk (checked in {source_path})."

        try:
            with open(full_file_path, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
        except Exception as e:
            return f"Error reading file '{full_file_path}': {str(e)}"

        total_file_lines = len(lines)
        if start_line is None:
            start_line = 1
            end_line = min(50, total_file_lines)

        actual_start = max(1, start_line - context_lines)
        actual_end = min(total_file_lines, (end_line or start_line) + context_lines)

        slice_content = "".join(lines[actual_start - 1:actual_end])
        ext = os.path.splitext(node.path)[1].lstrip(".").lower()
        lang = cls.LANG_MAP.get(ext, ext or "text")

        out = f"### 📄 Code Slice: `{node.label}` ({node.type})\n"
        out += f"- **Archivo:** `{node.path}` (L{actual_start}-L{actual_end} de {total_file_lines})\n"
        if meta.get("signature"):
            out += f"- **Firma:** `{meta.get('signature')}`\n"
        out += f"\n```{lang}\n{slice_content.rstrip()}\n```\n"
        return out
