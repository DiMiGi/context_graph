import os
from typing import List, Dict, Any, Optional
from app.config import get_configured_projects, is_project_configured, DATA_PATH
from app.graph.storage import GraphStorage
from app.services.git_service import GitService

class ProjectService:
    @staticmethod
    def is_configured(project_id: str) -> bool:
        """Verifica si un project_id está explícitamente habilitado en projects_config.json."""
        return is_project_configured(project_id)

    @staticmethod
    def list_projects() -> List[Dict[str, Any]]:
        """Lista todos los proyectos configurados, sus ramas y estadísticas de grafo."""
        return GraphStorage.list_projects()

    @classmethod
    def get_active_branch(cls, project_id: str) -> str:
        """Obtiene el nombre de la rama activa de Git en el workspace."""
        source_path = cls.get_source_path(project_id)
        if source_path:
            git_info = GitService.get_git_info(source_path)
            return git_info.get("branch", "main")
        return "main"

    @classmethod
    def get_git_info(cls, project_id: str) -> Dict[str, Any]:
        """Obtiene la información de Git del proyecto."""
        source_path = cls.get_source_path(project_id)
        if source_path:
            return GitService.get_git_info(source_path)
        return {"is_git_repo": False, "branch": "main"}

    @classmethod
    def list_branches(cls, project_id: str) -> List[Dict[str, Any]]:
        """
        Lista todas las ramas locales de Git y las ramas indexadas en disco.
        """
        source_path = cls.get_source_path(project_id)
        active_branch = cls.get_active_branch(project_id)
        
        # 1. Obtener ramas indexadas en disco
        indexed_branches = GraphStorage.list_branches(project_id)
        indexed_map = {b["branch"]: b for b in indexed_branches}

        # 2. Obtener todas las ramas locales de Git
        local_git_branches = GitService.get_local_branches(source_path) if source_path else []

        combined = []
        seen_branches = set()

        # Primero procesar ramas locales de Git
        for gb in local_git_branches:
            b_name = gb["branch"]
            seen_branches.add(b_name)
            is_active = (b_name == active_branch)
            idx_info = indexed_map.get(b_name, {})

            combined.append({
                "branch": b_name,
                "is_active": is_active,
                "is_indexed": bool(idx_info),
                "nodes_count": idx_info.get("nodes_count", 0),
                "edges_count": idx_info.get("edges_count", 0),
                "commit_hash": gb.get("commit_hash") or idx_info.get("commit_hash", ""),
                "short_hash": gb.get("short_hash") or idx_info.get("short_hash", ""),
                "commit_message": gb.get("commit_message") or idx_info.get("commit_message", ""),
                "commit_date": gb.get("commit_date") or "",
                "updated_at": idx_info.get("updated_at", 0.0)
            })

        # Agregar ramas indexadas que quizás ya no existen en git local (ej. legacy o worktrees antiguos)
        for b_name, idx_info in indexed_map.items():
            if b_name not in seen_branches:
                seen_branches.add(b_name)
                combined.append({
                    "branch": b_name,
                    "is_active": (b_name == active_branch),
                    "is_indexed": True,
                    "nodes_count": idx_info.get("nodes_count", 0),
                    "edges_count": idx_info.get("edges_count", 0),
                    "commit_hash": idx_info.get("commit_hash", ""),
                    "short_hash": idx_info.get("short_hash", ""),
                    "commit_message": idx_info.get("commit_message", ""),
                    "commit_date": "",
                    "updated_at": idx_info.get("updated_at", 0.0)
                })

        # Si la lista sigue vacía (ej. proyecto no git), agregar al menos la activa o main
        if not combined:
            combined.append({
                "branch": active_branch or "main",
                "is_active": True,
                "is_indexed": False,
                "nodes_count": 0,
                "edges_count": 0,
                "commit_hash": "",
                "short_hash": "",
                "commit_message": "",
                "commit_date": "",
                "updated_at": 0.0
            })

        # Ordenar: La rama activa primero, luego las indexadas, luego por nombre
        def sort_key(x):
            return (
                0 if x["is_active"] else 1,
                0 if x["is_indexed"] else 1,
                -x["updated_at"],
                x["branch"]
            )

        return sorted(combined, key=sort_key)

    @classmethod
    def get_summary(cls, project_id: str, branch: Optional[str] = None) -> str:
        """Obtiene el reporte arquitectónico resumido (GRAPH_REPORT.md)."""
        if not is_project_configured(project_id):
            return f"Error: Project '{project_id}' is not configured or enabled in projects_config.json."
        
        effective_branch = branch or cls.get_active_branch(project_id)
        return GraphStorage.load_report(project_id, branch=effective_branch)

    @staticmethod
    def get_source_path(project_id: str) -> Optional[str]:
        """Resuelve la ruta absoluta en disco o contenedor para el código fuente del proyecto."""
        if not is_project_configured(project_id):
            return None
        configured = get_configured_projects()
        target = next((p for p in configured if (p.get("id") or "").lower() == project_id.lower()), None)
        
        pid_clean = project_id.lower()
        
        # 1. Si está configurado container_path explícito
        if target and target.get("container_path"):
            cp = target.get("container_path")
            if os.path.exists(cp):
                return cp

        # 2. Rutas estándar en contenedor usando project_id en minúsculas
        candidate_paths = [
            f"/sources/{pid_clean}",
            f"/sources/{project_id}"
        ]

        # 3. Si tiene host_path, verificar nombre de carpeta original y en minúsculas dentro de /sources
        if target and target.get("host_path"):
            hp = target.get("host_path", "")
            folder_name = os.path.basename(hp.rstrip("/\\"))
            if folder_name:
                candidate_paths.append(f"/sources/{folder_name.lower()}")
                candidate_paths.append(f"/sources/{folder_name}")

        for cp in candidate_paths:
            if os.path.exists(cp):
                return cp

        # 4. Fallback: búsqueda case-insensitive dentro de /sources
        if os.path.exists("/sources") and os.path.isdir("/sources"):
            try:
                for entry in os.listdir("/sources"):
                    if entry.lower() == pid_clean:
                        return os.path.join("/sources", entry)
            except Exception:
                pass

        # 5. Fallback host_path directo (ej. si se ejecuta en host local sin Docker)
        if target and target.get("host_path"):
            hpath = target.get("host_path")
            if os.path.exists(hpath):
                return hpath

        # 6. Fallback legado
        candidate_fallbacks = [
            f"/host_proyectos/{pid_clean}",
            f"/host_proyectos/{project_id}",
            os.path.abspath(os.path.join(DATA_PATH, "..", ".."))
        ]
        for cp in candidate_fallbacks:
            if os.path.exists(cp):
                return cp
        return None
