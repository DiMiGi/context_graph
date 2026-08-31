from typing import List, Dict, Any, Tuple
from app.ingestion.parsers.base import BaseParser

class TextDocParser(BaseParser):
    def parse(self, content: str, file_rel_path: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        # Simple document node
        return [], []
