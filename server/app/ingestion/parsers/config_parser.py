import re
import json
from typing import List, Dict, Any, Tuple
from app.ingestion.parsers.base import BaseParser

class ConfigParser(BaseParser):
    def parse(self, content: str, file_rel_path: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        nodes = []
        edges = []
        file_node_id = f"file:{file_rel_path}"

        # 1. Package.json dependencies
        if file_rel_path.endswith("package.json"):
            try:
                pkg = json.loads(content)
                deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
                for dep in deps.keys():
                    dep_id = f"module:{dep}"
                    nodes.append({
                        "id": dep_id,
                        "label": dep,
                        "type": "Module",
                        "path": None,
                        "description": f"NPM Dependency {dep}"
                    })
                    edges.append({
                        "source": file_node_id,
                        "target": dep_id,
                        "relation": "imports"
                    })
            except Exception:
                pass

        # 2. Composer.json dependencies
        elif file_rel_path.endswith("composer.json"):
            try:
                comp = json.loads(content)
                deps = {**comp.get("require", {}), **comp.get("require-dev", {})}
                for dep in deps.keys():
                    if dep != "php":
                        dep_id = f"module:{dep}"
                        nodes.append({
                            "id": dep_id,
                            "label": dep,
                            "type": "Module",
                            "path": None,
                            "description": f"Composer PHP Package {dep}"
                        })
                        edges.append({
                            "source": file_node_id,
                            "target": dep_id,
                            "relation": "imports"
                        })
            except Exception:
                pass

        # 3. Docker compose / YAML services
        elif file_rel_path.endswith((".yml", ".yaml")):
            # Extract service names
            service_matches = re.findall(r"^\s\s([a-zA-Z0-9_-]+):\s*$", content, re.MULTILINE)
            for sname in service_matches:
                if sname not in ("services", "networks", "volumes", "version", "environment", "ports", "build"):
                    srv_id = f"service:{sname}"
                    nodes.append({
                        "id": srv_id,
                        "label": sname,
                        "type": "Module",
                        "path": file_rel_path,
                        "description": f"Docker Service '{sname}'"
                    })
                    edges.append({
                        "source": file_node_id,
                        "target": srv_id,
                        "relation": "defines"
                    })

        return nodes, edges
