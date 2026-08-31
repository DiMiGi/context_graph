from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import networkx as nx
from app.graph.model import GraphData, Node, Edge
from app.graph.storage import GraphStorage
from app.ingestion.engine import IngestionEngine

router = APIRouter(prefix="/api/ingest", tags=["ingest"])

class IngestRequest(BaseModel):
    project_id: str
    source_directory: str
    project_name: Optional[str] = None

class IngestPayloadRequest(BaseModel):
    project_id: str
    project_name: Optional[str] = None
    source_directory: Optional[str] = None
    nodes: List[Dict[str, Any]]
    edges: List[Dict[str, Any]]
    stats: Optional[Dict[str, Any]] = Field(default_factory=dict)

@router.post("")
def ingest_directory(req: IngestRequest):
    """Indexa un directorio que esté dentro del alcance del contenedor."""
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

@router.post("/payload")
def ingest_payload(req: IngestPayloadRequest):
    """Recibe un grafo ya escaneado por el CLI externo (host) y lo almacena."""
    try:
        nodes_dict: Dict[str, Node] = {}
        for n_raw in req.nodes:
            nid = n_raw.get("id")
            if nid and nid not in nodes_dict:
                nodes_dict[nid] = Node(**n_raw)

        edges_list: List[Edge] = []
        raw_edges_tuples = []
        for e_raw in req.edges:
            edges_list.append(Edge(**e_raw))
            raw_edges_tuples.append((e_raw.get("source"), e_raw.get("target")))

        # NetworkX analysis
        G = nx.Graph()
        for nid in nodes_dict.keys():
            G.add_node(nid)
        for s, t in raw_edges_tuples:
            if s and t:
                G.add_edge(s, t)

        try:
            communities = list(nx.community.greedy_modularity_communities(G))
            for comm_id, comm_nodes in enumerate(communities):
                for nid in comm_nodes:
                    if nid in nodes_dict:
                        nodes_dict[nid].community = comm_id
        except Exception:
            pass

        god_nodes = sorted(G.degree, key=lambda x: x[1], reverse=True)[:10]

        display_name = req.project_name if req.project_name else req.project_id
        graph = GraphData(
            project_id=req.project_id,
            name=display_name,
            nodes=list(nodes_dict.values()),
            edges=edges_list,
            metadata={
                "source_directory": req.source_directory or "Remote Client",
                "total_files": req.stats.get("total_files", 0),
                "file_types": req.stats.get("file_types", {}),
                "total_nodes": len(nodes_dict),
                "total_edges": len(edges_list)
            }
        )

        GraphStorage.save_graph(graph)

        # Generar GRAPH_REPORT.md
        report_md = IngestionEngine._generate_report(graph, god_nodes, req.stats.get("file_types", {}))
        GraphStorage.save_report(req.project_id, report_md)

        return {
            "status": "success",
            "project_id": graph.project_id,
            "nodes_count": len(graph.nodes),
            "edges_count": len(graph.edges),
            "total_files": graph.metadata.get("total_files", 0)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
