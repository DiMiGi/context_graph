from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional
from app.ingestion.engine import IngestionEngine

router = APIRouter(prefix="/api/ingest", tags=["ingest"])

class IngestRequest(BaseModel):
    project_id: str
    source_directory: str
    project_name: Optional[str] = None

@router.post("")
def ingest_directory(req: IngestRequest):
    try:
        graph = IngestionEngine.index_directory(
            project_id=req.project_id,
            source_directory=req.source_directory,
            project_name=req.project_name
        )
        return {
            "status": "success",
            "project_id": graph.project_id,
            "nodes_count": len(graph.nodes),
            "edges_count": len(graph.edges),
            "total_files": graph.metadata.get("total_files", 0)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
