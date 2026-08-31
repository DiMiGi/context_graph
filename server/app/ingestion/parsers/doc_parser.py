import re
from typing import List, Dict, Any, Tuple
from app.ingestion.parsers.base import BaseParser

class DocParser(BaseParser):
    def parse(self, content: str, file_rel_path: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        nodes = []
        edges = []
        file_node_id = f"file:{file_rel_path}"

        # Headers H1, H2, H3
        header_matches = re.finditer(r"^(#{1,3})\s+(.+)$", content, re.MULTILINE)
        for m in header_matches:
            level = len(m.group(1))
            title = m.group(2).strip()
            clean_title = re.sub(r"[^\w\s-]", "", title).strip()
            if 2 < len(clean_title) < 60:
                cid = f"concept:{file_rel_path}:{clean_title.lower().replace(' ', '_')}"
                nodes.append({
                    "id": cid,
                    "label": title,
                    "type": "Concept",
                    "path": file_rel_path,
                    "description": f"Markdown Heading H{level} in {file_rel_path}"
                })
                edges.append({
                    "source": file_node_id,
                    "target": cid,
                    "relation": "explains"
                })

        # Links
        link_matches = re.findall(r"\[(.*?)\]\((.*?)\)", content)
        for text, target in link_matches:
            if not target.startswith("http") and not target.startswith("#"):
                clean_target = target.split("#")[0].lstrip("./")
                if clean_target:
                    edges.append({
                        "source": file_node_id,
                        "target": f"file:{clean_target}",
                        "relation": "references"
                    })

        return nodes, edges
