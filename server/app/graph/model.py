from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

class Node(BaseModel):
    id: str
    label: str
    type: str = "Concept"  # Module, Class, Function, Document, Concept, Schema
    path: Optional[str] = None
    description: Optional[str] = ""
    community: Optional[int] = 0
    metadata: Dict[str, Any] = Field(default_factory=dict)

class Edge(BaseModel):
    source: str
    target: str
    relation: str = "relates_to"  # calls, imports, defines, references, explains
    weight: Optional[float] = 1.0
    metadata: Dict[str, Any] = Field(default_factory=dict)

class GraphData(BaseModel):
    project_id: str
    name: str
    nodes: List[Node] = Field(default_factory=list)
    edges: List[Edge] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
