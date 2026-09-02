import os
from typing import List, Dict, Any, Optional
from app.config import get_configured_projects, is_project_configured, DATA_PATH
from app.graph.storage import GraphStorage

class ProjectService:
    @staticmethod
    def is_configured(project_id: str) -> bool:
        """Verifica si un project_id está explícitamente habilitado en projects_config.json."""
        return is_project_configured(project_id)

    @staticmethod
    def list_projects() -> List[Dict[str, Any]]:
        """Lista todos los proyectos configurados y sus estadísticas de grafo."""
        return GraphStorage.list_projects()

    @staticmethod
    def get_summary(project_id: str) -> str:
        """Obtiene el reporte arquitectónico resumido (GRAPH_REPORT.md)."""
        if not is_project_configured(project_id):
            return f"Error: Project '{project_id}' is not configured or enabled in projects_config.json."
        return GraphStorage.load_report(project_id)

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
