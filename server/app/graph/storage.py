import json
import os
import shutil
from typing import Optional, List, Dict, Any
from app.config import DATA_PATH
from app.graph.model import GraphData, Node, Edge

class GraphStorage:
    @staticmethod
    def get_project_dir(project_id: str) -> str:
        safe_id = "".join(c for c in project_id if c.isalnum() or c in ("-", "_")).strip()
        if not safe_id:
            safe_id = "default_project"
        return os.path.join(DATA_PATH, safe_id)

    @staticmethod
    def get_graph_file(project_id: str) -> str:
        return os.path.join(GraphStorage.get_project_dir(project_id), "graph.json")

    @staticmethod
    def get_report_file(project_id: str) -> str:
        return os.path.join(GraphStorage.get_project_dir(project_id), "GRAPH_REPORT.md")

    @classmethod
    def list_projects(cls) -> List[Dict[str, Any]]:
        os.makedirs(DATA_PATH, exist_ok=True)
        projects = []
        for item in os.listdir(DATA_PATH):
            full_path = os.path.join(DATA_PATH, item)
            if os.path.isdir(full_path) and not item.startswith("."):
                graph_path = os.path.join(full_path, "graph.json")
                node_count = 0
                edge_count = 0
                name = item
                updated_at = os.path.getmtime(full_path)
                
                if os.path.exists(graph_path):
                    try:
                        with open(graph_path, "r", encoding="utf-8") as f:
                            data = json.load(f)
                            node_count = len(data.get("nodes", []))
                            edge_count = len(data.get("edges", []))
                            name = data.get("name", item)
                    except Exception:
                        pass
                
                projects.append({
                    "id": item,
                    "name": name,
                    "nodes_count": node_count,
                    "edges_count": edge_count,
                    "updated_at": updated_at
                })
        return sorted(projects, key=lambda x: x["updated_at"], reverse=True)

    @classmethod
    def create_project(cls, project_id: str, name: Optional[str] = None) -> GraphData:
        proj_dir = cls.get_project_dir(project_id)
        os.makedirs(proj_dir, exist_ok=True)
        display_name = name if name else project_id
        graph = GraphData(
            project_id=project_id,
            name=display_name,
            nodes=[],
            edges=[],
            metadata={"created_at": os.path.getmtime(proj_dir)}
        )
        cls.save_graph(graph)
        return graph

    @classmethod
    def delete_project(cls, project_id: str) -> bool:
        proj_dir = cls.get_project_dir(project_id)
        if os.path.exists(proj_dir):
            shutil.rmtree(proj_dir)
            return True
        return False

    @classmethod
    def load_graph(cls, project_id: str) -> Optional[GraphData]:
        graph_file = cls.get_graph_file(project_id)
        if not os.path.exists(graph_file):
            return None
        try:
            with open(graph_file, "r", encoding="utf-8") as f:
                raw = json.load(f)
                return GraphData(**raw)
        except Exception as e:
            print(f"Error loading graph for {project_id}: {e}")
            return None

    @classmethod
    def save_graph(cls, graph: GraphData) -> bool:
        proj_dir = cls.get_project_dir(graph.project_id)
        os.makedirs(proj_dir, exist_ok=True)
        graph_file = cls.get_graph_file(graph.project_id)
        tmp_file = f"{graph_file}.tmp"
        try:
            with open(tmp_file, "w", encoding="utf-8") as f:
                json.dump(graph.model_dump(), f, indent=2, ensure_ascii=False)
            os.replace(tmp_file, graph_file)
            return True
        except Exception as e:
            print(f"Error saving graph for {graph.project_id}: {e}")
            if os.path.exists(tmp_file):
                os.remove(tmp_file)
            return False

    @classmethod
    def load_report(cls, project_id: str) -> str:
        report_file = cls.get_report_file(project_id)
        if os.path.exists(report_file):
            with open(report_file, "r", encoding="utf-8") as f:
                return f.read()
        return "# Reporte no generado aún\n\nEjecuta la indexación del proyecto para generar este reporte."

    @classmethod
    def save_report(cls, project_id: str, content: str) -> bool:
        proj_dir = cls.get_project_dir(project_id)
        os.makedirs(proj_dir, exist_ok=True)
        report_file = cls.get_report_file(project_id)
        with open(report_file, "w", encoding="utf-8") as f:
            f.write(content)
        return True
