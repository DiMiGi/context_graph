from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any
from pydantic import BaseModel
from app.graph.storage import GraphStorage
from app.graph.model import GraphData

router = APIRouter(prefix="/api/projects", tags=["projects"])

class CreateProjectRequest(BaseModel):
    project_id: str
    name: str

@router.get("", response_model=List[Dict[str, Any]])
def list_projects():
    return GraphStorage.list_projects()

@router.post("", response_model=GraphData)
def create_project(req: CreateProjectRequest):
    if not req.project_id.strip():
        raise HTTPException(status_code=400, detail="Project ID cannot be empty")
    return GraphStorage.create_project(req.project_id, req.name)

@router.delete("/{project_id}")
def delete_project(project_id: str):
    success = GraphStorage.delete_project(project_id)
    if not success:
        raise HTTPException(status_code=404, detail="Project not found")
    return {"message": f"Project {project_id} deleted"}
