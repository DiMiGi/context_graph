import re
from typing import List, Dict, Any, Tuple
from app.ingestion.parsers.base import BaseParser

class StyleParser(BaseParser):
    def parse(self, content: str, file_rel_path: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        nodes = []
        edges = []
        file_node_id = f"file:{file_rel_path}"

        # CSS @import
        imports = re.findall(r"@import\s+(?:url\()?['\"](.*?)['\"]\)?;", content)
        for imp in imports:
            if not imp.startswith("http"):
                clean_imp = imp.lstrip("./")
                edges.append({
                    "source": file_node_id,
                    "target": f"file:{clean_imp}",
                    "relation": "imports"
                })

        return nodes, edges
