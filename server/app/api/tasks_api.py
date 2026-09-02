import uuid
import time
import os
import threading
from typing import Dict, Any, Optional, List
from fastapi import APIRouter, HTTPException, BackgroundTasks, Header
from pydantic import BaseModel
from app.graph.storage import GraphStorage
from app.config import get_configured_projects, is_project_configured
from app.ingestion.engine import IngestionEngine

router = APIRouter(prefix="/api/tasks", tags=["tasks"])

# Almacén en memoria de tareas asíncronas
TASKS_STORE: Dict[str, Dict[str, Any]] = {}

class ReindexTaskRequest(BaseModel):
    mode: str = "incremental"  # "incremental", "partial", "rebuild"
    target_paths: Optional[List[str]] = None

def _run_reindex_task(task_id: str, project_id: str, mode: str, target_paths: Optional[List[str]]):
    try:
        TASKS_STORE[task_id]["status"] = "running"
        TASKS_STORE[task_id]["started_at"] = time.time()
        
        configured = get_configured_projects()
        target_config = next((cp for cp in configured if cp.get("id") == project_id), None)
        
        source_path = None
        proj_name = None
        if target_config:
            host_path = target_config.get("host_path", "")
            folder_name = os.path.basename(host_path.rstrip("/\\")) if host_path else project_id
            source_path = target_config.get("container_path", f"/sources/{folder_name}")
            proj_name = target_config.get("name")
        
        if not source_path or not os.path.exists(source_path):
            for fb in [f"/sources/{project_id}", f"/host_proyectos/{project_id}"]:
                if os.path.exists(fb):
                    source_path = fb
                    break

        if not source_path or not os.path.exists(source_path):
            TASKS_STORE[task_id]["status"] = "failed"
            TASKS_STORE[task_id]["error"] = f"Ruta fuente para '{project_id}' no encontrada en el contenedor."
            return

        graph = IngestionEngine.index_directory(
            project_id=project_id,
            source_directory=source_path,
            project_name=proj_name,
            mode=mode,
            target_paths=target_paths
        )

        TASKS_STORE[task_id]["status"] = "completed"
        TASKS_STORE[task_id]["completed_at"] = time.time()
        TASKS_STORE[task_id]["result"] = {
            "project_id": project_id,
            "mode": mode,
            "nodes_count": len(graph.nodes),
            "edges_count": len(graph.edges),
            "total_files": graph.metadata.get("total_files", 0),
            "new_files_parsed": graph.metadata.get("new_files_parsed", 0)
        }
    except Exception as e:
        TASKS_STORE[task_id]["status"] = "failed"
        TASKS_STORE[task_id]["error"] = str(e)
        TASKS_STORE[task_id]["completed_at"] = time.time()

@router.post("/projects/{project_id}/reindex")
def start_reindex_task(
    project_id: str,
    req: Optional[ReindexTaskRequest] = None,
    background_tasks: BackgroundTasks = None,
    x_requested_by: Optional[str] = Header(None)
):
    if not is_project_configured(project_id):
        raise HTTPException(
            status_code=404,
            detail=f"El proyecto '{project_id}' no está configurado o habilitado en projects_config.json."
        )

    mode = req.mode if req else "incremental"
    target_paths = req.target_paths if req else None

    if mode == "rebuild" and x_requested_by != "web_ui":
        raise HTTPException(
            status_code=403,
            detail="La purga completa (rebuild) solo está permitida desde la interfaz web."
        )

    task_id = str(uuid.uuid4())
    TASKS_STORE[task_id] = {
        "id": task_id,
        "type": "reindex",
        "project_id": project_id,
        "mode": mode,
        "target_paths": target_paths,
        "status": "queued",
        "created_at": time.time(),
        "started_at": None,
        "completed_at": None,
        "result": None,
        "error": None
    }

    thread = threading.Thread(
        target=_run_reindex_task,
        args=(task_id, project_id, mode, target_paths),
        daemon=True
    )
    thread.start()

    return {
        "task_id": task_id,
        "status": "queued",
        "message": f"Tarea de indexación ({mode}) encolada para '{project_id}'."
    }

@router.get("")
def list_tasks():
    tasks = list(TASKS_STORE.values())
    return sorted(tasks, key=lambda x: x["created_at"], reverse=True)

@router.get("/{task_id}")
def get_task_status(task_id: str):
    if task_id not in TASKS_STORE:
        raise HTTPException(status_code=404, detail="Tarea no encontrada")
    return TASKS_STORE[task_id]
