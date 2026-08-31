import re
from typing import List, Dict, Any, Tuple
from app.ingestion.parsers.base import BaseParser

class CsharpParser(BaseParser):
    def parse(self, content: str, file_rel_path: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        nodes = []
        edges = []
        file_node_id = f"file:{file_rel_path}"

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
            r"(?:\[Table\([\"'](.*?)[\"']\)\].*?)?(?:public|internal|private)?\s*(?:static|abstract|sealed)?\s*(class|interface|struct)\s+([A-Za-z0-9_]+)(?:\s*:\s*([A-Za-z0-9_,\s]+))?",
            content,
            re.DOTALL
        )

        for m in class_matches:
            table_name = m.group(1)
            kind = m.group(2)
            class_name = m.group(3)
            inheritance = m.group(4)

            if not class_name:
                continue

            class_node_id = f"class:{file_rel_path}:{class_name}"
            nodes.append({
                "id": class_node_id,
                "label": class_name,
                "type": "Class" if kind == "class" else kind.capitalize(),
                "path": file_rel_path,
                "description": f"C# {kind} {class_name} in {file_rel_path}"
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
                for parent in [p.strip() for p in inheritance.split(",") if p.strip()]:
                    edges.append({
                        "source": class_node_id,
                        "target": f"class:{parent}",
                        "relation": "inherits"
                    })

            if table_name:
                table_id = f"schema:{table_name}"
                nodes.append({
                    "id": table_id,
                    "label": table_name,
                    "type": "Schema",
                    "path": file_rel_path,
                    "description": f"Entity Framework database table '{table_name}'"
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

        return nodes, edges
