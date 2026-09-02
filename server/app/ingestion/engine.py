import os
import networkx as nx
from typing import Dict, Any, List, Optional
from app.ingestion.walker import DirectoryWalker
from app.ingestion.parsers import get_parser
from app.graph.model import GraphData, Node, Edge
from app.graph.storage import GraphStorage

class IngestionEngine:
    @classmethod
    def index_directory(
        cls,
        project_id: str,
        source_directory: str,
        project_name: str = None,
        mode: str = "incremental",  # "incremental", "rebuild", "partial"
        target_paths: Optional[List[str]] = None
    ) -> GraphData:
        if not os.path.exists(source_directory):
            raise ValueError(f"Directory {source_directory} does not exist")

        existing_graph = GraphStorage.load_graph(project_id)
        
        # 1. Preparar nodos y aristas existentes según el modo
        nodes_dict: Dict[str, Node] = {}
        edges_list: List[Edge] = []
        raw_edges_tuples = []

        existing_file_paths = set()

        if existing_graph and mode != "rebuild":
            # Si es parcial, identificar qué rutas deben ser purgadas y re-parseadas
            purge_prefixes = []
            if mode == "partial" and target_paths:
                purge_prefixes = [p.strip().lstrip("./") for p in target_paths if p.strip()]

            for n in existing_graph.nodes:
                should_purge = False
                if purge_prefixes and n.path:
                    for pfx in purge_prefixes:
                        if n.path == pfx or n.path.startswith(pfx + "/") or n.path.startswith(pfx + "\\"):
                            # Si es un nodo automático del archivo a purgar, se purga para re-parsearlo
                            if not n.is_custom:
                                should_purge = True
                                break

                if not should_purge:
                    nodes_dict[n.id] = n
                    if n.path:
                        existing_file_paths.add(n.path)

            # Conservar aristas no afectadas por la purga parcial
            for e in existing_graph.edges:
                if e.source in nodes_dict and e.target in nodes_dict:
                    edges_list.append(e)
                    raw_edges_tuples.append((e.source, e.target))

        total_files = 0
        file_types_count = {}
        file_gen, unregistered_files = DirectoryWalker.walk(source_directory)

        new_files_parsed = 0

        # 2. Recorrido de archivos en disco
        for file_meta in file_gen:
            total_files += 1
            rel_path = file_meta["relative_path"]
            abs_path = file_meta["absolute_path"]
            ext = file_meta["extension"]
            is_media = file_meta.get("is_media", False)

            file_types_count[ext] = file_types_count.get(ext, 0) + 1

            # Si es modo incremental y el archivo ya existe en el grafo, OMITIR (Append-Only)
            if mode == "incremental" and rel_path in existing_file_paths:
                continue

            # Si es modo parcial y el archivo NO está en las rutas target ni es nuevo, OMITIR
            if mode == "partial" and purge_prefixes:
                matches_target = any(rel_path == pfx or rel_path.startswith(pfx + "/") for pfx in purge_prefixes)
                if not matches_target and rel_path in existing_file_paths:
                    continue

            new_files_parsed += 1
            file_node_id = f"file:{rel_path}"
            
            if is_media:
                file_node_type = "Asset"
            elif ext in (".md", ".mdx", ".txt", ".mmd", ".mermaid"):
                file_node_type = "Document"
            elif ext in (".json", ".yml", ".yaml", ".xml", ".sbc", ".conf"):
                file_node_type = "Config"
            elif ext in (".css", ".scss", ".sass", ".less"):
                file_node_type = "Style"
            else:
                file_node_type = "Module"

            if file_node_id not in nodes_dict or not nodes_dict[file_node_id].is_custom:
                nodes_dict[file_node_id] = Node(
                    id=file_node_id,
                    label=os.path.basename(rel_path),
                    type=file_node_type,
                    path=rel_path,
                    description=f"Source file: {rel_path}",
                    origin="auto",
                    is_custom=False,
                    metadata={"size": file_meta["size"], "extension": ext}
                )

            if not is_media:
                parser = get_parser(ext)
                if parser:
                    try:
                        with open(abs_path, "r", encoding="utf-8", errors="ignore") as f:
                            content = f.read()

                        extracted_nodes, extracted_edges = parser.parse(content, rel_path)

                        for n in extracted_nodes:
                            nid = n["id"]
                            if nid not in nodes_dict:
                                nodes_dict[nid] = Node(**n, origin="auto", is_custom=False)

                        for e in extracted_edges:
                            edges_list.append(Edge(**e, origin="auto", is_custom=False))
                            raw_edges_tuples.append((e["source"], e["target"]))

                    except Exception as e:
                        print(f"Error parsing {abs_path}: {e}")

        # 3. NetworkX Communities & Degrees
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

        # 3.1 Cálculo de Layout Espacial 2D Determinista para WebGL
        try:
            num_nodes = len(G.nodes)
            if num_nodes > 0:
                if num_nodes <= 10000:
                    pos = nx.spring_layout(G, seed=42, iterations=35, k=2.0 / (num_nodes ** 0.5 + 1e-5))
                else:
                    try:
                        pos = nx.spectral_layout(G, scale=1.0)
                    except Exception:
                        pos = nx.spring_layout(G, seed=42, iterations=15)

                for nid, coords in pos.items():
                    if nid in nodes_dict and len(coords) >= 2:
                        nodes_dict[nid].x = round(float(coords[0]) * 1500.0, 2)
                        nodes_dict[nid].y = round(float(coords[1]) * 1500.0, 2)
        except Exception as e:
            print(f"Error computing 2D layout coordinates: {e}")

        god_nodes = sorted(G.degree, key=lambda x: x[1], reverse=True)[:10]

        # 4. Save GraphData
        display_name = project_name if project_name else (existing_graph.name if existing_graph else os.path.basename(source_directory))
        graph = GraphData(
            project_id=project_id,
            name=display_name,
            nodes=list(nodes_dict.values()),
            edges=edges_list,
            metadata={
                "source_directory": source_directory,
                "total_files": total_files,
                "new_files_parsed": new_files_parsed,
                "file_types": file_types_count,
                "unregistered_files": unregistered_files,
                "last_mode": mode,
                "total_nodes": len(nodes_dict),
                "total_edges": len(edges_list)
            }
        )

        GraphStorage.save_graph(graph)

        # 5. Generate Report
        report_md = cls._generate_report(graph, god_nodes, file_types_count, unregistered_files, mode, new_files_parsed)
        GraphStorage.save_report(project_id, report_md)

        return graph

    @classmethod
    def _generate_report(cls, graph: GraphData, god_nodes: list, file_types: dict, unregistered_files: dict = None, mode: str = "incremental", new_files_count: int = 0) -> str:
        report = f"# 🌐 Reporte de Grafo de Conocimiento: {graph.name}\n\n"
        report += f"- **ID Proyecto:** `{graph.project_id}`\n"
        report += f"- **Directorio Origen:** `{graph.metadata.get('source_directory', 'N/A')}`\n"
        report += f"- **Total Nodos en Base:** `{len(graph.nodes)}`\n"
        report += f"- **Total Conexiones:** `{len(graph.edges)}`\n"
        report += f"- **Archivos Analizados en Disco:** `{graph.metadata.get('total_files', 0)}`\n"
        report += f"- **Última Operación:** Modo `{mode}` (Archivos nuevos/actualizados procesados: `{new_files_count}`)\n\n"

        schema_nodes = [n for n in graph.nodes if n.type.lower() == "schema"]
        if schema_nodes:
            report += f"## 🗄️ Entidades de Base de Datos Detectadas ({len(schema_nodes)})\n\n"
            report += "| Tabla / Esquema | Definido en |\n| :--- | :--- |\n"
            for sn in schema_nodes:
                report += f"| `{sn.label}` | `{sn.path or 'Schema'}` |\n"
            report += "\n"

        report += "## 📊 Distribución de Tipos de Archivos\n\n"
        for ft, count in sorted(file_types.items(), key=lambda x: x[1], reverse=True):
            report += f"- **{ft}:** {count} archivos\n"

        report += "\n## 👑 Nodos Críticos / God Nodes (Mayor Conectividad)\n\n"
        report += "| Nodo | Conexiones |\n| :--- | :--- |\n"
        for node_id, degree in god_nodes:
            report += f"| `{node_id}` | **{degree}** |\n"

        if unregistered_files:
            report += "\n## ⚠️ Archivos No Registrados (Pendientes de Categorizar)\n\n"
            report += "Se encontraron extensiones de archivo que no tienen un parser asignado:\n\n"
            report += "| Extensión | Cantidad |\n| :--- | :--- |\n"
            for ext, count in sorted(unregistered_files.items(), key=lambda x: x[1], reverse=True):
                report += f"| `{ext}` | {count} |\n"
        else:
            report += "\n## ✅ Estado de Categorización\n\nTodos los archivos del proyecto han sido categorizados exitosamente.\n"

        report += "\n---\n*Generado automáticamente por context_graph Incremental Engine.*\n"
        return report
