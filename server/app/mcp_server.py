import json
from typing import List, Optional
from mcp.server.fastmcp import FastMCP
from app.services.project_service import ProjectService
from app.services.graph_service import GraphService
from app.services.code_service import CodeService
from app.services.git_service import GitService
from app.ingestion.engine import IngestionEngine
import os

# FastMCP Server Instance
mcp = FastMCP("context_graph")

# Exponer el manejador SSE directamente en /sse y /messages
mcp_sse_app = mcp.sse_app()

@mcp.tool()
def list_projects() -> str:
    """Lists all available knowledge graph projects, active Git branches, commit hashes, and available branch graphs configured in projects_config.json."""
    projects = ProjectService.list_projects()
    return json.dumps(projects, indent=2)

@mcp.tool()
def get_project_summary(project_id: str, branch: Optional[str] = None) -> str:
    """Gets the architectural summary report (GRAPH_REPORT.md) for a project and optional branch (defaults to active Git branch)."""
    return ProjectService.get_summary(project_id, branch=branch)

@mcp.tool()
def query_graph_nodes(project_id: str, query: str = "", node_type: str = "", branch: Optional[str] = None) -> str:
    """Search for nodes in a project's knowledge graph by name/query and optional type (Module, Class, Function, Concept, Schema, Document, Config, Asset) in the specified or active branch."""
    if not ProjectService.is_configured(project_id):
        return f"Error: Project '{project_id}' is not configured or enabled in projects_config.json."
    results = GraphService.query_nodes(project_id, query=query, node_type=node_type, limit=50, branch=branch)
    return json.dumps(results, indent=2)

@mcp.tool()
def get_node_connections(project_id: str, node_id: str, branch: Optional[str] = None) -> str:
    """Finds all incoming and outgoing connections/dependencies for a specific node in the specified or active branch."""
    if not ProjectService.is_configured(project_id):
        return f"Error: Project '{project_id}' is not configured or enabled in projects_config.json."
    connections = GraphService.get_node_connections(project_id, node_id, branch=branch)
    if not connections:
        return f"Node '{node_id}' not found in project '{project_id}' (branch: {branch or 'active'})."
    return json.dumps(connections, indent=2)

@mcp.tool()
def get_impact_analysis(
    project_id: str,
    node_id: str,
    max_depth: int = 2,
    output_format: str = "markdown",
    branch: Optional[str] = None
) -> str:
    """Calculates the transitive blast radius / impact analysis for a node, identifying all upstream dependents (callers, importers, inheritors, mappers) grouped by risk level (Critical, High, Medium) in the specified or active branch."""
    return GraphService.calculate_impact(project_id, node_id, max_depth=max_depth, output_format=output_format, branch=branch)

@mcp.tool()
def get_code_slice(
    project_id: str,
    node_id: str,
    context_lines: int = 0,
    branch: Optional[str] = None
) -> str:
    """Retrieves the exact source code snippet for a node using AST line metadata (start_line, end_line) directly without manual file slicing."""
    return CodeService.get_code_slice(project_id, node_id, context_lines=context_lines, branch=branch)

@mcp.tool()
def get_subgraph(
    project_id: str,
    focal_node_id: str,
    depth: int = 1,
    output_format: str = "markdown",
    branch: Optional[str] = None
) -> str:
    """Extracts a focused architecture ego-subgraph centered around a focal node (Module, Class, or Function) within N-hops in the specified or active branch, ideal for compact agent prompt context."""
    return GraphService.extract_subgraph(project_id, focal_node_id, depth=depth, output_format=output_format, branch=branch)

@mcp.tool()
def update_node_context(project_id: str, node_id: str, description: str, branch: Optional[str] = None) -> str:
    """Allows AI agents to enrich notes or architectural context on a specific node without breaking scanner data."""
    success, msg = GraphService.update_node_context(project_id, node_id, description, branch=branch)
    return msg

@mcp.tool()
def add_custom_connection(project_id: str, source: str, target: str, relation: str = "relates_to", branch: Optional[str] = None) -> str:
    """Allows AI agents to create new architectural relationships between nodes that persist across re-indexing."""
    success, msg = GraphService.add_custom_connection(project_id, source, target, relation, branch=branch)
    return msg

@mcp.tool()
def sync_project_graph(project_id: str, branch: Optional[str] = None) -> str:
    """Checks the Git repository commit hash for the project/branch and performs an incremental Git-diff sync if changes or new commits are detected."""
    if not ProjectService.is_configured(project_id):
        return f"Error: Project '{project_id}' is not configured or enabled in projects_config.json."

    source_path = ProjectService.get_source_path(project_id)
    if not source_path or not os.path.exists(source_path):
        return f"Error: Project source path for '{project_id}' not found."

    git_info = GitService.get_git_info(source_path)
    effective_branch = branch or git_info.get("branch", "main")
    
    try:
        graph = IngestionEngine.index_directory(
            project_id=project_id,
            source_directory=source_path,
            mode="incremental",
            branch=effective_branch
        )
        return json.dumps({
            "status": "success",
            "project_id": project_id,
            "branch": effective_branch,
            "commit_hash": graph.metadata.get("commit_hash", ""),
            "commit_short": graph.metadata.get("commit_short", ""),
            "commit_message": graph.metadata.get("commit_message", ""),
            "is_dirty": graph.metadata.get("is_dirty", False),
            "total_nodes": len(graph.nodes),
            "total_edges": len(graph.edges),
            "total_files": graph.metadata.get("total_files", 0),
            "new_files_parsed": graph.metadata.get("new_files_parsed", 0)
        }, indent=2)
    except Exception as e:
        return f"Error syncing project graph: {str(e)}"

@mcp.tool()
def reindex_modified_files(project_id: str, file_paths: List[str], branch: Optional[str] = None) -> str:
    """Allows AI agents to partially re-index only the files they just modified or created, leaving all other graph connections and notes intact."""
    if not ProjectService.is_configured(project_id):
        return f"Error: Project '{project_id}' is not configured or enabled in projects_config.json."

    source_path = ProjectService.get_source_path(project_id)
    if not source_path or not os.path.exists(source_path):
        return f"Error: Project source path for '{project_id}' not found."

    try:
        graph = IngestionEngine.index_directory(
            project_id=project_id,
            source_directory=source_path,
            mode="partial",
            target_paths=file_paths,
            branch=branch
        )
        return json.dumps({
            "status": "success",
            "project_id": project_id,
            "branch": graph.metadata.get("branch", branch or "main"),
            "mode": "partial",
            "files_reindexed": file_paths,
            "total_nodes": len(graph.nodes),
            "total_edges": len(graph.edges)
        }, indent=2)
    except Exception as e:
        return f"Error during partial reindex: {str(e)}"
