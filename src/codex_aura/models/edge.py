from enum import Enum
from typing import Optional

from pydantic import BaseModel


class EdgeType(str, Enum):
    IMPORTS = "IMPORTS"


class Edge(BaseModel):
    source: str
    target: str
    type: EdgeType
    line: Optional[int] = None