import json
import os
import shutil
from typing import Optional, List, Dict, Any
from app.config import DATA_PATH
from app.graph.model import GraphData, Node, Edge

class GraphStorage:
    @staticmethod
    def sanitize_branch(branch: Optional[str]) -> str:
        """Sanitiza el nombre de la rama para usar como directorio seguro."""
        if not branch or not branch.strip():
            return "main"
        b = branch.strip().replace("\\", "/").replace("/", "__").replace(":", "_")
        # Mantener solo caracteres alfanuméricos, guiones y underscores
        safe = "".join(c for c in b if c.isalnum() or c in ("-", "_", "."))
        return safe or "main"

    @classmethod
    def get_project_base_dir(cls, project_id: str) -> str:
        safe_id = "".join(c for c in project_id if c.isalnum() or c in ("-", "_")).strip()
        if not safe_id:
            safe_id = "default_project"
        return os.path.join(DATA_PATH, safe_id)

    @classmethod
    def get_project_dir(cls, project_id: str, branch: Optional[str] = None) -> str:
        base_dir = cls.get_project_base_dir(project_id)
        if branch:
            safe_b = cls.sanitize_branch(branch)
            return os.path.join(base_dir, safe_b)
        
        # Si branch no se pasa, verificar si hay ramas en subcarpetas
        # o si existe archivo legado en la raíz del proyecto
        legacy_graph = os.path.join(base_dir, "graph.json")
        if os.path.exists(legacy_graph):
            return base_dir
            
        return os.path.join(base_dir, "main")

    @classmethod
    def get_graph_file(cls, project_id: str, branch: Optional[str] = None) -> str:
        if branch:
            return os.path.join(cls.get_project_dir(project_id, branch), "graph.json")
        
        base_dir = cls.get_project_base_dir(project_id)
        legacy_graph = os.path.join(base_dir, "graph.json")
        if os.path.exists(legacy_graph):
            return legacy_graph
            
        return os.path.join(cls.get_project_dir(project_id, "main"), "graph.json")

    @classmethod
    def get_report_file(cls, project_id: str, branch: Optional[str] = None) -> str:
        if branch:
            return os.path.join(cls.get_project_dir(project_id, branch), "GRAPH_REPORT.md")
            
        base_dir = cls.get_project_base_dir(project_id)
        legacy_report = os.path.join(base_dir, "GRAPH_REPORT.md")
        if os.path.exists(legacy_report):
            return legacy_report
            
        return os.path.join(cls.get_project_dir(project_id, "main"), "GRAPH_REPORT.md")

    @classmethod
    def list_branches(cls, project_id: str) -> List[Dict[str, Any]]:
        """Lista todas las ramas indexadas en disco para un proyecto."""
        base_dir = cls.get_project_base_dir(project_id)
        if not os.path.exists(base_dir):
            return []

        branches = []
        
        # 1. Comprobar subdirectorios de ramas
        try:
            for entry in os.listdir(base_dir):
                branch_dir = os.path.join(base_dir, entry)
                if os.path.isdir(branch_dir):
                    graph_file = os.path.join(branch_dir, "graph.json")
                    if os.path.exists(graph_file):
                        try:
                            with open(graph_file, "r", encoding="utf-8") as f:
                                data = json.load(f)
                                meta = data.get("metadata", {})
                                branch_name = meta.get("branch", entry.replace("__", "/"))
                                branches.append({
                                    "branch": branch_name,
                                    "safe_branch": entry,
                                    "nodes_count": len(data.get("nodes", [])),
                                    "edges_count": len(data.get("edges", [])),
                                    "commit_hash": meta.get("commit_hash", ""),
                                    "short_hash": meta.get("commit_short", meta.get("commit_hash", "")[:8]),
                                    "commit_message": meta.get("commit_message", ""),
                                    "updated_at": os.path.getmtime(graph_file)
                                })
                        except Exception as e:
                            print(f"Error reading branch {entry} for {project_id}: {e}")
        except Exception:
            pass

        # 2. Comprobar si hay archivo legado en la raíz
        legacy_graph = os.path.join(base_dir, "graph.json")
        if os.path.exists(legacy_graph):
            try:
                with open(legacy_graph, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    meta = data.get("metadata", {})
                    branch_name = meta.get("branch", "legacy")
                    if not any(b["branch"] == branch_name for b in branches):
                        branches.append({
                            "branch": branch_name,
                            "safe_branch": "legacy",
                            "nodes_count": len(data.get("nodes", [])),
                            "edges_count": len(data.get("edges", [])),
                            "commit_hash": meta.get("commit_hash", ""),
                            "short_hash": meta.get("commit_short", meta.get("commit_hash", "")[:8]),
                            "commit_message": meta.get("commit_message", ""),
                            "updated_at": os.path.getmtime(legacy_graph)
                        })
            except Exception:
                pass

        return sorted(branches, key=lambda x: x["updated_at"], reverse=True)

    @classmethod
    def list_projects(cls) -> List[Dict[str, Any]]:
        from app.config import get_configured_projects
        from app.services.git_service import GitService
        os.makedirs(DATA_PATH, exist_ok=True)
        configured = get_configured_projects()
        projects = []
        
        for cp in configured:
            pid = cp.get("id")
            if not pid:
                continue

            host_path = cp.get("host_path", "")
            pid_clean = pid.lower()
            inferred_container_path = cp.get("container_path", f"/sources/{pid_clean}")
            name = cp.get("name", pid)

            # Extraer info de Git desde el directorio fuente
            from app.services.project_service import ProjectService
            source_path = ProjectService.get_source_path(pid)
            git_info = GitService.get_git_info(source_path) if source_path else {}
            active_git_branch = git_info.get("branch", "main")
            
            # Listar ramas indexadas
            indexed_branches = cls.list_branches(pid)
            
            # Buscar métricas de la rama activa o de la más reciente
            active_branch_data = next((b for b in indexed_branches if b["branch"] == active_git_branch), None)
            if not active_branch_data and indexed_branches:
                active_branch_data = indexed_branches[0]

            node_count = active_branch_data["nodes_count"] if active_branch_data else 0
            edge_count = active_branch_data["edges_count"] if active_branch_data else 0
            updated_at = active_branch_data["updated_at"] if active_branch_data else 0.0

            projects.append({
                "id": pid,
                "name": name,
                "nodes_count": node_count,
                "edges_count": edge_count,
                "updated_at": updated_at,
                "container_path": inferred_container_path,
                "is_configured": True,
                "git_branch": active_git_branch,
                "commit_hash": git_info.get("commit_hash", ""),
                "short_hash": git_info.get("short_hash", ""),
                "commit_message": git_info.get("commit_message", ""),
                "is_dirty": git_info.get("is_dirty", False),
                "is_git_repo": git_info.get("is_git_repo", False),
                "branches": indexed_branches
            })
            
        return sorted(projects, key=lambda x: x["updated_at"], reverse=True)

    @classmethod
    def create_project(cls, project_id: str, name: Optional[str] = None, branch: Optional[str] = None) -> GraphData:
        proj_dir = cls.get_project_dir(project_id, branch)
        os.makedirs(proj_dir, exist_ok=True)
        display_name = name if name else project_id
        graph = GraphData(
            project_id=project_id,
            name=display_name,
            nodes=[],
            edges=[],
            metadata={"created_at": os.path.getmtime(proj_dir), "branch": branch or "main"}
        )
        cls.save_graph(graph, branch)
        return graph

    @classmethod
    def delete_project(cls, project_id: str, branch: Optional[str] = None) -> bool:
        if branch:
            branch_dir = cls.get_project_dir(project_id, branch)
            if os.path.exists(branch_dir):
                shutil.rmtree(branch_dir)
                return True
            return False
            
        base_dir = cls.get_project_base_dir(project_id)
        if os.path.exists(base_dir):
            shutil.rmtree(base_dir)
            return True
        return False

    @classmethod
    def load_graph(cls, project_id: str, branch: Optional[str] = None) -> Optional[GraphData]:
        graph_file = cls.get_graph_file(project_id, branch)
        if not os.path.exists(graph_file):
            # Si no existe en la rama solicitada pero existe en otra o como legado, intentar fallback
            if branch:
                fallback = cls.get_graph_file(project_id, None)
                if os.path.exists(fallback):
                    graph_file = fallback
                else:
                    return None
            else:
                return None
        try:
            with open(graph_file, "r", encoding="utf-8") as f:
                raw = json.load(f)
                return GraphData(**raw)
        except Exception as e:
            print(f"Error loading graph for {project_id} (branch: {branch}): {e}")
            return None

    @classmethod
    def save_graph(cls, graph: GraphData, branch: Optional[str] = None) -> bool:
        effective_branch = branch or graph.metadata.get("branch")
        proj_dir = cls.get_project_dir(graph.project_id, effective_branch)
        os.makedirs(proj_dir, exist_ok=True)
        graph_file = os.path.join(proj_dir, "graph.json")
        tmp_file = f"{graph_file}.tmp"
        try:
            with open(tmp_file, "w", encoding="utf-8") as f:
                json.dump(graph.model_dump(), f, indent=2, ensure_ascii=False)
            os.replace(tmp_file, graph_file)
            return True
        except Exception as e:
            print(f"Error saving graph for {graph.project_id} (branch: {effective_branch}): {e}")
            if os.path.exists(tmp_file):
                os.remove(tmp_file)
            return False

    @classmethod
    def load_report(cls, project_id: str, branch: Optional[str] = None) -> str:
        report_file = cls.get_report_file(project_id, branch)
        if os.path.exists(report_file):
            with open(report_file, "r", encoding="utf-8") as f:
                return f.read()
        return "# Reporte no generado aún\n\nEjecuta la indexación del proyecto para generar este reporte."

    @classmethod
    def save_report(cls, project_id: str, content: str, branch: Optional[str] = None) -> bool:
        proj_dir = cls.get_project_dir(project_id, branch)
        os.makedirs(proj_dir, exist_ok=True)
        report_file = os.path.join(proj_dir, "GRAPH_REPORT.md")
        with open(report_file, "w", encoding="utf-8") as f:
            f.write(content)
        return True
