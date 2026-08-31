import re
from typing import List, Dict, Any, Tuple
from app.ingestion.parsers.base import BaseParser

class DiagramParser(BaseParser):
    def parse(self, content: str, file_rel_path: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        nodes = []
        edges = []
        file_node_id = f"file:{file_rel_path}"

        # Mermaid Participants & Nodes (participant Auth, class User, etc.)
        participants = re.findall(r"(?:participant|actor|class|subgraph)\s+([A-Za-z0-9_]+)", content)
        for p in set(participants):
            pid = f"concept:{p}"
            nodes.append({
                "id": pid,
                "label": p,
                "type": "Concept",
                "path": file_rel_path,
                "description": f"Mermaid Diagram Actor/Entity '{p}'"
            })
            edges.append({
                "source": file_node_id,
                "target": pid,
                "relation": "explains"
            })

        return nodes, edges
