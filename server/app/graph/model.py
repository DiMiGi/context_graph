from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

class Node(BaseModel):
    id: str
    label: str
    type: str = "Concept"  # Module, Class, Function, Document, Concept, Schema, Config, Asset
    path: Optional[str] = None
    description: Optional[str] = ""
    community: Optional[int] = 0
    origin: str = "auto"   # "auto" (creado por scanner/indexación) o "manual" / "ai" (creado/editado por IA o usuario)
    is_custom: bool = False # True si fue creado/modificado manualmente o por la IA
    metadata: Dict[str, Any] = Field(default_factory=dict)

class Edge(BaseModel):
    source: str
    target: str
    relation: str = "relates_to"  # calls, imports, defines, references, explains, declared_in, uses, maps_to_table
    weight: Optional[float] = 1.0
    origin: str = "auto"   # "auto" o "manual" / "ai"
    is_custom: bool = False # True si fue creada por la IA o usuario
    metadata: Dict[str, Any] = Field(default_factory=dict)

class GraphData(BaseModel):
    project_id: str
    name: str
    nodes: List[Node] = Field(default_factory=list)
    edges: List[Edge] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
