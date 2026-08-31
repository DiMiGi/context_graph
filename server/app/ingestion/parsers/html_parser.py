import re
from typing import List, Dict, Any, Tuple
from app.ingestion.parsers.base import BaseParser

class HtmlParser(BaseParser):
    def parse(self, content: str, file_rel_path: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        nodes = []
        edges = []
        file_node_id = f"file:{file_rel_path}"

        # 1. Title
        title_match = re.search(r"<title>(.*?)</title>", content, re.IGNORECASE)
        page_title = title_match.group(1).strip() if title_match else file_rel_path

        # 2. Script references (<script src="...">)
        scripts = re.findall(r'<script\s+[^>]*src=["\'](.*?)["\']', content, re.IGNORECASE)
        for s in scripts:
            if not s.startswith("http"):
                clean_s = s.split("?")[0].lstrip("./")
                edges.append({
                    "source": file_node_id,
                    "target": f"file:{clean_s}",
                    "relation": "imports"
                })

        # 3. Stylesheet references (<link rel="stylesheet" href="...">)
        links = re.findall(r'<link\s+[^>]*href=["\'](.*?)["\']', content, re.IGNORECASE)
        for l in links:
            if not l.startswith("http") and (l.endswith(".css") or "css" in l):
                clean_l = l.split("?")[0].lstrip("./")
                edges.append({
                    "source": file_node_id,
                    "target": f"file:{clean_l}",
                    "relation": "references"
                })

        # 4. Form Actions (<form action="...">)
        forms = re.findall(r'<form\s+[^>]*action=["\'](.*?)["\']', content, re.IGNORECASE)
        for act in forms:
            if act and not act.startswith("#") and not act.startswith("javascript:"):
                act_id = f"route:{act}"
                nodes.append({
                    "id": act_id,
                    "label": act,
                    "type": "Concept",
                    "path": file_rel_path,
                    "description": f"HTML Form target route '{act}'"
                })
                edges.append({
                    "source": file_node_id,
                    "target": act_id,
                    "relation": "calls"
                })

        return nodes, edges
