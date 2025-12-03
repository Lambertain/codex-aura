from typing import List, Optional, Literal

from pydantic import BaseModel, field_validator


class Node(BaseModel):
    id: str
    type: Literal["file", "class", "function"]
    name: str
    path: str
    lines: Optional[List[int]] = None
    docstring: Optional[str] = None

    @field_validator('lines')
    @classmethod
    def validate_lines(cls, v):
        if v is not None and len(v) != 2:
            raise ValueError('lines must be a list of exactly 2 integers or None')
        return v
