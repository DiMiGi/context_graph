import re
from typing import List, Dict, Any, Tuple

class CodeParser:
    """
    Parser semántico para extracción rápida de símbolos de código
    (clases, funciones, imports y relaciones).
    """

    @classmethod
    def parse_python(cls, content: str, file_rel_path: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        nodes = []
        edges = []
        file_node_id = f"file:{file_rel_path}"

        # 1. Imports
        import_matches = re.findall(r"^(?:from\s+([\w\.]+)\s+import\s+([\w\s,\*]+)|import\s+([\w\.]+))", content, re.MULTILINE)
        for imp in import_matches:
            module = imp[0] or imp[2]
            if module:
                imp_node_id = f"module:{module}"
                nodes.append({
                    "id": imp_node_id,
                    "label": module,
                    "type": "Module",
                    "path": None,
                    "description": f"External/Internal imported module {module}"
                })
                edges.append({
                    "source": file_node_id,
                    "target": imp_node_id,
                    "relation": "imports"
                })

        # 2. Classes
        class_matches = re.finditer(r"^class\s+([A-Za-z0-9_]+)(?:\((.*?)\))?:", content, re.MULTILINE)
        for m in class_matches:
            class_name = m.group(1)
            bases = m.group(2)
            class_node_id = f"class:{file_rel_path}:{class_name}"
            nodes.append({
                "id": class_node_id,
                "label": class_name,
                "type": "Class",
                "path": file_rel_path,
                "description": f"Class defined in {file_rel_path}"
            })
            edges.append({
                "source": file_node_id,
                "target": class_node_id,
                "relation": "defines"
            })
            if bases:
                for base in [b.strip() for b in bases.split(",") if b.strip()]:
                    edges.append({
                        "source": class_node_id,
                        "target": f"class:{base}",
                        "relation": "inherits"
                    })

        # 3. Functions
        func_matches = re.finditer(r"^(?:\s*async\s+)?def\s+([A-Za-z0-9_]+)\s*\(", content, re.MULTILINE)
        for m in func_matches:
            func_name = m.group(1)
            func_node_id = f"func:{file_rel_path}:{func_name}"
            nodes.append({
                "id": func_node_id,
                "label": func_name,
                "type": "Function",
                "path": file_rel_path,
                "description": f"Function defined in {file_rel_path}"
            })
            edges.append({
                "source": file_node_id,
                "target": func_node_id,
                "relation": "defines"
            })

        return nodes, edges

    @classmethod
    def parse_js_ts(cls, content: str, file_rel_path: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        nodes = []
        edges = []
        file_node_id = f"file:{file_rel_path}"

        # 1. Imports
        import_matches = re.findall(r"import\s+(?:.*?from\s+)?['\"](.*?)['\"]", content)
        for imp in import_matches:
            imp_node_id = f"module:{imp}"
            nodes.append({
                "id": imp_node_id,
                "label": imp,
                "type": "Module",
                "path": None,
                "description": f"Imported module/file {imp}"
            })
            edges.append({
                "source": file_node_id,
                "target": imp_node_id,
                "relation": "imports"
            })

        # 2. Classes
        class_matches = re.finditer(r"class\s+([A-Za-z0-9_]+)", content)
        for m in class_matches:
            class_name = m.group(1)
            class_node_id = f"class:{file_rel_path}:{class_name}"
            nodes.append({
                "id": class_node_id,
                "label": class_name,
                "type": "Class",
                "path": file_rel_path,
                "description": f"Class defined in {file_rel_path}"
            })
            edges.append({
                "source": file_node_id,
                "target": class_node_id,
                "relation": "defines"
            })

        # 3. Functions & Exports
        func_matches = re.finditer(r"(?:export\s+)?(?:async\s+)?function\s+([A-Za-z0-9_]+)|(?:const|let|var)\s+([A-Za-z0-9_]+)\s*=\s*(?:async\s*)?\([^)]*\)\s*=>", content)
        for m in func_matches:
            func_name = m.group(1) or m.group(2)
            if func_name:
                func_node_id = f"func:{file_rel_path}:{func_name}"
                nodes.append({
                    "id": func_node_id,
                    "label": func_name,
                    "type": "Function",
                    "path": file_rel_path,
                    "description": f"Function/Arrow defined in {file_rel_path}"
                })
                edges.append({
                    "source": file_node_id,
                    "target": func_node_id,
                    "relation": "defines"
                })

        return nodes, edges

    @classmethod
    def parse_sql_prisma(cls, content: str, file_rel_path: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        nodes = []
        edges = []
        file_node_id = f"file:{file_rel_path}"

        # SQL Tables
        sql_tables = re.findall(r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?([A-Za-z0-9_\.\"]+)", content, re.IGNORECASE)
        for table in sql_tables:
            clean_table = table.replace('"', '').split('.')[-1]
            table_id = f"schema:{clean_table}"
            nodes.append({
                "id": table_id,
                "label": clean_table,
                "type": "Schema",
                "path": file_rel_path,
                "description": f"Database table defined in {file_rel_path}"
            })
            edges.append({
                "source": file_node_id,
                "target": table_id,
                "relation": "defines"
            })

        # Prisma Models
        prisma_models = re.findall(r"model\s+([A-Za-z0-9_]+)\s*\{", content)
        for model in prisma_models:
            model_id = f"schema:{model}"
            nodes.append({
                "id": model_id,
                "label": model,
                "type": "Schema",
                "path": file_rel_path,
                "description": f"Prisma entity defined in {file_rel_path}"
            })
            edges.append({
                "source": file_node_id,
                "target": model_id,
                "relation": "defines"
            })

        return nodes, edges
