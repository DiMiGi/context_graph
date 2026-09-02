import ast
import re
from typing import List, Dict, Any, Tuple
from app.ingestion.parsers.base import BaseParser

class PythonParser(BaseParser):
    def parse(self, content: str, file_rel_path: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        nodes = []
        edges = []
        file_node_id = f"file:{file_rel_path}"
        total_lines = len(content.splitlines())

        try:
            tree = ast.parse(content)
            return self._parse_ast(tree, content, file_rel_path, file_node_id, total_lines)
        except Exception:
            return self._parse_regex(content, file_rel_path, file_node_id, total_lines)

    def _parse_ast(self, tree: ast.AST, content: str, file_rel_path: str, file_node_id: str, total_lines: int) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        nodes = []
        edges = []
        imported_modules = []

        # 1. Imports
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    mod = alias.name
                    imp_id = f"module:{mod}"
                    if imp_id not in imported_modules:
                        imported_modules.append(imp_id)
                        nodes.append({
                            "id": imp_id,
                            "label": mod,
                            "type": "Module",
                            "path": None,
                            "description": f"Imported Python module {mod}"
                        })
                        edges.append({"source": file_node_id, "target": imp_id, "relation": "imports"})
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imp_id = f"module:{node.module}"
                    if imp_id not in imported_modules:
                        imported_modules.append(imp_id)
                        nodes.append({
                            "id": imp_id,
                            "label": node.module,
                            "type": "Module",
                            "path": None,
                            "description": f"Imported Python module {node.module}"
                        })
                        edges.append({"source": file_node_id, "target": imp_id, "relation": "imports"})

        # 2. Classes & Functions
        for item in tree.body:
            if isinstance(item, ast.ClassDef):
                cname = item.name
                cid = f"class:{file_rel_path}:{cname}"
                start_l = item.lineno
                end_l = getattr(item, "end_lineno", start_l)
                doc = ast.get_docstring(item) or ""
                bases = []
                for b in item.bases:
                    try:
                        bases.append(ast.unparse(b))
                    except Exception:
                        pass

                decorators = []
                for d in item.decorator_list:
                    try:
                        decorators.append(f"@{ast.unparse(d)}")
                    except Exception:
                        pass

                method_names = [n.name for n in item.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]

                class_meta = {
                    "start_line": start_l,
                    "end_line": end_l,
                    "bases": bases,
                    "decorators": decorators,
                    "methods": method_names,
                    "docstring": doc[:300] if doc else ""
                }

                nodes.append({
                    "id": cid,
                    "label": cname,
                    "type": "Class",
                    "path": file_rel_path,
                    "description": f"Python Class {cname} (L{start_l}-L{end_l}) in {file_rel_path}",
                    "metadata": class_meta
                })
                edges.append({"source": file_node_id, "target": cid, "relation": "defines"})
                edges.append({"source": cid, "target": file_node_id, "relation": "declared_in"})

                for mod_id in imported_modules:
                    edges.append({"source": cid, "target": mod_id, "relation": "uses"})

                for base in bases:
                    edges.append({"source": cid, "target": f"class:{base}", "relation": "inherits"})

                # Methods inside Class
                for sub in item.body:
                    if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        f_node, f_edges = self._extract_func(sub, file_rel_path, cid, file_node_id)
                        nodes.append(f_node)
                        edges.extend(f_edges)

                    # SQLAlchemy __tablename__
                    elif isinstance(sub, ast.Assign):
                        for target in sub.targets:
                            if isinstance(target, ast.Name) and target.id == "__tablename__":
                                if isinstance(sub.value, ast.Constant) and isinstance(sub.value.value, str):
                                    tbl = sub.value.value
                                    tid = f"schema:{tbl}"
                                    nodes.append({
                                        "id": tid,
                                        "label": tbl,
                                        "type": "Schema",
                                        "path": file_rel_path,
                                        "description": f"SQLAlchemy database table '{tbl}'",
                                        "metadata": {"start_line": sub.lineno, "end_line": getattr(sub, "end_lineno", sub.lineno)}
                                    })
                                    edges.append({"source": cid, "target": tid, "relation": "maps_to_table"})
                                    edges.append({"source": tid, "target": cid, "relation": "mapped_by"})

            elif isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                f_node, f_edges = self._extract_func(item, file_rel_path, file_node_id, file_node_id)
                nodes.append(f_node)
                edges.extend(f_edges)

        return nodes, edges

    def _extract_func(self, node: ast.AST, file_rel_path: str, parent_id: str, file_node_id: str) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        fname = node.name
        fid = f"func:{file_rel_path}:{fname}"
        start_l = node.lineno
        end_l = getattr(node, "end_lineno", start_l)
        is_async = isinstance(node, ast.AsyncFunctionDef)
        doc = ast.get_docstring(node) or ""

        decorators = []
        for d in node.decorator_list:
            try:
                decorators.append(f"@{ast.unparse(d)}")
            except Exception:
                pass

        return_type = None
        if node.returns:
            try:
                return_type = ast.unparse(node.returns)
            except Exception:
                pass

        params = []
        for arg in node.args.args:
            ptype = None
            if arg.annotation:
                try:
                    ptype = ast.unparse(arg.annotation)
                except Exception:
                    pass
            params.append({"name": arg.arg, "type": ptype})

        if node.args.vararg:
            params.append({"name": f"*{node.args.vararg.arg}", "type": None})
        if node.args.kwarg:
            params.append({"name": f"**{node.args.kwarg.arg}", "type": None})

        param_strs = []
        for p in params:
            if p["type"]:
                param_strs.append(f"{p['name']}: {p['type']}")
            else:
                param_strs.append(p["name"])

        async_prefix = "async " if is_async else ""
        ret_suffix = f" -> {return_type}" if return_type else ""
        signature = f"{async_prefix}def {fname}({', '.join(param_strs)}){ret_suffix}"

        func_meta = {
            "start_line": start_l,
            "end_line": end_l,
            "signature": signature,
            "parameters": params,
            "return_type": return_type,
            "is_async": is_async,
            "decorators": decorators,
            "docstring": doc[:300] if doc else ""
        }

        func_node = {
            "id": fid,
            "label": fname,
            "type": "Function",
            "path": file_rel_path,
            "description": f"Python function {fname} (L{start_l}-L{end_l}) in {file_rel_path}",
            "metadata": func_meta
        }

        f_edges = [
            {"source": parent_id, "target": fid, "relation": "defines"},
            {"source": fid, "target": file_node_id, "relation": "declared_in"}
        ]
        return func_node, f_edges

    def _parse_regex(self, content: str, file_rel_path: str, file_node_id: str, total_lines: int) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        nodes = []
        edges = []
        lines = content.splitlines()

        for idx, line in enumerate(lines, start=1):
            m_func = re.match(r"^\s*(?:async\s+)?def\s+([A-Za-z0-9_]+)\s*\((.*?)\)(?:\s*->\s*(.*?))?:", line)
            if m_func:
                fname = m_func.group(1)
                params_raw = m_func.group(2)
                ret_type = m_func.group(3).strip() if m_func.group(3) else None
                fid = f"func:{file_rel_path}:{fname}"
                nodes.append({
                    "id": fid,
                    "label": fname,
                    "type": "Function",
                    "path": file_rel_path,
                    "description": f"Python function {fname} (L{idx}) in {file_rel_path}",
                    "metadata": {
                        "start_line": idx,
                        "end_line": idx,
                        "signature": line.strip(),
                        "return_type": ret_type,
                        "is_async": "async " in line
                    }
                })
                edges.append({"source": file_node_id, "target": fid, "relation": "defines"})
                edges.append({"source": fid, "target": file_node_id, "relation": "declared_in"})

        return nodes, edges
