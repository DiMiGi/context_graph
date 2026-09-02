import re
import bisect
from typing import List, Dict, Any, Tuple
from app.ingestion.parsers.base import BaseParser

class CsharpParser(BaseParser):
    def parse(self, content: str, file_rel_path: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        nodes = []
        edges = []
        file_node_id = f"file:{file_rel_path}"

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
                elif ch in ('"', "'"):
                    quote = ch
                    i += 1
                    while i < n and content[i] != quote:
                        if content[i] == "\\":
                            i += 1
                        i += 1
                i += 1
            return get_line(i - 1 if i <= n else n - 1)

        def get_xmldoc(pos: int) -> str:
            sub = content[:pos].rstrip()
            doc_lines = []
            for line in reversed(sub.splitlines()):
                line_s = line.strip()
                if line_s.startswith("///"):
                    doc_lines.append(line_s.lstrip("/").strip())
                elif doc_lines:
                    break
            if doc_lines:
                doc_lines.reverse()
                raw = " ".join(doc_lines)
                clean = re.sub(r"<[^>]+>", "", raw).strip()
                return clean[:300]
            return ""

        # 1. Using statements
        using_matches = re.findall(r"using\s+([A-Za-z0-9_\.]+);", content)
        for u in using_matches:
            imp_id = f"module:{u}"
            nodes.append({
                "id": imp_id,
                "label": u,
                "type": "Module",
                "path": None,
                "description": f"Imported C# Namespace {u}"
            })
            edges.append({
                "source": file_node_id,
                "target": imp_id,
                "relation": "imports"
            })

        # 2. Classes & Entity Framework [Table("...")]
        class_matches = re.finditer(
            r"(?:\[Table\([\"'](.*?)[\"']\)\].*?)?(public|internal|private)?\s*(?:static|abstract|sealed)?\s*(class|interface|struct)\s+([A-Za-z0-9_]+)(?:\s*:\s*([A-Za-z0-9_,\s]+))?",
            content,
            re.DOTALL
        )

        current_class_id = None
        for m in class_matches:
            table_name = m.group(1)
            visibility = m.group(2) or "internal"
            kind = m.group(3)
            class_name = m.group(4)
            inheritance = m.group(5)

            if not class_name:
                continue

            class_node_id = f"class:{file_rel_path}:{class_name}"
            current_class_id = class_node_id
            start_l = get_line(m.start())
            end_l = get_end_line(m.start())
            doc = get_xmldoc(m.start())

            bases = []
            if inheritance:
                bases = [p.strip() for p in inheritance.split(",") if p.strip()]

            nodes.append({
                "id": class_node_id,
                "label": class_name,
                "type": "Class" if kind == "class" else kind.capitalize(),
                "path": file_rel_path,
                "description": f"C# {kind} {class_name} (L{start_l}-L{end_l}) in {file_rel_path}",
                "metadata": {
                    "start_line": start_l,
                    "end_line": end_l,
                    "visibility": visibility,
                    "kind": kind,
                    "bases": bases,
                    "docstring": doc
                }
            })
            edges.append({
                "source": file_node_id,
                "target": class_node_id,
                "relation": "defines"
            })
            edges.append({
                "source": class_node_id,
                "target": file_node_id,
                "relation": "declared_in"
            })

            # Vincular los usings a la clase
            for u in using_matches:
                edges.append({
                    "source": class_node_id,
                    "target": f"module:{u}",
                    "relation": "uses"
                })

            if inheritance:
                for parent in bases:
                    edges.append({
                        "source": class_node_id,
                        "target": f"class:{parent}",
                        "relation": "inherits"
                    })

            if table_name:
                table_id = f"schema:{table_name}"
                tbl_line = get_line(m.start())
                nodes.append({
                    "id": table_id,
                    "label": table_name,
                    "type": "Schema",
                    "path": file_rel_path,
                    "description": f"Entity Framework database table '{table_name}'",
                    "metadata": {"start_line": tbl_line, "end_line": tbl_line}
                })
                edges.append({
                    "source": class_node_id,
                    "target": table_id,
                    "relation": "maps_to_table"
                })
                edges.append({
                    "source": table_id,
                    "target": class_node_id,
                    "relation": "mapped_by"
                })

        # 3. Methods
        method_matches = re.finditer(
            r"(public|protected|private|internal)\s+(static\s+|virtual\s+|async\s+|override\s+)?([A-Za-z0-9_<>\[\]]+)\s+([A-Za-z0-9_]+)\s*\((.*?)\)",
            content
        )
        for m in method_matches:
            visibility = m.group(1)
            modifier = (m.group(2) or "").strip()
            ret_type = m.group(3)
            method_name = m.group(4)
            params_raw = m.group(5) or ""

            if method_name in ("if", "for", "foreach", "while", "switch", "catch"):
                continue

            mid = f"func:{file_rel_path}:{method_name}"
            start_l = get_line(m.start())
            end_l = get_end_line(m.start())
            doc = get_xmldoc(m.start())
            is_async = "async" in modifier

            params = []
            if params_raw:
                for p in params_raw.split(","):
                    p_str = p.strip()
                    if p_str:
                        parts = p_str.split()
                        if len(parts) >= 2:
                            params.append({"name": parts[-1], "type": " ".join(parts[:-1])})
                        else:
                            params.append({"name": p_str, "type": None})

            signature = f"{visibility} {modifier + ' ' if modifier else ''}{ret_type} {method_name}({params_raw})"

            nodes.append({
                "id": mid,
                "label": method_name,
                "type": "Function",
                "path": file_rel_path,
                "description": f"C# Method {method_name}() (L{start_l}-L{end_l}) in {file_rel_path}",
                "metadata": {
                    "start_line": start_l,
                    "end_line": end_l,
                    "signature": signature,
                    "visibility": visibility,
                    "return_type": ret_type,
                    "is_async": is_async,
                    "parameters": params,
                    "docstring": doc
                }
            })

            parent_id = current_class_id if current_class_id else file_node_id
            edges.append({
                "source": parent_id,
                "target": mid,
                "relation": "defines"
            })
            edges.append({
                "source": mid,
                "target": file_node_id,
                "relation": "declared_in"
            })

        return nodes, edges
