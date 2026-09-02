import re
import bisect
from typing import List, Dict, Any, Tuple
from app.ingestion.parsers.base import BaseParser

class JsTsParser(BaseParser):
    def parse(self, content: str, file_rel_path: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        nodes = []
        edges = []
        file_node_id = f"file:{file_rel_path}"
        imported_modules = []

        line_offsets = [0] + [m.end() for m in re.finditer(r"\n", content)]
        total_lines = len(line_offsets)

        def get_line(pos: int) -> int:
            return bisect.bisect_right(line_offsets, pos)

        def get_end_line(start_pos: int) -> int:
            idx = content.find("{", start_pos)
            if idx == -1:
                return get_line(start_pos)
            depth = 1
            i = idx + 1
            n = len(content)
            while i < n and depth > 0:
                ch = content[i]
                if ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                elif ch in ('"', "'", '`'):
                    quote = ch
                    i += 1
                    while i < n and content[i] != quote:
                        if content[i] == "\\":
                            i += 1
                        i += 1
                i += 1
            return get_line(i - 1 if i <= n else n - 1)

        def get_jsdoc(pos: int) -> str:
            sub = content[:pos].rstrip()
            if sub.endswith("*/"):
                start_doc = sub.rfind("/**")
                if start_doc != -1:
                    raw_doc = sub[start_doc + 3:-2]
                    clean = "\n".join(l.strip().lstrip("*").strip() for l in raw_doc.splitlines())
                    return clean.strip()[:300]
            return ""

        # 1. Imports
        for m in re.finditer(r"import\s+(?:.*?from\s+)?['\"](.*?)['\"]", content):
            imp = m.group(1)
            imp_id = f"module:{imp}"
            if imp_id not in imported_modules:
                imported_modules.append(imp_id)
                nodes.append({
                    "id": imp_id,
                    "label": imp,
                    "type": "Module",
                    "path": None,
                    "description": f"Imported module {imp}",
                    "metadata": {"start_line": get_line(m.start())}
                })
                edges.append({"source": file_node_id, "target": imp_id, "relation": "imports"})

        # 2. Classes & TypeORM @Entity('table_name')
        class_matches = re.finditer(
            r"(?:@Entity\([\"'](.*?)[\"']\)\s*)?(?:export\s+)?(?:default\s+)?class\s+([A-Za-z0-9_]+)(?:\s+extends\s+([A-Za-z0-9_]+))?(?:\s+implements\s+([A-Za-z0-9_,\s]+))?",
            content
        )
        current_class_id = None
        for m in class_matches:
            tbl_name = m.group(1)
            cname = m.group(2)
            extends_name = m.group(3)
            implements_names = m.group(4)
            cid = f"class:{file_rel_path}:{cname}"
            current_class_id = cid

            start_l = get_line(m.start())
            end_l = get_end_line(m.start())
            doc = get_jsdoc(m.start())

            bases = []
            if extends_name:
                bases.append(extends_name)

            implements_list = [i.strip() for i in implements_names.split(",") if i.strip()] if implements_names else []

            nodes.append({
                "id": cid,
                "label": cname,
                "type": "Class",
                "path": file_rel_path,
                "description": f"Class {cname} (L{start_l}-L{end_l}) in {file_rel_path}",
                "metadata": {
                    "start_line": start_l,
                    "end_line": end_l,
                    "bases": bases,
                    "implements": implements_list,
                    "docstring": doc
                }
            })
            edges.append({"source": file_node_id, "target": cid, "relation": "defines"})
            edges.append({"source": cid, "target": file_node_id, "relation": "declared_in"})

            for mod_id in imported_modules:
                edges.append({"source": cid, "target": mod_id, "relation": "uses"})

            if extends_name:
                edges.append({"source": cid, "target": f"class:{extends_name}", "relation": "inherits"})

            for iface in implements_list:
                edges.append({"source": cid, "target": f"class:{iface}", "relation": "implements"})

            if tbl_name:
                tid = f"schema:{tbl_name}"
                nodes.append({
                    "id": tid,
                    "label": tbl_name,
                    "type": "Schema",
                    "path": file_rel_path,
                    "description": f"TypeORM Entity table '{tbl_name}'",
                    "metadata": {"start_line": start_l, "end_line": end_l}
                })
                edges.append({"source": cid, "target": tid, "relation": "maps_to_table"})
                edges.append({"source": tid, "target": cid, "relation": "mapped_by"})

        # 3. Functions & Arrow functions
        func_matches = re.finditer(
            r"(?:export\s+)?(?:async\s+)?function\s+([A-Za-z0-9_]+)\s*\((.*?)\)(?:\s*:\s*([^{]+))?|(?:export\s+)?(?:const|let|var)\s+([A-Za-z0-9_]+)\s*=\s*(?:async\s*)?\((.*?)\)(?:\s*:\s*([^=]+))?\s*=>",
            content
        )
        for m in func_matches:
            fname = m.group(1) or m.group(4)
            params_raw = m.group(2) if m.group(1) else m.group(5)
            ret_type = (m.group(3) if m.group(1) else m.group(6)) or None
            if ret_type:
                ret_type = ret_type.strip()

            if fname:
                fid = f"func:{file_rel_path}:{fname}"
                start_l = get_line(m.start())
                end_l = get_end_line(m.start())
                doc = get_jsdoc(m.start())
                is_async = "async" in m.group(0)

                params = []
                if params_raw:
                    for p in params_raw.split(","):
                        p_str = p.strip()
                        if p_str:
                            p_parts = p_str.split(":")
                            p_name = p_parts[0].strip()
                            p_type = p_parts[1].strip() if len(p_parts) > 1 else None
                            params.append({"name": p_name, "type": p_type})

                async_prefix = "async " if is_async else ""
                ret_suffix = f": {ret_type}" if ret_type else ""
                signature = f"{async_prefix}function {fname}({params_raw or ''}){ret_suffix}"

                nodes.append({
                    "id": fid,
                    "label": fname,
                    "type": "Function",
                    "path": file_rel_path,
                    "description": f"Function {fname} (L{start_l}-L{end_l}) in {file_rel_path}",
                    "metadata": {
                        "start_line": start_l,
                        "end_line": end_l,
                        "signature": signature,
                        "parameters": params,
                        "return_type": ret_type,
                        "is_async": is_async,
                        "docstring": doc
                    }
                })
                parent_id = current_class_id if current_class_id else file_node_id
                edges.append({"source": parent_id, "target": fid, "relation": "defines"})
                edges.append({"source": fid, "target": file_node_id, "relation": "declared_in"})

        return nodes, edges
