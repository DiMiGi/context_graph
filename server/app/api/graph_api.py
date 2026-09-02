from fastapi import APIRouter, HTTPException
from typing import Optional, Dict, Any
from pydantic import BaseModel
from app.services.project_service import ProjectService
from app.services.graph_service import GraphService
from app.graph.storage import GraphStorage
from app.graph.model import GraphData, Node, Edge

router = APIRouter(prefix="/api/projects/{project_id}/graph", tags=["graph"])

def check_project_configured(project_id: str):
    if not ProjectService.is_configured(project_id):
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' is not configured or enabled")

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

import networkx as nx

def ensure_graph_layout(graph: GraphData, project_id: str):
    if not graph or not graph.nodes:
        return
    if any(n.x is None or n.y is None for n in graph.nodes):
        G = nx.Graph()
        for n in graph.nodes:
            G.add_node(n.id)
        for e in graph.edges:
            if e.source and e.target:
                G.add_edge(e.source, e.target)

        num_nodes = len(G.nodes)
        try:
            if num_nodes <= 10000:
                pos = nx.spring_layout(G, seed=42, iterations=35, k=2.0 / (num_nodes ** 0.5 + 1e-5))
            else:
                try:
                    pos = nx.spectral_layout(G, scale=1.0)
                except Exception:
                    pos = nx.spring_layout(G, seed=42, iterations=15)

            for n in graph.nodes:
                if n.id in pos and len(pos[n.id]) >= 2:
                    coords = pos[n.id]
                    n.x = round(float(coords[0]) * 1500.0, 2)
                    n.y = round(float(coords[1]) * 1500.0, 2)

            GraphStorage.save_graph(graph)
        except Exception as e:
            print(f"Error computing layout for {project_id}: {e}. Usando fallback radial...")
            import math
            for idx, n in enumerate(graph.nodes):
                comm = n.community or 0
                angle = idx * 2.399963229728653
                r = math.sqrt(idx + 1) * 35.0
                cx = (comm % 5 - 2) * 500.0
                cy = (comm // 5 - 2) * 500.0
                n.x = round(cx + r * math.cos(angle), 2)
                n.y = round(cy + r * math.sin(angle), 2)
            GraphStorage.save_graph(graph)

@router.get("", response_model=GraphData)
def get_graph(project_id: str):
    check_project_configured(project_id)
    graph = GraphService.get_graph(project_id)
    if not graph:
        raise HTTPException(status_code=404, detail="Graph not found")
    ensure_graph_layout(graph, project_id)
    return graph

@router.get("/geometry")
def get_graph_geometry(project_id: str):
    check_project_configured(project_id)
    graph = GraphService.get_graph(project_id)
    if not graph:
        raise HTTPException(status_code=404, detail="Graph not found")
    ensure_graph_layout(graph, project_id)

    compact_nodes = [
        {
            "id": n.id,
            "label": n.label or n.id,
            "type": n.type,
            "x": n.x,
            "y": n.y,
            "community": n.community or 0,
            "is_custom": n.is_custom
        }
        for n in graph.nodes
    ]

    compact_edges = [
        {
            "source": e.source,
            "target": e.target,
            "relation": e.relation
        }
        for e in graph.edges
    ]

    return {
        "project_id": graph.project_id,
        "name": graph.name,
        "nodes": compact_nodes,
        "edges": compact_edges,
        "metadata": {
            "total_nodes": len(compact_nodes),
            "total_edges": len(compact_edges),
            "total_files": graph.metadata.get("total_files", 0),
            "file_types": graph.metadata.get("file_types", {}),
            "unregistered_files": graph.metadata.get("unregistered_files", {})
        }
    }

@router.get("/nodes/{node_id:path}", response_model=Node)
def get_node(project_id: str, node_id: str):
    check_project_configured(project_id)
    graph = GraphStorage.load_graph(project_id)
    if not graph:
        raise HTTPException(status_code=404, detail="Graph not found")
    for n in graph.nodes:
        if n.id == node_id:
            return n
    raise HTTPException(status_code=404, detail="Node not found")

@router.get("/report")
def get_report(project_id: str):
    check_project_configured(project_id)
    report = ProjectService.get_summary(project_id)
    return {"report": report}

@router.post("/nodes", response_model=Node)
def add_node(project_id: str, req: AddNodeRequest):
    check_project_configured(project_id)
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
    check_project_configured(project_id)
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
    check_project_configured(project_id)
    graph = GraphStorage.load_graph(project_id)
    if not graph:
        raise HTTPException(status_code=404, detail="Graph not found")

    graph.nodes = [n for n in graph.nodes if n.id != node_id]
    graph.edges = [e for e in graph.edges if e.source != node_id and e.target != node_id]

    GraphStorage.save_graph(graph)
    return {"message": f"Node {node_id} and related edges deleted"}

@router.post("/edges", response_model=Edge)
def add_edge(project_id: str, req: AddEdgeRequest):
    check_project_configured(project_id)
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
    check_project_configured(project_id)
    graph = GraphStorage.load_graph(project_id)
    if not graph:
        raise HTTPException(status_code=404, detail="Graph not found")

    if relation:
        graph.edges = [e for e in graph.edges if not (e.source == source and e.target == target and e.relation == relation)]
    else:
        graph.edges = [e for e in graph.edges if not (e.source == source and e.target == target)]

    GraphStorage.save_graph(graph)
    return {"message": "Edge deleted"}
