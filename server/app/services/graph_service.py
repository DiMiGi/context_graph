import json
from typing import List, Dict, Any, Optional, Tuple
from app.graph.storage import GraphStorage
from app.graph.model import Node, Edge, GraphData
from app.services.project_service import ProjectService

class GraphService:
    @staticmethod
    def get_graph(project_id: str) -> Optional[GraphData]:
        """Carga el grafo completo para un proyecto si está configurado."""
        if not ProjectService.is_configured(project_id):
            return None
        return GraphStorage.load_graph(project_id)

    @classmethod
    def query_nodes(cls, project_id: str, query: str = "", node_type: str = "", limit: int = 50) -> List[Dict[str, Any]]:
        """Busca nodos por nombre/texto y tipo opcional."""
        graph = cls.get_graph(project_id)
        if not graph:
            return []

        results = []
        q = (query or "").lower().strip()
        nt = (node_type or "").lower().strip()

        for node in graph.nodes:
            if nt and node.type.lower() != nt:
                continue
            if not q or (q in node.id.lower() or q in node.label.lower() or q in (node.description or "").lower()):
                results.append(node.model_dump())
                if len(results) >= limit:
                    break

        return results

    @classmethod
    def get_node_connections(cls, project_id: str, node_id: str) -> Optional[Dict[str, Any]]:
        """Obtiene el nodo y todas sus conexiones entrantes y salientes."""
        graph = cls.get_graph(project_id)
        if not graph:
            return None

        node_data = next((n.model_dump() for n in graph.nodes if n.id == node_id), None)
        if not node_data:
            return None

        incoming = [e.model_dump() for e in graph.edges if e.target == node_id]
        outgoing = [e.model_dump() for e in graph.edges if e.source == node_id]

        return {
            "node": node_data,
            "outgoing_calls_or_imports": outgoing,
            "incoming_dependents": incoming
        }

    @classmethod
    def update_node_context(cls, project_id: str, node_id: str, description: str) -> Tuple[bool, str]:
        """Permite enriquecer notas o contexto arquitectónico en un nodo con persistencia (is_custom=True)."""
        graph = cls.get_graph(project_id)
        if not graph:
            return False, f"Project '{project_id}' not found or not configured."

        target = next((n for n in graph.nodes if n.id == node_id), None)
        if not target:
            return False, f"Node '{node_id}' not found in project '{project_id}'."

        target.description = description
        target.is_custom = True
        target.origin = "ai"
        GraphStorage.save_graph(graph)
        return True, f"Successfully updated node '{node_id}' in project '{project_id}'."

    @classmethod
    def add_custom_connection(cls, project_id: str, source: str, target: str, relation: str = "relates_to") -> Tuple[bool, str]:
        """Crea una relación personalizada persistente entre dos nodos existentes."""
        graph = cls.get_graph(project_id)
        if not graph:
            return False, f"Project '{project_id}' not found or not configured."

        node_ids = {n.id for n in graph.nodes}
        if source not in node_ids or target not in node_ids:
            return False, f"Error: Source '{source}' or Target '{target}' does not exist in graph."

        for e in graph.edges:
            if e.source == source and e.target == target and e.relation == relation:
                return True, "Connection already exists."

        edge = Edge(source=source, target=target, relation=relation, origin="ai", is_custom=True)
        graph.edges.append(edge)
        GraphStorage.save_graph(graph)
        return True, f"Successfully created persistent connection: {source} -[{relation}]-> {target}"

    @classmethod
    def calculate_impact(cls, project_id: str, node_id: str, max_depth: int = 2, output_format: str = "markdown") -> str:
        """Calcula el radio de impacto transitivo (Blast Radius) clasificando por riesgo."""
        graph = cls.get_graph(project_id)
        if not graph:
            return f"Project '{project_id}' not found or not configured."

        target_node = next((n for n in graph.nodes if n.id == node_id), None)
        if not target_node:
            return f"Node '{node_id}' not found in project '{project_id}'."

        incoming_map: Dict[str, List[Tuple[str, str]]] = {}
        node_lookup: Dict[str, Node] = {n.id: n for n in graph.nodes}
        for edge in graph.edges:
            if edge.target not in incoming_map:
                incoming_map[edge.target] = []
            incoming_map[edge.target].append((edge.source, edge.relation))

        visited = {node_id: 0}
        queue = [(node_id, 0)]
        edge_paths = []

        while queue:
            curr, depth = queue.pop(0)
            if depth >= max_depth:
                continue
            for src, rel in incoming_map.get(curr, []):
                if src not in visited:
                    visited[src] = depth + 1
                    queue.append((src, depth + 1))
                edge_paths.append({"source": src, "target": curr, "relation": rel, "hop": depth + 1})

        critical_nodes = []
        high_nodes = []
        medium_nodes = []

        for nid, hop in visited.items():
            if nid == node_id:
                continue
            n_obj = node_lookup.get(nid)
            if not n_obj:
                continue

            entry = {
                "id": n_obj.id,
                "label": n_obj.label,
                "type": n_obj.type,
                "path": n_obj.path,
                "hop": hop,
                "signature": n_obj.metadata.get("signature") if n_obj.metadata else None
            }

            if n_obj.type == "Schema" or (n_obj.metadata and n_obj.metadata.get("kind") in ("schema", "entity")):
                critical_nodes.append(entry)
            elif hop == 1:
                high_nodes.append(entry)
            else:
                medium_nodes.append(entry)

        if output_format.lower() == "json":
            return json.dumps({
                "target_node": target_node.model_dump(),
                "max_depth": max_depth,
                "total_impacted": len(visited) - 1,
                "critical_risk": critical_nodes,
                "high_risk": high_nodes,
                "medium_risk": medium_nodes,
                "dependency_paths": edge_paths
            }, indent=2)

        md = f"# 💥 Impact Analysis (Blast Radius): `{target_node.label}`\n\n"
        md += f"- **Target Node:** `{target_node.id}` ({target_node.type})\n"
        if target_node.path:
            md += f"- **File Path:** `{target_node.path}`\n"
        if target_node.metadata and target_node.metadata.get("signature"):
            md += f"- **Signature:** `{target_node.metadata.get('signature')}`\n"
        md += f"- **Exploration Depth:** {max_depth} saltos | **Total de dependientes afectados:** {len(visited) - 1}\n\n"

        if critical_nodes:
            md += "### 🔴 Riesgo Crítico (Schemas & Modelos de Datos)\n"
            md += "| Nodo / Tabla | Tipo | Salto | Archivo |\n| :--- | :--- | :--- | :--- |\n"
            for cn in critical_nodes:
                md += f"| `{cn['label']}` | `{cn['type']}` | Hop {cn['hop']} | `{cn['path'] or 'N/A'}` |\n"
            md += "\n"

        if high_nodes:
            md += "### 🟠 Riesgo Alto (Dependientes Directos - Hop 1)\n"
            md += "| Nodo | Tipo | Firma / Rol | Archivo |\n| :--- | :--- | :--- | :--- |\n"
            for hn in high_nodes:
                sig = f"`{hn['signature']}`" if hn['signature'] else "-"
                md += f"| `{hn['label']}` | `{hn['type']}` | {sig} | `{hn['path'] or 'N/A'}` |\n"
            md += "\n"

        if medium_nodes:
            md += "### 🟡 Riesgo Medio (Dependientes Transitivos - Hop 2+)\n"
            md += "| Nodo | Tipo | Salto | Archivo |\n| :--- | :--- | :--- | :--- |\n"
            for mn in medium_nodes:
                md += f"| `{mn['label']}` | `{mn['type']}` | Hop {mn['hop']} | `{mn['path'] or 'N/A'}` |\n"
            md += "\n"

        if not critical_nodes and not high_nodes and not medium_nodes:
            md += "✅ **No se detectaron dependientes entrantes.** Modificar este nodo no debería impactar otros componentes indexados.\n"

        return md

    @classmethod
    def extract_subgraph(cls, project_id: str, focal_node_id: str, depth: int = 1, output_format: str = "markdown") -> str:
        """Extrae un subgrafo focalizado de N-saltos alrededor de un nodo focal."""
        graph = cls.get_graph(project_id)
        if not graph:
            return f"Project '{project_id}' not found or not configured."

        focal_node = next((n for n in graph.nodes if n.id == focal_node_id), None)
        if not focal_node:
            return f"Error: Focal node '{focal_node_id}' not found in project '{project_id}'."

        node_lookup = {n.id: n for n in graph.nodes}
        adj: Dict[str, List[Tuple[str, str, str]]] = {}

        for edge in graph.edges:
            if edge.source not in adj:
                adj[edge.source] = []
            if edge.target not in adj:
                adj[edge.target] = []
            adj[edge.source].append((edge.target, edge.relation, "outgoing"))
            adj[edge.target].append((edge.source, edge.relation, "incoming"))

        visited_nodes = {focal_node_id: 0}
        queue = [(focal_node_id, 0)]
        collected_edges = []
        seen_edges = set()

        while queue:
            curr, cur_depth = queue.pop(0)
            if cur_depth >= depth:
                continue
            for neighbor, rel, direction in adj.get(curr, []):
                edge_key = (curr, neighbor, rel) if direction == "outgoing" else (neighbor, curr, rel)
                if edge_key not in seen_edges:
                    seen_edges.add(edge_key)
                    collected_edges.append({
                        "source": edge_key[0],
                        "target": edge_key[1],
                        "relation": rel
                    })
                if neighbor not in visited_nodes:
                    visited_nodes[neighbor] = cur_depth + 1
                    queue.append((neighbor, cur_depth + 1))

        subgraph_nodes = [node_lookup[nid].model_dump() for nid in visited_nodes if nid in node_lookup]

        if output_format.lower() == "json":
            return json.dumps({
                "focal_node": focal_node.model_dump(),
                "depth": depth,
                "nodes_count": len(subgraph_nodes),
                "edges_count": len(collected_edges),
                "nodes": subgraph_nodes,
                "edges": collected_edges
            }, indent=2)

        md = f"# 🕸️ Subgrafo Contextual: `{focal_node.label}`\n\n"
        md += f"- **Nodo Focal:** `{focal_node.id}` ({focal_node.type})\n"
        md += f"- **Profundidad de corte:** {depth} saltos | **Nodos:** {len(subgraph_nodes)} | **Relaciones:** {len(collected_edges)}\n\n"

        md += "### 📦 Nodos del Subgrafo\n"
        md += "| ID / Label | Tipo | Salto | Firma / Contexto |\n| :--- | :--- | :--- | :--- |\n"
        for sn in sorted(subgraph_nodes, key=lambda x: visited_nodes.get(x["id"], 0)):
            h = visited_nodes.get(sn["id"], 0)
            h_str = "🎯 Focal" if h == 0 else f"Hop {h}"
            sig = sn.get("metadata", {}).get("signature") or sn.get("description") or "-"
            md += f"| `{sn['label']}` | `{sn['type']}` | {h_str} | `{sig}` |\n"
        md += "\n"

        md += "### 🔗 Relaciones\n"
        md += "| Origen | Relación | Destino |\n| :--- | :--- | :--- | :--- |\n"
        for ce in collected_edges:
            src_label = node_lookup.get(ce["source"], Node(id=ce["source"], label=ce["source"])).label
            tgt_label = node_lookup.get(ce["target"], Node(id=ce["target"], label=ce["target"])).label
            md += f"| `{src_label}` | `--[{ce['relation']}]-->` | `{tgt_label}` |\n"

        return md
