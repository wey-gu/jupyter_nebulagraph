from pydantic import BaseModel
from typing import Optional


class LoadDataArgsModel(BaseModel):
    source: str
    space: str
    # Args to load data
    batch: int = 100
    header: bool = False
    limit: Optional[int] = None
    # Args of data mapping
    tag: Optional[str] = None
    edge: Optional[str] = None
    vid: Optional[int] = None
    src: Optional[int] = None
    dst: Optional[int] = None
    props: Optional[str] = None
    rank: Optional[int] = None
