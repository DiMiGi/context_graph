import re
from typing import List, Dict, Any, Tuple

class DocParser:
    @classmethod
    def parse_markdown(cls, content: str, file_rel_path: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        nodes = []
        edges = []
        file_node_id = f"file:{file_rel_path}"

        # Extract Headers (# Concept)
        header_matches = re.finditer(r"^(#{1,3})\s+(.+)$", content, re.MULTILINE)
        for m in header_matches:
            level = len(m.group(1))
            title = m.group(2).strip()
            # Clean title
            clean_title = re.sub(r"[^\w\s-]", "", title).strip()
            if len(clean_title) > 2 and len(clean_title) < 60:
                concept_id = f"concept:{file_rel_path}:{clean_title.lower().replace(' ', '_')}"
                nodes.append({
                    "id": concept_id,
                    "label": title,
                    "type": "Concept",
                    "path": file_rel_path,
                    "description": f"Heading H{level} in {file_rel_path}"
                })
                edges.append({
                    "source": file_node_id,
                    "target": concept_id,
                    "relation": "explains"
                })

        # Extract Markdown links [text](path)
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
