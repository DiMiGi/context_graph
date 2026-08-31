import re
from typing import List, Dict, Any, Tuple
from app.ingestion.parsers.base import BaseParser

class GenericCodeParser(BaseParser):
    def parse(self, content: str, file_rel_path: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        nodes = []
        edges = []
        file_node_id = f"file:{file_rel_path}"

        # Heuristic for Classes / Structs
        for m in re.finditer(r"(?:class|struct|interface|type)\s+([A-Za-z0-9_]+)", content):
            cname = m.group(1)
            cid = f"class:{file_rel_path}:{cname}"
            nodes.append({
                "id": cid,
                "label": cname,
                "type": "Class",
                "path": file_rel_path,
                "description": f"Entity {cname} in {file_rel_path}"
            })
            edges.append({"source": file_node_id, "target": cid, "relation": "defines"})

        # Heuristic for Functions
        for m in re.finditer(r"(?:fn|func|def|function|sub)\s+([A-Za-z0-9_]+)\s*\(", content):
            fname = m.group(1)
            fid = f"func:{file_rel_path}:{fname}"
            nodes.append({
                "id": fid,
                "label": fname,
                "type": "Function",
                "path": file_rel_path,
                "description": f"Function {fname} in {file_rel_path}"
            })
            edges.append({"source": file_node_id, "target": fid, "relation": "defines"})

        return nodes, edges
