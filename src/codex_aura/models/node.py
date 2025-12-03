from typing import List, Optional

from pydantic import BaseModel


class Node(BaseModel):
    id: str
    type: str  # "file", "class", "function"
    name: str
    path: str
    lines: Optional[List[int]] = None
    docstring: Optional[str] = None
