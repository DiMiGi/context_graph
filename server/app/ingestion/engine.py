import os
import networkx as nx
from typing import Dict, Any, List
from app.ingestion.walker import DirectoryWalker
from app.ingestion.code_parser import CodeParser
from app.ingestion.doc_parser import DocParser
from app.graph.model import GraphData, Node, Edge
from app.graph.storage import GraphStorage

class IngestionEngine:
    @classmethod
    def index_directory(cls, project_id: str, source_directory: str, project_name: str = None) -> GraphData:
        if not os.path.exists(source_directory):
            raise ValueError(f"Directory {source_directory} does not exist")

        nodes_dict: Dict[str, Node] = {}
        edges_list: List[Edge] = []
        raw_edges_tuples = []

        total_files = 0
        file_types_count = {}

        # 1. Walk directory and parse
        for file_meta in DirectoryWalker.walk(source_directory):
            total_files += 1
            rel_path = file_meta["relative_path"]
            abs_path = file_meta["absolute_path"]
            ext = file_meta["extension"]
            ftype = file_meta["file_type"]

            file_types_count[ftype] = file_types_count.get(ftype, 0) + 1

            file_node_id = f"file:{rel_path}"
            file_node_type = "Document" if ftype in ("markdown", "text") else "Module"

            nodes_dict[file_node_id] = Node(
                id=file_node_id,
                label=os.path.basename(rel_path),
                type=file_node_type,
                path=rel_path,
                description=f"Source file: {rel_path}",
                metadata={"size": file_meta["size"], "extension": ext}
            )

            try:
                with open(abs_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()

                extracted_nodes = []
                extracted_edges = []

                if ftype == "python":
                    extracted_nodes, extracted_edges = CodeParser.parse_python(content, rel_path)
                elif ftype in ("javascript", "typescript"):
                    extracted_nodes, extracted_edges = CodeParser.parse_js_ts(content, rel_path)
                elif ftype in ("sql", "prisma"):
                    extracted_nodes, extracted_edges = CodeParser.parse_sql_prisma(content, rel_path)
                elif ftype == "markdown":
                    extracted_nodes, extracted_edges = DocParser.parse_markdown(content, rel_path)

                for n in extracted_nodes:
                    nid = n["id"]
                    if nid not in nodes_dict:
                        nodes_dict[nid] = Node(**n)

                for e in extracted_edges:
                    edges_list.append(Edge(**e))
                    raw_edges_tuples.append((e["source"], e["target"]))

            except Exception as e:
                print(f"Error indexing file {abs_path}: {e}")

        # 2. Graph analysis & Community detection (NetworkX)
        G = nx.Graph()
        for nid in nodes_dict.keys():
            G.add_node(nid)
        for s, t in raw_edges_tuples:
            G.add_edge(s, t)

        # Calculate communities and God Nodes (Degrees)
        try:
            communities = list(nx.community.greedy_modularity_communities(G))
            for comm_id, comm_nodes in enumerate(communities):
                for nid in comm_nodes:
                    if nid in nodes_dict:
                        nodes_dict[nid].community = comm_id
        except Exception:
            pass

        god_nodes = sorted(G.degree, key=lambda x: x[1], reverse=True)[:10]

        # 3. Create GraphData & Save
        display_name = project_name if project_name else os.path.basename(source_directory)
        graph = GraphData(
            project_id=project_id,
            name=display_name,
            nodes=list(nodes_dict.values()),
            edges=edges_list,
            metadata={
                "source_directory": source_directory,
                "total_files": total_files,
                "file_types": file_types_count,
                "total_nodes": len(nodes_dict),
                "total_edges": len(edges_list)
            }
        )

        GraphStorage.save_graph(graph)

        # 4. Generate GRAPH_REPORT.md
        report_md = cls._generate_report(graph, god_nodes, file_types_count)
        GraphStorage.save_report(project_id, report_md)

        return graph

    @classmethod
    def _generate_report(cls, graph: GraphData, god_nodes: list, file_types: dict) -> str:
        report = f"# 🌐 Reporte de Grafo de Conocimiento: {graph.name}\n\n"
        report += f"- **ID Proyecto:** `{graph.project_id}`\n"
        report += f"- **Directorio Origen:** `{graph.metadata.get('source_directory', 'N/A')}`\n"
        report += f"- **Total Nodos:** `{len(graph.nodes)}`\n"
        report += f"- **Total Conexiones (Aristas):** `{len(graph.edges)}`\n"
        report += f"- **Archivos Analizados:** `{graph.metadata.get('total_files', 0)}`\n\n"

        report += "## 📊 Distribución de Tipos de Archivos\n\n"
        for ft, count in file_types.items():
            report += f"- **{ft.capitalize()}:** {count} archivos\n"

        report += "\n## 👑 Nodos Críticos / God Nodes (Mayor Conectividad)\n\n"
        report += "| Nodo | Conexiones |\n| :--- | :--- |\n"
        for node_id, degree in god_nodes:
            report += f"| `{node_id}` | **{degree}** |\n"

        report += "\n---\n*Generado automáticamente por local_graphs Ingestion Engine.*\n"
        return report
