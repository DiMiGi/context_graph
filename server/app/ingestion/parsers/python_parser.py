import re
from typing import List, Dict, Any, Tuple
from app.ingestion.parsers.base import BaseParser

class PythonParser(BaseParser):
    def parse(self, content: str, file_rel_path: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        nodes = []
        edges = []
        file_node_id = f"file:{file_rel_path}"
        imported_modules = []

        # 1. Imports
        for imp in re.findall(r"^(?:from\s+([\w\.]+)\s+import\s+([\w\s,\*]+)|import\s+([\w\.]+))", content, re.MULTILINE):
            mod = imp[0] or imp[2]
            if mod:
                imp_id = f"module:{mod}"
                imported_modules.append(imp_id)
                nodes.append({
                    "id": imp_id,
                    "label": mod,
                    "type": "Module",
                    "path": None,
                    "description": f"Imported Python module {mod}"
                })
                edges.append({"source": file_node_id, "target": imp_id, "relation": "imports"})

        # 2. Classes & Database Tables (__tablename__ / Meta db_table)
        class_matches = re.finditer(r"^class\s+([A-Za-z0-9_]+)(?:\((.*?)\))?:", content, re.MULTILINE)
        current_class_id = None
        for m in class_matches:
            cname = m.group(1)
            bases = m.group(2)
            cid = f"class:{file_rel_path}:{cname}"
            current_class_id = cid

            nodes.append({
                "id": cid,
                "label": cname,
                "type": "Class",
                "path": file_rel_path,
                "description": f"Python Class {cname} in {file_rel_path}"
            })
            edges.append({"source": file_node_id, "target": cid, "relation": "defines"})
            edges.append({"source": cid, "target": file_node_id, "relation": "declared_in"})

            for mod_id in imported_modules:
                edges.append({"source": cid, "target": mod_id, "relation": "uses"})

            if bases:
                for base in [b.strip() for b in bases.split(",") if b.strip()]:
                    edges.append({"source": cid, "target": f"class:{base}", "relation": "inherits"})

        # SQLAlchemy __tablename__
        table_matches = re.findall(r"__tablename__\s*=\s*['\"](.*?)['\"]", content)
        for tbl in table_matches:
            tid = f"schema:{tbl}"
            nodes.append({
                "id": tid,
                "label": tbl,
                "type": "Schema",
                "path": file_rel_path,
                "description": f"SQLAlchemy database table '{tbl}'"
            })
            if current_class_id:
                edges.append({"source": current_class_id, "target": tid, "relation": "maps_to_table"})
                edges.append({"source": tid, "target": current_class_id, "relation": "mapped_by"})

        # 3. Functions
        for m in re.finditer(r"^(?:\s*async\s+)?def\s+([A-Za-z0-9_]+)\s*\(", content, re.MULTILINE):
            fname = m.group(1)
            fid = f"func:{file_rel_path}:{fname}"
            nodes.append({
                "id": fid,
                "label": fname,
                "type": "Function",
                "path": file_rel_path,
                "description": f"Python function {fname} in {file_rel_path}"
            })
            parent_id = current_class_id if current_class_id else file_node_id
            edges.append({"source": parent_id, "target": fid, "relation": "defines"})
            edges.append({"source": fid, "target": file_node_id, "relation": "declared_in"})

        return nodes, edges
