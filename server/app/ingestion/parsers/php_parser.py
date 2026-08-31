import re
from typing import List, Dict, Any, Tuple
from app.ingestion.parsers.base import BaseParser

class PhpParser(BaseParser):
    def parse(self, content: str, file_rel_path: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        nodes = []
        edges = []
        file_node_id = f"file:{file_rel_path}"

        # 1. Namespaces & Top-level Use Statements (Imports)
        namespace_match = re.search(r"namespace\s+([A-Za-z0-9_\\]+);", content)
        current_namespace = namespace_match.group(1) if namespace_match else ""

        use_map = {}
        use_matches = re.findall(r"^use\s+([A-Za-z0-9_\\]+)(?:\s+as\s+([A-Za-z0-9_]+))?;", content, re.MULTILINE)
        for use_item in use_matches:
            full_use = use_item[0]
            alias = use_item[1] or full_use.split('\\')[-1]
            use_map[alias] = full_use
            imp_id = f"class:{full_use}"
            nodes.append({
                "id": imp_id,
                "label": alias,
                "type": "Class",
                "path": None,
                "description": f"Imported PHP Class/Namespace {full_use}"
            })
            edges.append({
                "source": file_node_id,
                "target": imp_id,
                "relation": "imports"
            })

        # 2. Classes, Interfaces, Traits
        class_matches = re.finditer(
            r"(?:abstract\s+|final\s+)?(class|interface|trait)\s+([A-Za-z0-9_]+)(?:\s+extends\s+([A-Za-z0-9_\\]+))?(?:\s+implements\s+([A-Za-z0-9_\\,\s]+))?",
            content
        )
        
        current_class_id = None
        for m in class_matches:
            kind = m.group(1) # class, interface, trait
            class_name = m.group(2)
            extends_class = m.group(3)
            implements_interfaces = m.group(4)

            full_class_name = f"{current_namespace}\\{class_name}" if current_namespace else class_name
            class_node_id = f"class:{file_rel_path}:{class_name}"
            current_class_id = class_node_id

            nodes.append({
                "id": class_node_id,
                "label": class_name,
                "type": "Class" if kind == "class" else kind.capitalize(),
                "path": file_rel_path,
                "description": f"PHP {kind} {full_class_name} defined in {file_rel_path}",
                "metadata": {"namespace": current_namespace, "kind": kind, "file": file_rel_path}
            })
            
            # Relación bidireccional y explícita: Archivo -> Clase (defines) y Clase -> Archivo (declared_in)
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

            # También vincular los use/imports del archivo directamente a la clase
            for use_item in use_matches:
                full_use = use_item[0]
                imp_id = f"class:{full_use}"
                edges.append({
                    "source": class_node_id,
                    "target": imp_id,
                    "relation": "uses"
                })

            if extends_class:
                edges.append({
                    "source": class_node_id,
                    "target": f"class:{extends_class}",
                    "relation": "inherits"
                })

            if implements_interfaces:
                for iface in [i.strip() for i in implements_interfaces.split(",") if i.strip()]:
                    edges.append({
                        "source": class_node_id,
                        "target": f"class:{iface}",
                        "relation": "implements"
                    })

        # 3. Database Table Detection (Eloquent Model: protected $table = 'audit.audit_trail')
        table_matches = re.findall(r"protected\s+\$table\s*=\s*['\"](.*?)['\"];", content)
        for tbl in table_matches:
            table_id = f"schema:{tbl}"
            
            fillable_match = re.search(r"protected\s+\$fillable\s*=\s*\[(.*?)\];", content, re.DOTALL)
            fillable_cols = []
            if fillable_match:
                fillable_cols = re.findall(r"['\"]([A-Za-z0-9_]+)['\"]", fillable_match.group(1))

            nodes.append({
                "id": table_id,
                "label": tbl,
                "type": "Schema",
                "path": file_rel_path,
                "description": f"Database table '{tbl}' defined in Eloquent Model",
                "metadata": {"columns": fillable_cols}
            })
            
            if current_class_id:
                edges.append({
                    "source": current_class_id,
                    "target": table_id,
                    "relation": "maps_to_table"
                })
                edges.append({
                    "source": table_id,
                    "target": current_class_id,
                    "relation": "mapped_by"
                })
            else:
                edges.append({
                    "source": file_node_id,
                    "target": table_id,
                    "relation": "defines"
                })

        # 4. Functions & Methods
        func_matches = re.finditer(
            r"(?:public|protected|private)?\s*(?:static\s+)?function\s+([A-Za-z0-9_]+)\s*\(",
            content
        )
        for m in func_matches:
            func_name = m.group(1)
            if func_name.startswith("__") and func_name not in ("__construct", "__invoke"):
                continue
            func_node_id = f"func:{file_rel_path}:{func_name}"
            nodes.append({
                "id": func_node_id,
                "label": func_name,
                "type": "Function",
                "path": file_rel_path,
                "description": f"PHP Method {func_name}() in {file_rel_path}"
            })
            
            parent_id = current_class_id if current_class_id else file_node_id
            edges.append({
                "source": parent_id,
                "target": func_node_id,
                "relation": "defines"
            })
            edges.append({
                "source": func_node_id,
                "target": file_node_id,
                "relation": "declared_in"
            })

        return nodes, edges
