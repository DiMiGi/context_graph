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
        target = next((p for p in configured if p.get("id") == project_id), None)
        if target:
            cpath = target.get("container_path")
            if cpath and os.path.exists(cpath):
                return cpath
            hpath = target.get("host_path")
            if hpath and os.path.exists(hpath):
                return hpath

        # Fallbacks estándar de contenedor
        candidate_paths = [
            f"/sources/{project_id}",
            f"/host_proyectos/{project_id}",
            os.path.abspath(os.path.join(DATA_PATH, "..", ".."))
        ]
        for cp in candidate_paths:
            if os.path.exists(cp):
                return cp
        return None
