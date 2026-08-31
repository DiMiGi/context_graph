import re
from typing import List, Dict, Any, Tuple
from app.ingestion.parsers.base import BaseParser

class SqlParser(BaseParser):
    def parse(self, content: str, file_rel_path: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        nodes = []
        edges = []
        file_node_id = f"file:{file_rel_path}"

        # CREATE TABLE
        sql_tables = re.findall(r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?([A-Za-z0-9_\.\"]+)", content, re.IGNORECASE)
        for table in sql_tables:
            clean_table = table.replace('"', '').split('.')[-1]
            table_id = f"schema:{clean_table}"
            nodes.append({
                "id": table_id,
                "label": clean_table,
                "type": "Schema",
                "path": file_rel_path,
                "description": f"SQL Table '{clean_table}' in {file_rel_path}"
            })
            edges.append({
                "source": file_node_id,
                "target": table_id,
                "relation": "defines"
            })

        return nodes, edges
