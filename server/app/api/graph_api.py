from fastapi import APIRouter, HTTPException
from typing import Optional, Dict, Any
from pydantic import BaseModel
from app.graph.storage import GraphStorage
from app.graph.model import GraphData, Node, Edge

router = APIRouter(prefix="/api/projects/{project_id}/graph", tags=["graph"])

class AddNodeRequest(BaseModel):
    id: str
    label: str
    type: str = "Concept"
    path: Optional[str] = None
    description: Optional[str] = ""
    community: Optional[int] = 0
    origin: Optional[str] = "manual"

class UpdateNodeRequest(BaseModel):
    label: Optional[str] = None
    type: Optional[str] = None
    path: Optional[str] = None
    description: Optional[str] = None
    community: Optional[int] = None
    origin: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

class AddEdgeRequest(BaseModel):
    source: str
    target: str
    relation: str = "relates_to"
    weight: Optional[float] = 1.0
    origin: Optional[str] = "manual"

@router.get("", response_model=GraphData)
def get_graph(project_id: str):
    graph = GraphStorage.load_graph(project_id)
    if not graph:
        raise HTTPException(status_code=404, detail="Graph not found")
    return graph

@router.get("/report")
def get_report(project_id: str):
    report = GraphStorage.load_report(project_id)
    return {"report": report}

@router.post("/nodes", response_model=Node)
def add_node(project_id: str, req: AddNodeRequest):
    graph = GraphStorage.load_graph(project_id)
    if not graph:
        raise HTTPException(status_code=404, detail="Graph not found")

    for n in graph.nodes:
        if n.id == req.id:
            raise HTTPException(status_code=400, detail="Node already exists")

    node_dict = req.model_dump()
    node_dict["is_custom"] = True
    node_dict["origin"] = req.origin or "manual"

    node = Node(**node_dict)
    graph.nodes.append(node)
    GraphStorage.save_graph(graph)
    return node

@router.put("/nodes/{node_id:path}", response_model=Node)
def update_node(project_id: str, node_id: str, req: UpdateNodeRequest):
    graph = GraphStorage.load_graph(project_id)
    if not graph:
        raise HTTPException(status_code=404, detail="Graph not found")

    target_node = None
    for n in graph.nodes:
        if n.id == node_id:
            target_node = n
            break

    if not target_node:
        raise HTTPException(status_code=404, detail="Node not found")

    update_data = req.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(target_node, key, value)

    # Marcar como editado manualmente / por IA
    target_node.is_custom = True
    if not req.origin:
        target_node.origin = "manual"

    GraphStorage.save_graph(graph)
    return target_node

@router.delete("/nodes/{node_id:path}")
def delete_node(project_id: str, node_id: str):
    graph = GraphStorage.load_graph(project_id)
    if not graph:
        raise HTTPException(status_code=404, detail="Graph not found")

    graph.nodes = [n for n in graph.nodes if n.id != node_id]
    graph.edges = [e for e in graph.edges if e.source != node_id and e.target != node_id]

    GraphStorage.save_graph(graph)
    return {"message": f"Node {node_id} and related edges deleted"}

@router.post("/edges", response_model=Edge)
def add_edge(project_id: str, req: AddEdgeRequest):
    graph = GraphStorage.load_graph(project_id)
    if not graph:
        raise HTTPException(status_code=404, detail="Graph not found")

    node_ids = {n.id for n in graph.nodes}
    if req.source not in node_ids or req.target not in node_ids:
        raise HTTPException(status_code=400, detail="Both source and target nodes must exist")

    edge_dict = req.model_dump()
    edge_dict["is_custom"] = True
    edge_dict["origin"] = req.origin or "manual"

    edge = Edge(**edge_dict)
    graph.edges.append(edge)
    GraphStorage.save_graph(graph)
    return edge

@router.delete("/edges")
def delete_edge(project_id: str, source: str, target: str, relation: Optional[str] = None):
    graph = GraphStorage.load_graph(project_id)
    if not graph:
        raise HTTPException(status_code=404, detail="Graph not found")

    if relation:
        graph.edges = [e for e in graph.edges if not (e.source == source and e.target == target and e.relation == relation)]
    else:
        graph.edges = [e for e in graph.edges if not (e.source == source and e.target == target)]

    GraphStorage.save_graph(graph)
    return {"message": "Edge deleted"}
