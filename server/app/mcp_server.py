import json
from typing import Dict, Any, List, Optional
from mcp.server.fastmcp import FastMCP
from app.graph.storage import GraphStorage
from app.graph.model import Node, Edge
from app.ingestion.engine import IngestionEngine
from app.config import get_configured_projects
import os

# FastMCP Server
mcp = FastMCP("local_graphs")

# Exponer el manejador SSE directamente en /sse y /messages
mcp_sse_app = mcp.sse_app()

@mcp.tool()
def list_projects() -> str:
    """Lists all available knowledge graph projects."""
    projects = GraphStorage.list_projects()
    return json.dumps(projects, indent=2)

@mcp.tool()
def get_project_summary(project_id: str) -> str:
    """Gets the architectural summary report (GRAPH_REPORT.md) for a project."""
    report = GraphStorage.load_report(project_id)
    return report

@mcp.tool()
def query_graph_nodes(project_id: str, query: str = "", node_type: str = "") -> str:
    """Search for nodes in a project's knowledge graph by name/query and optional type (Module, Class, Function, Concept, Schema, Document)."""
    graph = GraphStorage.load_graph(project_id)
    if not graph:
        return f"Project '{project_id}' not found."

    results = []
    q = query.lower()
    for node in graph.nodes:
        if node_type and node.type.lower() != node_type.lower():
            continue
        if not q or (q in node.id.lower() or q in node.label.lower() or q in (node.description or "").lower()):
            results.append(node.model_dump())

    return json.dumps(results[:50], indent=2)

@mcp.tool()
def get_node_connections(project_id: str, node_id: str) -> str:
    """Finds all incoming and outgoing connections/dependencies for a specific node."""
    graph = GraphStorage.load_graph(project_id)
    if not graph:
        return f"Project '{project_id}' not found."

    incoming = [e.model_dump() for e in graph.edges if e.target == node_id]
    outgoing = [e.model_dump() for e in graph.edges if e.source == node_id]

    node_data = next((n.model_dump() for n in graph.nodes if n.id == node_id), None)
    return json.dumps({
        "node": node_data,
        "outgoing_calls_or_imports": outgoing,
        "incoming_dependents": incoming
    }, indent=2)

@mcp.tool()
def update_node_context(project_id: str, node_id: str, description: str) -> str:
    """Allows AI agents to enrich notes or architectural context on a specific node without breaking scanner data."""
    graph = GraphStorage.load_graph(project_id)
    if not graph:
        return f"Project '{project_id}' not found."

    target = next((n for n in graph.nodes if n.id == node_id), None)
    if not target:
        return f"Node '{node_id}' not found in project '{project_id}'."

    target.description = description
    target.is_custom = True
    target.origin = "ai"
    GraphStorage.save_graph(graph)
    return f"Successfully updated node '{node_id}' (marked as AI-enriched) in project '{project_id}'."

@mcp.tool()
def add_custom_connection(project_id: str, source: str, target: str, relation: str = "relates_to") -> str:
    """Allows AI agents to create new architectural relationships between nodes that persist across re-indexing."""
    graph = GraphStorage.load_graph(project_id)
    if not graph:
        return f"Project '{project_id}' not found."

    node_ids = {n.id for n in graph.nodes}
    if source not in node_ids or target not in node_ids:
        return f"Error: Source '{source}' or Target '{target}' does not exist in graph."

    for e in graph.edges:
        if e.source == source and e.target == target and e.relation == relation:
            return "Connection already exists."

    edge = Edge(source=source, target=target, relation=relation, origin="ai", is_custom=True)
    graph.edges.append(edge)
    GraphStorage.save_graph(graph)
    return f"Successfully created persistent connection: {source} -[{relation}]-> {target}"

@mcp.tool()
def reindex_modified_files(project_id: str, file_paths: List[str]) -> str:
    """Allows AI agents to partially re-index only the files they just modified or created, leaving all other graph connections and notes intact."""
    configured = get_configured_projects()
    target_config = next((cp for cp in configured if cp.get("id") == project_id), None)

    source_path = None
    if target_config:
        source_path = target_config.get("container_path")
    if not source_path or not os.path.exists(source_path):
        source_path = f"/host_proyectos/{project_id}"

    if not os.path.exists(source_path):
        return f"Error: Project path for '{project_id}' not found."

    try:
        graph = IngestionEngine.index_directory(
            project_id=project_id,
            source_directory=source_path,
            mode="partial",
            target_paths=file_paths
        )
        return json.dumps({
            "status": "success",
            "project_id": project_id,
            "mode": "partial",
            "files_reindexed": file_paths,
            "total_nodes": len(graph.nodes),
            "total_edges": len(graph.edges)
        }, indent=2)
    except Exception as e:
        return f"Error during partial reindex: {str(e)}"
