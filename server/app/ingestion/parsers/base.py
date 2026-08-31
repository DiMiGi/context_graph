from abc import ABC, abstractmethod
from typing import List, Dict, Any, Tuple

class BaseParser(ABC):
    @abstractmethod
    def parse(self, content: str, file_rel_path: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Retorna (nodes, edges) extraídos del archivo.
        """
        pass
