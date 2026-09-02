from fastapi import APIRouter, HTTPException, Header
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
import os
from app.services.project_service import ProjectService
from app.graph.storage import GraphStorage
from app.graph.model import GraphData
from app.config import get_configured_projects
from app.ingestion.engine import IngestionEngine

router = APIRouter(prefix="/api/projects", tags=["projects"])

class CreateProjectRequest(BaseModel):
    project_id: str
    name: str

class ReindexRequest(BaseModel):
    mode: str = "incremental"  # "incremental", "partial", "rebuild"
    target_paths: Optional[List[str]] = None

@router.get("", response_model=List[Dict[str, Any]])
def list_projects():
    return ProjectService.list_projects()

@router.post("", response_model=GraphData)
def create_project(req: CreateProjectRequest):
    if not req.project_id.strip():
        raise HTTPException(status_code=400, detail="Project ID cannot be empty")
    return GraphStorage.create_project(req.project_id, req.name)

@router.post("/{project_id}/reindex")
def reindex_project(
    project_id: str,
    req: Optional[ReindexRequest] = None,
    x_requested_by: Optional[str] = Header(None)
):
    """
    Reindexa el proyecto.
    - Modo 'incremental' (default): Solo agrega archivos que no existan.
    - Modo 'partial': Purga y re-parsea solo los archivos indicados en target_paths.
    - Modo 'rebuild': Purga total (solo permitido si viene explícitamente desde la Web UI).
    """
    if not ProjectService.is_configured(project_id):
        raise HTTPException(
            status_code=404,
            detail=f"El proyecto '{project_id}' no está configurado o habilitado en projects_config.json."
        )

    mode = req.mode if req else "incremental"
    target_paths = req.target_paths if req else None

    # Seguridad: El modo 'rebuild' completo SOLO se permite si la petición viene del navegador (UI)
    if mode == "rebuild" and x_requested_by != "web_ui":
        raise HTTPException(
            status_code=403,
            detail="La purga completa (rebuild) solo está permitida desde la interfaz web con confirmación del usuario."
        )

    source_path = ProjectService.get_source_path(project_id)
    if not source_path or not os.path.exists(source_path):
        raise HTTPException(
            status_code=404,
            detail=f"No se encontró la ruta del proyecto '{project_id}'. Verifica que la carpeta exista en tu máquina y ejecuta ./start.sh o ./start.ps1."
        )

    configured = get_configured_projects()
    target_config = next((cp for cp in configured if cp.get("id") == project_id), None)
    proj_name = target_config.get("name") if target_config else project_id

    try:
        graph = IngestionEngine.index_directory(
            project_id=project_id,
            source_directory=source_path,
            project_name=proj_name,
            mode=mode,
            target_paths=target_paths
        )
        return {
            "status": "success",
            "project_id": graph.project_id,
            "mode": mode,
            "nodes_count": len(graph.nodes),
            "edges_count": len(graph.edges),
            "total_files": graph.metadata.get("total_files", 0),
            "new_files_parsed": graph.metadata.get("new_files_parsed", 0)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{project_id}")
def delete_project(project_id: str):
    success = GraphStorage.delete_project(project_id)
    if not success:
        raise HTTPException(status_code=404, detail="Project not found")
    return {"message": f"Project {project_id} deleted"}
