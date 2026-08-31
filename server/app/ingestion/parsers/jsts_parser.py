import re
from typing import List, Dict, Any, Tuple
from app.ingestion.parsers.base import BaseParser

class JsTsParser(BaseParser):
    def parse(self, content: str, file_rel_path: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        nodes = []
        edges = []
        file_node_id = f"file:{file_rel_path}"
        imported_modules = []

        # 1. Imports
        for imp in re.findall(r"import\s+(?:.*?from\s+)?['\"](.*?)['\"]", content):
            imp_id = f"module:{imp}"
            imported_modules.append(imp_id)
            nodes.append({
                "id": imp_id,
                "label": imp,
                "type": "Module",
                "path": None,
                "description": f"Imported module {imp}"
            })
            edges.append({"source": file_node_id, "target": imp_id, "relation": "imports"})

        # 2. Classes & TypeORM @Entity('table_name')
        class_matches = re.finditer(
            r"(?:@Entity\([\"'](.*?)[\"']\)\s*)?(?:export\s+)?(?:default\s+)?class\s+([A-Za-z0-9_]+)(?:\s+extends\s+([A-Za-z0-9_]+))?",
            content
        )
        current_class_id = None
        for m in class_matches:
            tbl_name = m.group(1)
            cname = m.group(2)
            extends_name = m.group(3)
            cid = f"class:{file_rel_path}:{cname}"
            current_class_id = cid

            nodes.append({
                "id": cid,
                "label": cname,
                "type": "Class",
                "path": file_rel_path,
                "description": f"Class {cname} in {file_rel_path}"
            })
            edges.append({"source": file_node_id, "target": cid, "relation": "defines"})
            edges.append({"source": cid, "target": file_node_id, "relation": "declared_in"})

            for mod_id in imported_modules:
                edges.append({"source": cid, "target": mod_id, "relation": "uses"})

            if extends_name:
                edges.append({"source": cid, "target": f"class:{extends_name}", "relation": "inherits"})

            if tbl_name:
                tid = f"schema:{tbl_name}"
                nodes.append({
                    "id": tid,
                    "label": tbl_name,
                    "type": "Schema",
                    "path": file_rel_path,
                    "description": f"TypeORM Entity table '{tbl_name}'"
                })
                edges.append({"source": cid, "target": tid, "relation": "maps_to_table"})
                edges.append({"source": tid, "target": cid, "relation": "mapped_by"})

        # 3. Functions & Arrow functions
        func_matches = re.finditer(
            r"(?:export\s+)?(?:async\s+)?function\s+([A-Za-z0-9_]+)|(?:const|let|var)\s+([A-Za-z0-9_]+)\s*=\s*(?:async\s*)?\([^)]*\)\s*=>",
            content
        )
        for m in func_matches:
            fname = m.group(1) or m.group(2)
            if fname:
                fid = f"func:{file_rel_path}:{fname}"
                nodes.append({
                    "id": fid,
                    "label": fname,
                    "type": "Function",
                    "path": file_rel_path,
                    "description": f"Function {fname} in {file_rel_path}"
                })
                parent_id = current_class_id if current_class_id else file_node_id
                edges.append({"source": parent_id, "target": fid, "relation": "defines"})
                edges.append({"source": fid, "target": file_node_id, "relation": "declared_in"})

        return nodes, edges
